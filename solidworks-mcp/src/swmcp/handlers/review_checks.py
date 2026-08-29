"""Document review: inspect, validate, audit holes, and report.

REV-001, REV-002, REV-004, REV-005, and REV-007.

Almost nothing here talks to COM directly. The server already measures volume, walks
the feature tree, reads sketch solver state, and finds cylindrical faces in the B-Rep —
review is those facts assembled and judged, and judging them is the part the caller
owns. REV-007 is explicit that a review policy is domain knowledge, not a rule the
server gets to impose, so every check in ``ReviewPolicy`` can be turned off or have its
severity changed. A check that cannot be disabled is a policy pretending to be a fact.

Every finding carries a ``source``: what was read to reach it. A verdict a reader
cannot re-derive is an opinion, and REV-007 is blunt that a file existence check is not
an engineering validation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import NonModelSideEffect, ReadSafety
from swmcp.com.marshal import normalize_sequence, try_com_member
from swmcp.context import OpContext
from swmcp.envelope import ArtifactEvidence
from swmcp.errors import SwMcpError, make_error
from swmcp.modeling import (
    bodies,
    body_summary,
    configuration_names,
    describe_feature,
    document_density,
    document_mass_properties,
    document_material,
)
from swmcp.safety.overwrite import resolve_output_path
from swmcp.safety.paths import assert_output_path
from swmcp.schemas.review_checks import (
    HoleExpectation,
    Outcome,
    ReviewFinding,
    ReviewHolesArgs,
    ReviewHolesResult,
    ReviewInspectArgs,
    ReviewInspectResult,
    ReviewPolicy,
    ReviewReportArgs,
    ReviewReportResult,
    ReviewValidateArgs,
    ReviewValidateResult,
)
from swmcp.sketching import sketch_state
from swmcp.units import from_meters

_RANK: dict[Outcome, int] = {"pass": 0, "warn": 1, "block": 2}

_ALL_SECTIONS = (
    "document",
    "features",
    "sketches",
    "bodies",
    "configurations",
    "equations",
    "dimensions",
    "properties",
    "components",
    "mass",
)


def _worst(findings: list[ReviewFinding]) -> Outcome:
    worst: Outcome = "pass"
    for finding in findings:
        if _RANK[finding.outcome] > _RANK[worst]:
            worst = finding.outcome
    return worst


def _feature_rows(doc: Any, limit: int) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        if len(rows) >= limit:
            return rows, True
        rows.append(describe_feature(feature))
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return rows, False


def _sketch_rows(doc: Any, limit: int) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        type_name = str(try_com_member(feature, "GetTypeName2", default="") or "")
        if type_name in {"ProfileFeature", "3DProfileFeature"}:
            if len(rows) >= limit:
                return rows, True
            sketch = try_com_member(feature, "GetSpecificFeature2", default=None)
            row = {"name": str(try_com_member(feature, "Name", default="") or "")}
            if sketch is not None:
                row.update(sketch_state(sketch))
            rows.append(row)
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return rows, False


def _errored_features(doc: Any) -> list[str]:
    names: list[str] = []
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        described = describe_feature(feature)
        if described.get("error_code"):
            names.append(described["name"])
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return names


def _suppressed_features(doc: Any) -> list[str]:
    names: list[str] = []
    feature = try_com_member(doc, "FirstFeature", default=None)
    guard = 0
    while feature is not None and guard < 5000:
        guard += 1
        if try_com_member(feature, "IsSuppressed", default=False):
            names.append(str(try_com_member(feature, "Name", default="") or ""))
        feature = try_com_member(feature, "GetNextFeature", default=None)
    return names


@op(
    name="sw_review_inspect",
    tier="core",
    domains=("review",),
    tags=("review", "inspect", "audit"),
    summary=(
        "Gather the document's feature tree, sketches, bodies, configurations, mass, "
        "and metadata into one payload, so a review is one call rather than eight."
    ),
    safety=ReadSafety(),
    partially_satisfies=("REV-001",),
    precondition="any",
    idempotent=True,
    timeout_s=600.0,
)
def review_inspect(ctx: OpContext, args: ReviewInspectArgs) -> ReviewInspectResult:
    doc = ctx.require_doc()
    wanted = tuple(args.sections) if args.sections else _ALL_SECTIONS
    info = ctx.session.describe(doc)
    sections: dict[str, Any] = {}
    truncated: list[str] = []

    def note(name: str, cut: bool) -> None:
        if cut:
            truncated.append(name)

    if "features" in wanted:
        rows, cut = _feature_rows(doc, args.max_items)
        sections["features"] = {"count": len(rows), "items": rows}
        note("features", cut)

    if "sketches" in wanted:
        rows, cut = _sketch_rows(doc, args.max_items)
        sections["sketches"] = {
            "count": len(rows),
            "fully_defined": sum(1 for r in rows if r.get("fully_defined")),
            "items": rows,
        }
        note("sketches", cut)

    if "bodies" in wanted:
        density = document_density(doc) or 1.0
        found = bodies(doc)[: args.max_items]
        sections["bodies"] = {
            "count": len(found),
            "items": [body_summary(body, density) for body in found],
        }
        note("bodies", len(bodies(doc)) > args.max_items)

    if "configurations" in wanted:
        names = configuration_names(doc)
        sections["configurations"] = {"count": len(names), "items": names[: args.max_items]}
        note("configurations", len(names) > args.max_items)

    if "mass" in wanted:
        sections["mass"] = document_mass_properties(doc)

    if "components" in wanted:
        components = [
            {
                "name": str(try_com_member(c, "Name2", default="") or ""),
                "path": str(try_com_member(c, "GetPathName", default="") or ""),
                "suppressed": bool(try_com_member(c, "IsSuppressed", default=False)),
            }
            for c in normalize_sequence(try_com_member(doc, "GetComponents", False, default=None))
            if c is not None
        ]
        if components:
            sections["components"] = {
                "count": len(components),
                "items": components[: args.max_items],
            }
            note("components", len(components) > args.max_items)

    return ReviewInspectResult(
        document=info.as_dict() if hasattr(info, "as_dict") else dict(info),
        sections=sections,
        truncated=truncated,
        warnings=(
            [f"These sections were cut at max_items: {', '.join(truncated)}."]
            if truncated
            else []
        ),
    )


def _run_policy(doc: Any, policy: ReviewPolicy) -> list[ReviewFinding]:
    """Every rule the policy turned on, each carrying what it read."""
    findings: list[ReviewFinding] = []

    def add(name: str, ok: bool, detail: str, source: str, fail: Outcome = "block") -> None:
        outcome: Outcome = "pass" if ok else policy.severity.get(name, fail)
        findings.append(
            ReviewFinding(name=name, outcome=outcome, detail=detail, source=source)
        )

    if policy.require_no_feature_errors:
        errored = _errored_features(doc)
        add(
            "features_without_errors",
            not errored,
            f"{len(errored)} feature(s) report an error: {', '.join(errored) or 'none'}",
            "IFeature::GetErrorCode2 over the whole tree",
        )

    mass = document_mass_properties(doc)
    volume_mm3 = (mass.get("volume_m3") or 0.0) * 1e9

    if policy.require_bodies_min is not None:
        found = len(bodies(doc))
        add(
            "body_count",
            found >= policy.require_bodies_min,
            f"{found} solid body(ies), policy requires at least {policy.require_bodies_min}",
            "bodies walked from the feature tree",
        )

    if policy.forbid_zero_volume:
        add(
            "non_zero_volume",
            volume_mm3 > 0,
            f"total volume {volume_mm3:.6g} mm³",
            "IModelDocExtension::GetMassProperties",
        )

    if policy.min_volume_mm3 is not None:
        add(
            "volume_at_least",
            volume_mm3 >= policy.min_volume_mm3,
            f"{volume_mm3:.6g} mm³ against a floor of {policy.min_volume_mm3:.6g} mm³",
            "IModelDocExtension::GetMassProperties",
        )

    if policy.max_volume_mm3 is not None:
        add(
            "volume_at_most",
            volume_mm3 <= policy.max_volume_mm3,
            f"{volume_mm3:.6g} mm³ against a ceiling of {policy.max_volume_mm3:.6g} mm³",
            "IModelDocExtension::GetMassProperties",
        )

    sketches, _ = _sketch_rows(doc, 5000)
    if policy.require_fully_defined_sketches:
        loose = [s["name"] for s in sketches if not s.get("fully_defined")]
        add(
            "sketches_fully_defined",
            not loose,
            f"{len(loose)} sketch(es) not fully defined: {', '.join(loose) or 'none'}",
            "ISketch::GetConstrainedStatus",
            fail="warn",
        )

    if policy.forbid_dangling_relations:
        dangling = [s["name"] for s in sketches if s.get("dangling_relations")]
        add(
            "no_dangling_relations",
            not dangling,
            f"{len(dangling)} sketch(es) hold dangling relations: {', '.join(dangling) or 'none'}",
            "ISketchRelationManager over each sketch",
        )

    if policy.forbid_suppressed_features:
        suppressed = _suppressed_features(doc)
        add(
            "no_suppressed_features",
            not suppressed,
            f"{len(suppressed)} suppressed: {', '.join(suppressed) or 'none'}",
            "IFeature::IsSuppressed over the whole tree",
            fail="warn",
        )

    if policy.require_material:
        density = mass.get("density_kg_m3")
        # SOLIDWORKS falls back to its own default density when no material is set, so
        # "has a density" is not the same as "has a material" — the name is what counts.
        material, _ = document_material(doc)
        add(
            "material_assigned",
            bool(material),
            f"material {material or 'not set'}, density {density} kg/m³",
            "IPartDoc::GetMaterialPropertyName2 with the density from GetMassProperties",
        )

    return findings


@op(
    name="sw_review_validate",
    tier="core",
    domains=("review",),
    tags=("review", "validate", "policy", "audit"),
    summary=(
        "Judge the document against caller-supplied rules and return pass, warn, or "
        "block findings, each naming what was read to reach it."
    ),
    safety=ReadSafety(),
    satisfies=("REV-002", "REV-007"),
    precondition="any",
    idempotent=True,
    timeout_s=600.0,
)
def review_validate(ctx: OpContext, args: ReviewValidateArgs) -> ReviewValidateResult:
    """REV-002 and REV-007.

    The rules live in the argument, not in this function. Every check can be switched
    off or have its severity changed, because what counts as a defect is domain
    knowledge — a 0.4 mm wall is fine in sheet metal and a disaster in a casting.
    """
    doc = ctx.require_doc()
    findings = _run_policy(doc, args.policy)
    counts = {"pass": 0, "warn": 0, "block": 0}
    for finding in findings:
        counts[finding.outcome] += 1

    return ReviewValidateResult(
        outcome=_worst(findings),
        findings=findings,
        blocked=counts["block"],
        warned=counts["warn"],
        passed=counts["pass"],
        warnings=(
            ["No rules were enabled, so this review checked nothing."] if not findings else []
        ),
    )


def _hole_groups(
    ctx: OpContext, doc: Any, args: ReviewHolesArgs
) -> list[dict[str, Any]]:
    """Cylindrical faces grouped by diameter, which is what a hole looks like in B-Rep."""
    from swmcp.refs.probes import ProbeFilters, probe_entities

    found, _ = probe_entities(
        ctx.session,
        doc,
        entity_class="face",
        filters=ProbeFilters(geometry_type="cylindrical_face"),
        limit=1000,
    )

    buckets: dict[float, list[Any]] = {}
    for ref in found:
        radius = ref.semantic.measurements.radius_m
        if radius is None:
            continue
        diameter = round(from_meters(radius * 2.0), 6)
        if args.min_diameter_mm is not None and diameter < args.min_diameter_mm:
            continue
        if args.max_diameter_mm is not None and diameter > args.max_diameter_mm:
            continue
        buckets.setdefault(diameter, []).append(ref)

    groups = []
    for diameter in sorted(buckets):
        refs = buckets[diameter]
        groups.append(
            {
                "diameter_mm": diameter,
                "count": len(refs),
                "faces": [
                    {
                        "label": ref.label,
                        "axis": ref.semantic.measurements.direction,
                        "at_mm": [
                            round(from_meters(v), 6)
                            for v in (ref.semantic.measurements.point_m or [])
                        ],
                        "tool_args": ref.tool_args(),
                    }
                    for ref in refs[:50]
                ],
            }
        )
    return groups


@op(
    name="sw_review_holes",
    tier="core",
    domains=("review",),
    tags=("review", "hole", "brep", "audit"),
    summary=(
        "Audit holes by their B-Rep geometry — cylindrical faces grouped by diameter, "
        "with axis and position — and compare them against expected counts."
    ),
    safety=ReadSafety(),
    partially_satisfies=("REV-004",),
    precondition="part_or_assembly",
    idempotent=True,
    timeout_s=600.0,
)
def review_holes(ctx: OpContext, args: ReviewHolesArgs) -> ReviewHolesResult:
    """REV-004.

    Holes are counted from the geometry rather than from the feature tree on purpose:
    a hole-wizard feature that failed still sits in the tree, and a hole cut by an
    extrude is not a hole feature at all. The B-Rep is what the part actually has.
    """
    doc = ctx.require_doc()
    groups = _hole_groups(ctx, doc, args)
    total = sum(group["count"] for group in groups)

    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for expectation in args.expect:
        hit = _match_expectation(expectation, groups)
        (matched if hit["satisfied"] else unmatched).append(hit)

    return ReviewHolesResult(
        hole_count=total,
        groups=groups,
        matched=matched,
        unmatched=unmatched,
        outcome="block" if unmatched else "pass",
        warnings=(
            [f"{len(unmatched)} expectation(s) were not met."] if unmatched else []
        ),
    )


def _match_expectation(
    expectation: HoleExpectation, groups: list[dict[str, Any]]
) -> dict[str, Any]:
    near = [
        group
        for group in groups
        if abs(group["diameter_mm"] - expectation.diameter_mm) <= expectation.tolerance_mm
    ]
    found = sum(group["count"] for group in near)
    return {
        "diameter_mm": expectation.diameter_mm,
        "expected_count": expectation.count,
        "found_count": found,
        "tolerance_mm": expectation.tolerance_mm,
        "satisfied": found == expectation.count,
        "detail": (
            f"{found} hole(s) at Ø{expectation.diameter_mm} ±{expectation.tolerance_mm} mm, "
            f"expected {expectation.count}"
        ),
    }


def _evidence(target: Path) -> ArtifactEvidence:
    """A written file is only evidence once it has been read back off the disk."""
    stat = target.stat()
    return ArtifactEvidence(
        path=str(target),
        exists=True,
        size_bytes=stat.st_size,
        modified_utc=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
    )


def _markdown(title: str, info: Any, result: ReviewValidateResult) -> str:
    lines = [
        f"# {title}",
        "",
        f"- generated: {datetime.now(UTC).isoformat()}",
        f"- outcome: **{result.outcome.upper()}**",
        f"- findings: {result.passed} passed, {result.warned} warned, {result.blocked} blocked",
        "",
        "## Findings",
        "",
        "| Check | Outcome | Detail | Source |",
        "|---|---|---|---|",
    ]
    for finding in result.findings:
        detail = finding.detail.replace("|", "\\|")
        source = finding.source.replace("|", "\\|")
        lines.append(
            f"| `{finding.name}` | {finding.outcome} | {detail} | {source} |"
        )
    lines += [
        "",
        "Each finding names what was read to produce it, so any line here can be",
        "re-derived rather than taken on trust.",
        "",
    ]
    return "\n".join(lines)


@op(
    name="sw_review_report",
    tier="core",
    domains=("review",),
    tags=("review", "report", "markdown", "json"),
    summary=(
        "Run a policy review and write it as both machine-readable JSON and a "
        "human-readable Markdown table, each finding attributed to what it read."
    ),
    safety=NonModelSideEffect(
        destructive=False,
        rationale=(
            "Writes two report files under an allowed output root. The model is only "
            "read; nothing in the document changes."
        ),
    ),
    partially_satisfies=("REV-005",),
    precondition="any",
    idempotent=False,
    timeout_s=600.0,
)
def review_report(ctx: OpContext, args: ReviewReportArgs) -> ReviewReportResult:
    """REV-005: both formats, always.

    The requirement asks for structured JSON *and* a human-readable report, so both are
    written rather than one chosen by extension — a reviewer reads the Markdown and a
    pipeline parses the JSON, and having only the one you did not ask for is useless.
    """
    doc = ctx.require_doc()
    findings = _run_policy(doc, args.policy)
    counts = {"pass": 0, "warn": 0, "block": 0}
    for finding in findings:
        counts[finding.outcome] += 1
    result = ReviewValidateResult(
        outcome=_worst(findings),
        findings=findings,
        blocked=counts["block"],
        warned=counts["warn"],
        passed=counts["pass"],
    )

    checked = Path(assert_output_path(args.output_path, ctx.config.allowed_roots))
    base = checked.with_suffix("")
    markdown_resolved, markdown_action = resolve_output_path(
        base.with_suffix(".md"), args.overwrite
    )
    json_resolved, _ = resolve_output_path(base.with_suffix(".json"), args.overwrite)
    markdown_target, json_target = Path(markdown_resolved), Path(json_resolved)

    info = ctx.session.describe(doc)
    document = info.as_dict() if hasattr(info, "as_dict") else dict(info)
    title = args.title or f"Review — {document.get('title', 'document')}"

    payload = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "document": document,
        "outcome": result.outcome,
        "counts": counts,
        "policy": args.policy.model_dump(),
        "findings": [finding.model_dump() for finding in result.findings],
    }

    try:
        markdown_target.parent.mkdir(parents=True, exist_ok=True)
        markdown_target.write_text(_markdown(title, info, result), encoding="utf-8")
        json_target.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        raise SwMcpError(
            make_error(
                "REPORT_NOT_WRITTEN",
                "filesystem",
                f"Could not write the review report: {exc}",
                remediation=["Check the output root is writable."],
            )
        ) from exc

    return ReviewReportResult(
        markdown_path=str(markdown_target),
        json_path=str(json_target),
        outcome=result.outcome,
        finding_count=len(result.findings),
        blocked=counts["block"],
        warned=counts["warn"],
        artifacts=[_evidence(markdown_target), _evidence(json_target)],
        warnings=(
            [f"The Markdown report was written as {markdown_action}."]
            if markdown_action != "create"
            else []
        ),
    )
