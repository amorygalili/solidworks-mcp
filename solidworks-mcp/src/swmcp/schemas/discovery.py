"""Low-level API access and API search."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from swmcp.envelope import MutationResult, ReadResult
from swmcp.refs.model import EntityRef
from swmcp.schemas.common import BaseArgs, ConfirmField, StrictModel

#: Object paths a caller may address. Anything else is refused, so an invoke cannot
#: wander to an arbitrary COM object.
InvokeTarget = Literal[
    "app",
    "doc",
    "doc.Extension",
    "doc.FeatureManager",
    "doc.SketchManager",
    "doc.SelectionManager",
    "doc.ConfigurationManager",
    "ref",
]


class InvokeCall(StrictModel):
    target: InvokeTarget = "doc"
    ref: EntityRef | None = Field(
        default=None, description="Required when target is 'ref': the entity to call on."
    )
    member: str = Field(min_length=1, max_length=80, description="Member name to read or call.")
    args: list[Any] = Field(
        default_factory=list, max_length=20, description="Arguments, JSON scalars only."
    )


class ApiInvokeArgs(BaseArgs, InvokeCall):
    pass


class ApiInvokeResult(ReadResult):
    target: str
    member: str
    value: Any = None
    value_type: str | None = None
    truncated: bool = False


class ApiBatchInvokeArgs(BaseArgs):
    calls: list[InvokeCall] = Field(min_length=1, max_length=50)
    stop_on_error: bool = Field(
        default=False, description="Abandon the batch at the first failure."
    )


class ApiBatchInvokeResult(ReadResult):
    results: list[dict[str, Any]] = Field(default_factory=list)
    failed: int = 0


class ApiInvokeWriteArgs(BaseArgs, InvokeCall):
    confirm: ConfirmField


class ApiInvokeWriteResult(MutationResult):
    target: str
    member: str
    value: Any = None


class ApiSearchArgs(StrictModel):
    query: str = Field(default="", max_length=120, description="Text matched against names.")
    kind: Literal["enum", "member", "any"] = "any"
    limit: int = Field(default=40, ge=1, le=200)


class ApiSearchResult(ReadResult):
    typelib: dict[str, Any] = Field(default_factory=dict)
    enums: list[dict[str, Any]] = Field(default_factory=list)
    members: list[dict[str, Any]] = Field(default_factory=list)
    note: str = (
        "This index is built from the type libraries registered on this machine, so it "
        "matches the installed release. It is not a copy of the online API reference."
    )
