"""SAFE-009: decoded status codes and HRESULTs, with actionable remediation.

These read the constant table generated from the installed type library, so they
verify against the real SOLIDWORKS enums rather than against hand-copied numbers.
"""

from __future__ import annotations

import pytest

from swmcp.com import swconst
from swmcp.decode import status as status_decode
from swmcp.decode.hresult import (
    DISP_E_EXCEPTION,
    HRESULT_TABLE,
    decode_hresult,
    format_hresult,
    is_disconnected,
    is_retryable,
    normalize_hresult,
)
from swmcp.decode.status import decode_open, decode_save, decode_status

# --- the constant table -------------------------------------------------------


def test_constant_table_came_from_the_installed_typelib():
    info = swconst.table_info()
    assert info["enum_count"] > 500
    assert info["typelib_major"] >= 20


def test_bitfield_detection_distinguishes_flags_from_sequences():
    assert swconst.is_bitfield("swFileLoadError_e"), "load errors combine as flags"
    assert swconst.is_bitfield("swFileSaveError_e")
    assert not swconst.is_bitfield("swAddMateError_e"), (
        "mate errors are sequential 0..6; bitwise decoding would invent conditions"
    )


def test_a_sequential_enum_never_decodes_into_multiple_names():
    names, unmatched = swconst.decode_flags("swAddMateError_e", 3)
    assert names == ["swAddMateError_IncorrectAlignment"]
    assert unmatched == 0


def test_a_bitfield_decodes_every_set_condition():
    combined = swconst.value("swFileLoadError_e", "swFileNotFoundError") | swconst.value(
        "swFileLoadError_e", "swReadOnlyWarn"
    )
    names, unmatched = swconst.decode_flags("swFileLoadError_e", combined)
    assert set(names) == {"swFileNotFoundError", "swReadOnlyWarn"}
    assert unmatched == 0


def test_an_undocumented_bit_is_reported_not_dropped():
    unknown = 1 << 30
    names, unmatched = swconst.decode_flags("swFileLoadError_e", unknown)
    assert names == []
    assert unmatched == unknown


def test_unknown_enum_is_an_explicit_key_error():
    with pytest.raises(KeyError):
        swconst.members("swNotARealEnum_e")


# --- remediation tables -------------------------------------------------------


def test_every_remediation_key_is_a_real_enum_member():
    """A typo here would silently produce a status with no advice attached."""
    problems = []
    for enum_name, per_member in status_decode._REMEDIATION.items():
        try:
            valid = set(swconst.members(enum_name))
        except KeyError:
            problems.append(f"{enum_name} is not an enum in the installed type library")
            continue
        for member in per_member:
            if member not in valid:
                problems.append(f"{enum_name}.{member} does not exist")
    assert not problems, "remediation table refers to constants that do not exist:\n" + "\n".join(
        problems
    )


def test_every_remediation_enum_name_constant_resolves():
    for enum_name in (
        status_decode.FILE_LOAD_ERROR,
        status_decode.FILE_LOAD_WARNING,
        status_decode.FILE_SAVE_ERROR,
        status_decode.FILE_SAVE_WARNING,
        status_decode.REBUILD_ERROR,
        status_decode.ADD_MATE_ERROR,
        status_decode.PERSIST_STATUS,
    ):
        assert swconst.members(enum_name), f"{enum_name} is empty"


# --- decode_status ------------------------------------------------------------


def test_zero_means_no_error():
    decoded = decode_status("swFileLoadError_e", 0)
    assert decoded.value == 0
    assert decoded.summary == "no error reported"
    assert decoded.remediation == []


def test_a_known_error_carries_its_name_and_advice():
    code = swconst.value("swFileLoadError_e", "swFileNotFoundError")
    decoded = decode_status("swFileLoadError_e", code)
    assert decoded.names == ["swFileNotFoundError"]
    assert any("path exists" in step for step in decoded.remediation)


def test_an_error_without_specific_advice_falls_back_to_the_enum_default():
    code = swconst.value("swFileLoadError_e", "swIdMatchError")
    decoded = decode_status("swFileLoadError_e", code)
    assert decoded.remediation, "every non-zero status must say something actionable"


def test_an_undocumented_value_is_summarised_honestly():
    decoded = decode_status("swFileLoadError_e", 1 << 30)
    assert "unrecognised bits" in decoded.summary or "undocumented" in decoded.summary


def test_open_and_save_decode_both_out_parameters():
    errors, warnings = decode_open(
        swconst.value("swFileLoadError_e", "swFileNotFoundError"),
        swconst.value("swFileLoadWarning_e", "swFileLoadWarning_AlreadyOpen"),
    )
    assert errors.is_error and errors.names == ["swFileNotFoundError"]
    assert not warnings.is_error and warnings.names == ["swFileLoadWarning_AlreadyOpen"]

    save_errors, _ = decode_save(swconst.value("swFileSaveError_e", "swReadOnlySaveError"), 0)
    assert any("read-only" in step for step in save_errors.remediation)


def test_a_missing_enum_degrades_instead_of_raising():
    decoded = decode_status("swNotARealEnum_e", 5)
    assert decoded.unmatched_bits == 5
    assert decoded.remediation


# --- HRESULT ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected_code"),
    [
        (-2147024891, "COM_ACCESS_DENIED"),  # 0x80070005 as a signed int
        (0x800706BA, "COM_RPC_SERVER_UNAVAILABLE"),
        (0x800401E3, "SOLIDWORKS_NOT_RUNNING"),
        (0x80020003, "COM_MEMBER_NOT_FOUND"),
        (0x8001010A, "COM_SERVER_BUSY"),
        (0x80070057, "COM_INVALID_ARG"),
    ],
)
def test_hresults_decode_by_number(raw, expected_code):
    info = decode_hresult(raw)
    assert info is not None
    assert info.code == expected_code


def test_signed_and_unsigned_forms_are_the_same_code():
    assert normalize_hresult(-2147352573) == 0x80020003
    assert decode_hresult(-2147352573) is decode_hresult(0x80020003)


def test_hresult_formatting_is_stable():
    assert format_hresult(0x800706BA) == "0x800706BA"
    assert format_hresult(-2147024891) == "0x80070005"
    assert format_hresult(None) is None


def test_busy_hresults_are_retryable_and_dead_ones_are_not():
    assert is_retryable(0x8001010A)
    assert is_retryable(0x80010001)
    assert not is_retryable(0x80070057)
    assert not is_retryable(None)


def test_disconnected_hresults_are_identified():
    assert is_disconnected(0x800706BA)
    assert is_disconnected(0x80010108)
    assert not is_disconnected(0x8001010A)


def test_busy_remediation_names_the_actual_cause():
    """A modal dialog is the usual reason, and an agent cannot guess that."""
    info = decode_hresult(0x8001010A)
    assert any("dialog" in step for step in info.remediation)


def test_every_hresult_entry_carries_remediation():
    for raw, info in HRESULT_TABLE.items():
        assert info.remediation, f"{format_hresult(raw)} ({info.symbol}) has no next step"
        assert info.code.isupper() or "_" in info.code


def test_disp_e_exception_is_in_the_table_because_it_wraps_real_causes():
    assert decode_hresult(DISP_E_EXCEPTION) is not None
