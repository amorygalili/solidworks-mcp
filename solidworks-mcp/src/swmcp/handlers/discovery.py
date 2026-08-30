"""Low-level API access (DISC-002/003/004).

An escape hatch is genuinely useful for research and for the long tail of operations
no typed tool covers. It is not a substitute for typed tools, and it is not treated as
coverage — the requirements document is explicit about that.

So the surface here is deliberately narrow:

* the object a call can reach is an allowlisted path, not an arbitrary COM pointer;
* the read invoker only permits members whose names say they read;
* writing is a separate operation behind an environment flag, a confirmation, an
  automatic checkpoint, and an audit entry.
"""

from __future__ import annotations

import re
from typing import Any

from swmcp.catalog.registry import op
from swmcp.catalog.spec import ModelMutation, ReadSafety
from swmcp.com import swconst
from swmcp.com.marshal import get_com_member
from swmcp.context import OpContext
from swmcp.envelope import Check, Verification
from swmcp.errors import SwMcpError, make_error, policy_error, validation_error
from swmcp.modeling import model_snapshot
from swmcp.refs.resolve import resolve
from swmcp.schemas.discovery import (
    ApiBatchInvokeArgs,
    ApiBatchInvokeResult,
    ApiInvokeArgs,
    ApiInvokeResult,
    ApiInvokeWriteArgs,
    ApiInvokeWriteResult,
    ApiSearchArgs,
    ApiSearchResult,
)

#: A read-only member either starts with one of these, or is on the explicit list.
_READ_PREFIXES = ("get", "is", "has", "count", "enum", "list", "find", "probe")

_READ_MEMBERS = frozenset(
    {
        "revisionnumber",
        "activedoc",
        "visible",
        "name",
        "name2",
        "fullname",
        "extension",
        "featuremanager",
        "sketchmanager",
        "selectionmanager",
        "configurationmanager",
        "firstfeature",
        "activesketch",
        "lengthunit",
        "systemvalue",
        "constructiongeometry",
        "drivenstate",
        "relationmanager",
        "planeparams",
        "cylinderparams",
        "coneparams",
    }
)

#: Members that must never be reachable through the read invoker, even though their
#: names look harmless. Selection changes the UI; delete and save change the world.
_ALWAYS_DENIED = re.compile(
    r"^(select|delete|save|close|quit|exit|insert|create|add|set|edit|suppress|replace|run|exec)",
    re.IGNORECASE,
)


def _resolve_target(ctx: OpContext, doc: Any, call: Any) -> Any:
    target = call.target
    if target == "app":
        return ctx.session.app
    if target == "ref":
        if call.ref is None:
            raise SwMcpError(
                validation_error(
                    "MISSING_ARGUMENT", "target='ref' needs a ref to resolve the entity."
                )
            )
        return resolve(ctx.session, doc, call.ref, max_candidates=ctx.config.max_candidates).entity

    obj: Any = doc
    for part in target.split(".")[1:]:
        obj = get_com_member(obj, part, default=None)
        if obj is None:
            raise SwMcpError(
                make_error(
                    "INVOKE_TARGET_UNAVAILABLE",
                    "worker",
                    f"{target!r} is not available on this document.",
                    remediation=["Check the document type supports this manager."],
                )
            )
    return obj


def _assert_readable(member: str) -> None:
    lowered = member.lower()
    if _ALWAYS_DENIED.match(lowered):
        raise SwMcpError(
            policy_error(
                "MEMBER_NOT_READ_ONLY",
                f"{member!r} changes state and is not available through the read invoker.",
                context={"member": member},
                remediation=[
                    "Use the typed operation for this action, which carries a checkpoint, "
                    "a confirmation gate, and read-back verification.",
                    "If no typed operation exists, the gated low-level write operation can "
                    "do it once SWMCP_ENABLE_LOWLEVEL_WRITE is set.",
                ],
            )
        )
    if lowered in _READ_MEMBERS or lowered.startswith(_READ_PREFIXES):
        return
    raise SwMcpError(
        policy_error(
            "MEMBER_NOT_ALLOWLISTED",
            f"{member!r} is not on the read allowlist.",
            context={"member": member, "allowed_prefixes": list(_READ_PREFIXES)},
            remediation=[
                "The read invoker permits members whose names begin with "
                f"{', '.join(_READ_PREFIXES)}, plus a small explicit list.",
            ],
        )
    )


def _describe(value: Any, limit: int = 200) -> tuple[Any, str, bool]:
    """Reduce a COM return value to something JSON-safe and bounded."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value, type(value).__name__, False
    if isinstance(value, (tuple, list)):
        items = list(value)
        truncated = len(items) > limit
        return (
            [_describe(item, limit)[0] for item in items[:limit]],
            "sequence",
            truncated,
        )
    return repr(value)[:limit], "com_object", len(repr(value)) > limit


def _invoke_one(ctx: OpContext, doc: Any, call: Any, *, readonly: bool) -> dict[str, Any]:
    if readonly:
        _assert_readable(call.member)
    target = _resolve_target(ctx, doc, call)
    value = get_com_member(target, call.member, *call.args)
    described, kind, truncated = _describe(value)
    return {
        "target": call.target,
        "member": call.member,
        "value": described,
        "value_type": kind,
        "truncated": truncated,
    }


@op(
    name="sw_api_invoke",
    tier="advanced",
    domains=("discovery",),
    tags=("invoke", "api", "introspect", "escape-hatch"),
    summary=(
        "Read a SOLIDWORKS API member on an allowlisted object. This is a research and "
        "diagnostics tool, not a substitute for the typed operations, and it refuses any "
        "member that would change state."
    ),
    safety=ReadSafety(),
    satisfies=("DISC-003",),
    precondition="any",
    idempotent=True,
    timeout_s=180.0,
)
def api_invoke(ctx: OpContext, args: ApiInvokeArgs) -> ApiInvokeResult:
    doc = ctx.doc
    if doc is None and args.target != "app":
        raise SwMcpError(
            make_error(
                "NO_ACTIVE_DOCUMENT",
                "validation",
                f"target={args.target!r} needs an open document.",
                remediation=["Open a document, or use target='app'."],
            )
        )
    outcome = _invoke_one(ctx, doc, args, readonly=True)
    return ApiInvokeResult(**outcome)


@op(
    name="sw_api_batch_invoke",
    tier="advanced",
    domains=("discovery",),
    tags=("invoke", "api", "batch", "introspect"),
    summary=(
        "Read several SOLIDWORKS API members in one round trip, applying the same "
        "read-only allowlist to each and reporting failures per call."
    ),
    safety=ReadSafety(),
    satisfies=("DISC-003",),
    precondition="any",
    idempotent=True,
    timeout_s=300.0,
)
def api_batch_invoke(ctx: OpContext, args: ApiBatchInvokeArgs) -> ApiBatchInvokeResult:
    doc = ctx.doc
    results: list[dict[str, Any]] = []
    failed = 0

    for index, call in enumerate(args.calls, start=1):
        try:
            outcome = _invoke_one(ctx, doc, call, readonly=True)
            results.append({"index": index, "ok": True, **outcome})
        except SwMcpError as exc:
            failed += 1
            results.append(
                {
                    "index": index,
                    "ok": False,
                    "target": call.target,
                    "member": call.member,
                    "error": exc.envelope.code,
                    "message": exc.envelope.message,
                }
            )
            if args.stop_on_error:
                break
        except Exception as exc:  # one bad call must not lose the batch
            failed += 1
            results.append(
                {
                    "index": index,
                    "ok": False,
                    "target": call.target,
                    "member": call.member,
                    "error": "INVOKE_FAILED",
                    "message": str(exc),
                }
            )
            if args.stop_on_error:
                break

    return ApiBatchInvokeResult(
        results=results,
        failed=failed,
        warnings=[f"{failed} of {len(args.calls)} calls failed."] if failed else [],
    )


@op(
    name="sw_api_invoke_write",
    tier="debug",
    domains=("discovery",),
    tags=("invoke", "api", "write", "unsafe"),
    summary=(
        "Call a state-changing SOLIDWORKS API member directly. Development only: it is "
        "gated behind SWMCP_ENABLE_LOWLEVEL_WRITE, requires confirmation, is "
        "checkpointed and audited, and its effect is not verified beyond a before and "
        "after snapshot."
    ),
    safety=ModelMutation(destructive=True),
    satisfies=("DISC-004",),
    precondition="any",
    idempotent=False,
    timeout_s=300.0,
)
def api_invoke_write(ctx: OpContext, args: ApiInvokeWriteArgs) -> ApiInvokeWriteResult:
    if not ctx.config.enable_lowlevel_write:
        raise SwMcpError(
            policy_error(
                "LOWLEVEL_WRITE_DISABLED",
                "Low-level API writes are disabled.",
                context={"flag": "SWMCP_ENABLE_LOWLEVEL_WRITE"},
                remediation=[
                    "Set SWMCP_ENABLE_LOWLEVEL_WRITE=1 to enable this, and prefer a typed "
                    "operation wherever one exists.",
                ],
            )
        )

    doc = ctx.doc
    before = model_snapshot(doc) if doc is not None else {}
    outcome = _invoke_one(ctx, doc, args, readonly=False)
    after = model_snapshot(doc) if doc is not None else {}

    return ApiInvokeWriteResult(
        target=outcome["target"],
        member=outcome["member"],
        value=outcome["value"],
        verification=Verification(
            read_back=True,
            before=before,
            after=after,
            checks=[
                Check(
                    name="call_returned",
                    passed=True,
                    detail=f"{args.target}.{args.member} returned {outcome['value_type']}",
                ),
                Check(
                    name="model_snapshot_compared",
                    passed=True,
                    detail=(
                        f"bodies {before.get('body_count')} -> {after.get('body_count')}, "
                        f"features {before.get('feature_count')} -> {after.get('feature_count')}"
                    ),
                ),
            ],
        ),
        warnings=[
            "This was a raw API call. Its effect has not been validated beyond the "
            "before and after snapshot; inspect the model before relying on it.",
        ],
    )


@op(
    name="sw_api_search",
    tier="extended",
    domains=("discovery",),
    tags=("api", "search", "constants", "enum"),
    summary=(
        "Search the SOLIDWORKS constants registered on this machine by name, so a caller "
        "can find the enum member a low-level call needs without guessing its value."
    ),
    safety=ReadSafety(),
    satisfies=("DISC-002",),
    precondition="none",
    idempotent=True,
    timeout_s=120.0,
    needs_session=False,
)
def api_search(ctx: OpContext, args: ApiSearchArgs) -> ApiSearchResult:
    query = args.query.lower().strip()
    info = swconst.table_info()

    enums: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []

    for enum_name in swconst.enum_names():
        enum_matches = not query or query in enum_name.lower()
        if enum_matches and args.kind in {"enum", "any"} and len(enums) < args.limit:
            found = swconst.members(enum_name)
            enums.append(
                {
                    "enum": enum_name,
                    "member_count": len(found),
                    "is_bitfield": swconst.is_bitfield(enum_name),
                    "members": dict(list(found.items())[:20]),
                }
            )
        if args.kind in {"member", "any"} and query and len(members) < args.limit:
            for member, value in swconst.members(enum_name).items():
                if query in member.lower():
                    members.append({"enum": enum_name, "member": member, "value": value})
                    if len(members) >= args.limit:
                        break

    warnings = []
    running_major = ctx.session.major if ctx.session.attached else None
    if running_major is not None and running_major != info["typelib_major"]:
        warnings.append(
            f"The constant table came from type library major {info['typelib_major']} but "
            f"the running SOLIDWORKS is major {running_major}. Regenerate the table."
        )

    return ApiSearchResult(
        typelib=info,
        enums=enums,
        members=members,
        warnings=warnings,
    )
