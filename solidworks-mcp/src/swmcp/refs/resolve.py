"""Resolve an :class:`EntityRef` back to a live COM entity.

REF-006 is the point of this module. When several entities match a reference equally
well, it raises with **every** tied candidate attached, each carrying paste-ready
``tool_args``. Silently taking the first face is how an automated fillet ends up on
the wrong edge, and the model has no way to notice.

When the persistent reference has died but semantic matching succeeds, the reference is
reported as *healed*: the caller gets the drift and a refreshed reference to store.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

from swmcp.com.marshal import call_with_outparams, normalize_sequence, out_long, try_com_member
from swmcp.decode.status import PERSIST_STATUS, decode_status
from swmcp.errors import SwMcpError, reference_error
from swmcp.refs.capture import capture, edges_of, faces_of
from swmcp.refs.model import EntityRef, ReferenceDrift
from swmcp.refs.signature import MIN_SCORE, drift_between, score_candidate


@dataclass
class Resolution:
    entity: Any
    via: str
    refreshed: EntityRef
    drift: ReferenceDrift | None = None
    score: int | None = None
    warnings: list[str] = field(default_factory=list)


def _by_persistent(doc: Any, ref: EntityRef) -> tuple[Any | None, str | None]:
    if ref.persistent is None:
        return None, None
    try:
        blob = base64.b64decode(ref.persistent.data_b64)
    except (ValueError, TypeError):
        return None, "the stored persistent reference is not valid base64"

    error = out_long(0)
    try:
        entity, outs = call_with_outparams(
            doc.Extension.GetObjectByPersistReference3, blob, error, outparams=(error,)
        )
    except Exception as exc:
        return None, f"GetObjectByPersistReference3 failed: {exc}"

    status = decode_status(PERSIST_STATUS, outs[0])
    if entity is None or (outs[0] and "swPersistReferencedObject_Ok" not in status.names):
        return None, status.summary
    return entity, None


def _candidates(session: Any, doc: Any, ref: EntityRef, scope: Any | None) -> list[Any]:
    """Entities worth comparing against, narrowed as far as the reference allows."""
    wanted = ref.semantic

    if scope is not None:
        owners = [scope]
    else:
        owners = []
        # Prefer the owning feature; it is the tightest scope a reference names.
        for name in reversed(wanted.feature_ancestry):
            feature = _find_feature(doc, name)
            if feature is not None:
                owners.append(feature)
                break
        if not owners:
            owners = _all_bodies(doc)

    found: list[Any] = []
    for owner in owners:
        if ref.kind == "edge":
            found.extend(edges_of(owner))
        else:
            found.extend(faces_of(owner))
    return found


def _find_feature(doc: Any, name: str) -> Any | None:
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        if str(try_com_member(feature, "Name", default="")) == name:
            return feature
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return None


def _all_bodies(doc: Any) -> list[Any]:
    """Bodies reachable without an IPartDoc cast, by walking solid-body features."""
    bodies: list[Any] = []
    seen: set[str] = set()
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        for face in normalize_sequence(try_com_member(feature, "GetFaces", default=None)):
            body = try_com_member(face, "GetBody", default=None)
            if body is None:
                continue
            key = str(try_com_member(body, "Name", default=id(body)))
            if key not in seen:
                seen.add(key)
                bodies.append(body)
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return bodies


def resolve(
    session: Any,
    doc: Any,
    ref: EntityRef,
    *,
    scope: Any | None = None,
    max_candidates: int = 2000,
) -> Resolution:
    """Resolve a reference, or raise with candidates rather than guessing."""
    warnings: list[str] = []

    entity, failure = _by_persistent(doc, ref)
    if entity is not None:
        return Resolution(
            entity=entity,
            via="persistent",
            refreshed=capture(session, doc, entity),
            drift=ReferenceDrift(via="persistent"),
        )
    if failure:
        warnings.append(f"persistent reference did not resolve ({failure}); matching on geometry")

    candidates = _candidates(session, doc, ref, scope)
    if len(candidates) > max_candidates:
        raise SwMcpError(
            reference_error(
                "REF_SCOPE_TOO_LARGE",
                f"{len(candidates)} entities are in scope, above the {max_candidates} limit.",
                context={"candidate_count": len(candidates)},
                remediation=["Narrow the search by naming the owning feature or body."],
            )
        )

    scored = []
    for candidate in candidates:
        fresh = capture(session, doc, candidate)
        result = score_candidate(ref.semantic, fresh.semantic)
        if result.geometry_type_matches and result.total >= MIN_SCORE:
            scored.append((result, candidate, fresh))

    if not scored:
        raise SwMcpError(
            reference_error(
                "REF_NOT_FOUND",
                f"No {ref.semantic.geometry_type} in this document matches the reference "
                f"{ref.label or ref.semantic.signature!r}.",
                context={
                    "searched": len(candidates),
                    "persistent_failure": failure,
                    "wanted": ref.semantic.model_dump(mode="json"),
                },
                remediation=[
                    "Re-probe the model to capture a fresh reference.",
                    "The owning feature may have been deleted, renamed, or suppressed.",
                ],
            )
        )

    best = max(result.total for result, _, _ in scored)
    winners = [(result, entity, fresh) for result, entity, fresh in scored if result.total == best]

    if len(winners) > 1:
        raise SwMcpError(
            reference_error(
                "REF_AMBIGUOUS",
                f"{len(winners)} entities match this reference equally well (score {best}). "
                "Refusing to choose one.",
                context={
                    "score": best,
                    "candidates": [
                        {
                            "label": fresh.label,
                            "tool_args": fresh.tool_args(),
                            "why": result.reasons,
                        }
                        for result, _, fresh in winners[:20]
                    ],
                },
                remediation=[
                    "Pick one candidate and pass its tool_args verbatim.",
                    "Or narrow the search with a face probe filtered by radius, area, "
                    "normal direction, or a containing point.",
                ],
            )
        )

    result, entity, fresh = winners[0]
    moved_mm, radius_delta_mm, area_ratio = drift_between(
        ref.semantic.measurements, fresh.semantic.measurements
    )
    return Resolution(
        entity=entity,
        via="semantic",
        refreshed=fresh,
        score=result.total,
        drift=ReferenceDrift(
            via="semantic",
            score=result.total,
            persistent_status=failure,
            moved_mm=moved_mm,
            radius_delta_mm=radius_delta_mm,
            area_ratio=area_ratio,
            note="Matched on geometry. Store the refreshed reference to avoid re-searching.",
        ),
        warnings=warnings,
    )
