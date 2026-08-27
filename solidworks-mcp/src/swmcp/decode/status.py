"""SAFE-009: decode SOLIDWORKS status codes into names and remediation.

Both sibling Python projects surface ``errors.value`` as a raw integer, which tells a
caller nothing. The names here come from the installed type library via
:mod:`swmcp.com.swconst` — nothing is hardcoded — and this module adds the part the
type library cannot: what to do about it.

Several of these enums are bitfields, so one integer can mean several conditions at
once. ``decode_status`` reports every matched flag plus any bit it could not account
for, rather than picking the first match.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from swmcp.com import swconst

FILE_LOAD_ERROR = "swFileLoadError_e"
FILE_LOAD_WARNING = "swFileLoadWarning_e"
FILE_SAVE_ERROR = "swFileSaveError_e"
FILE_SAVE_WARNING = "swFileSaveWarning_e"
REBUILD_ERROR = "swFeatureError_e"
ADD_MATE_ERROR = "swAddMateError_e"
PERSIST_STATUS = "swPersistReferencedObjectStates_e"


@dataclass(frozen=True, slots=True)
class StatusDecode:
    enum: str
    value: int
    names: list[str] = field(default_factory=list)
    unmatched_bits: int = 0
    remediation: list[str] = field(default_factory=list)
    is_error: bool = True

    @property
    def summary(self) -> str:
        if not self.value:
            return "no error reported"
        described = ", ".join(self.names) if self.names else f"undocumented value {self.value}"
        if self.unmatched_bits:
            described += f" (plus unrecognised bits 0x{self.unmatched_bits:X})"
        return described


# Per-member advice. Anything absent falls back to the enum-level default.
_REMEDIATION: dict[str, dict[str, list[str]]] = {
    FILE_LOAD_ERROR: {
        "swFileNotFoundError": [
            "Check the path exists and is spelled correctly.",
            "A referenced component may have moved; inspect external references.",
        ],
        "swReadOnlyWarn": ["The file opened read-only; saving will fail until that changes."],
        "swSharingViolationWarn": [
            "Another process or user has the file open. Close it there, or open read-only.",
        ],
        "swFutureVersion": [
            "The file was saved by a newer SOLIDWORKS than the one running. "
            "It cannot be opened by this version.",
        ],
        "swFileWithSameTitleAlreadyOpen": [
            "A different file with the same title is already open. Close it, "
            "or address the open document directly instead of opening by path.",
        ],
        "swLiquidMachineDoc": ["The document is managed by a data-management system."],
        "swInvalidFileTypeError": ["The extension does not match a supported document type."],
    },
    FILE_SAVE_ERROR: {
        "swReadOnlySaveError": [
            "The target file is read-only. Clear the attribute or save elsewhere.",
        ],
        "swFileLockError": ["Another process holds a lock on the file."],
        "swFileNameEmpty": ["Provide an explicit output path."],
        "swFileSaveFormatNotAvailable": [
            "The requested export format is not available in this SOLIDWORKS edition "
            "or its translator add-in is not loaded.",
        ],
        "swFileSaveAsBadEDrawingsVersion": ["The eDrawings translator version is incompatible."],
        "swFileSaveAsInvalidFileExtension": ["The extension does not match the chosen format."],
        "swFileSaveAsNoSelection": ["The export needs a selection; select the bodies first."],
        "swGenericSaveError": [
            "Check free disk space, path length, and write permission on the folder.",
        ],
    },
    ADD_MATE_ERROR: {
        "swAddMateError_IncorrectSelections": [
            "The chosen entities cannot form this mate type. "
            "Probe candidate entities before mating.",
        ],
        "swAddMateError_OverDefinedAssembly": [
            "The mate would over-define the assembly. Remove or suppress a conflicting mate.",
        ],
        "swAddMateError_IncorrectAlignment": ["Flip the alignment and retry."],
        "swAddMateError_IncorrectMateType": [
            "This mate type does not accept the selected entity kinds.",
        ],
        "swAddMateError_IncorrectGearRatios": ["Provide a valid non-zero gear ratio."],
    },
    PERSIST_STATUS: {
        "swPersistReferencedObject_Deleted": [
            "The referenced entity no longer exists. Re-probe to capture a fresh reference.",
        ],
        "swPersistReferencedObject_Invalid": [
            "The stored reference is not valid for this document. "
            "Resolution falls back to semantic matching.",
        ],
        "swPersistReferencedObject_Suppressed": [
            "The owning feature is suppressed. Unsuppress it before addressing the entity.",
        ],
    },
}

_DEFAULT_REMEDIATION: dict[str, list[str]] = {
    FILE_LOAD_ERROR: ["Inspect the document's external references and rebuild state."],
    FILE_SAVE_ERROR: ["Check disk space, permissions, and that the file is not open elsewhere."],
    ADD_MATE_ERROR: [
        "Probe the candidate mate entities and check the assembly's degrees of freedom."
    ],
    REBUILD_ERROR: ["Inspect the feature tree for errored or dangling features."],
    PERSIST_STATUS: ["Re-capture the entity reference from a fresh probe."],
}


def decode_status(enum_name: str, raw: int | None, *, is_error: bool = True) -> StatusDecode:
    """Decode one SOLIDWORKS status integer."""
    value = int(raw or 0)
    try:
        names, unmatched = swconst.decode_flags(enum_name, value)
    except (KeyError, FileNotFoundError):
        return StatusDecode(
            enum=enum_name,
            value=value,
            names=[],
            unmatched_bits=value,
            remediation=[f"{enum_name} is not present in the generated constant table."],
            is_error=is_error,
        )

    remediation: list[str] = []
    per_member = _REMEDIATION.get(enum_name, {})
    for name in names:
        for step in per_member.get(name, []):
            if step not in remediation:
                remediation.append(step)
    if value and not remediation:
        remediation = list(_DEFAULT_REMEDIATION.get(enum_name, []))

    return StatusDecode(
        enum=enum_name,
        value=value,
        names=names,
        unmatched_bits=unmatched,
        remediation=remediation,
        is_error=is_error,
    )


def decode_open(errors: int | None, warnings: int | None) -> tuple[StatusDecode, StatusDecode]:
    """Decode the paired out-parameters of ``ISldWorks.OpenDoc6``."""
    return (
        decode_status(FILE_LOAD_ERROR, errors),
        decode_status(FILE_LOAD_WARNING, warnings, is_error=False),
    )


def decode_save(errors: int | None, warnings: int | None) -> tuple[StatusDecode, StatusDecode]:
    """Decode the paired out-parameters of ``IModelDocExtension.SaveAs``."""
    return (
        decode_status(FILE_SAVE_ERROR, errors),
        decode_status(FILE_SAVE_WARNING, warnings, is_error=False),
    )
