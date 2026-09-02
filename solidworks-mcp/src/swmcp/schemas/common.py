"""Shared argument pieces (SAFE-001).

Every argument model is strict: unknown keys are a validation error, not a silently
ignored typo. ``extra="forbid"`` is asserted for the whole catalog by
``tests/test_catalog_integrity.py``, so a new operation cannot opt out by accident.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from swmcp.safety.overwrite import OverwritePolicy


class StrictModel(BaseModel):
    """Base for every args and result model."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class DocTarget(StrictModel):
    """Which document an operation acts on.

    With neither field set the active document is used. Naming both is refused rather
    than silently preferring one.
    """

    path: str | None = Field(
        default=None,
        description="Full path of an already-open document. Takes precedence over title.",
    )
    title: str | None = Field(
        default=None,
        description="Window title of an open document. Refused if more than one matches.",
    )

    def is_explicit(self) -> bool:
        return bool(self.path or self.title)


class BaseArgs(StrictModel):
    """Args for an operation that acts on a document."""

    document: DocTarget = Field(
        default_factory=DocTarget,
        description="Which document to act on. Defaults to the active document.",
    )


#: A confirmation field that the JSON schema itself advertises as mandatory.
#: Typing it as ``Literal[True]`` means the requirement is visible to the caller
#: before the call, not only in the rejection afterwards.
ConfirmField = Annotated[
    Literal[True],
    Field(
        description=(
            "Must be true. This operation is destructive: it can discard model state "
            "or overwrite a file."
        )
    ),
]


class ConfirmArgs(BaseArgs):
    """Args for a destructive operation."""

    confirm: ConfirmField


class PreflightMixin(StrictModel):
    """SAFE-007: validate and report the plan without mutating anything."""

    preflight: bool = Field(
        default=False,
        description=(
            "Validate inputs and report what would happen, without changing the model."
        ),
    )


class OutputPathArgs(StrictModel):
    """Args for an operation that writes a file."""

    output_path: str = Field(
        description="Destination path. Must resolve under an allowed output root.",
        min_length=1,
    )
    overwrite: OverwritePolicy = Field(
        default="version",
        description=(
            "'version' writes name_vNNN when the target exists (default), "
            "'forbid' refuses and proposes a free name, 'allow' replaces the file."
        ),
    )


#: Argument field names carrying a path to an *existing or open* document. These are
#: normalized but not root-checked: a document the user opened by hand outside the
#: allowed roots is still legitimately addressable.
DOCUMENT_PATH_FIELDS: frozenset[str] = frozenset(
    {
        "path",
        "part_path",
        "assembly_path",
        "model_path",
        "component_path",
        "source_path",
        # Read, never written, and authored by the caller the same way a document is -
        # so it is normalized like one rather than root-checked like an output.
        "entities_file",
    }
)

#: Argument field names naming a file the server is about to create or overwrite.
#: These are hard-refused outside the allowed roots.
OUTPUT_PATH_FIELDS: frozenset[str] = frozenset(
    {"output_path", "output_dir", "preview_path", "export_path", "target_path", "manifest_path"}
)
