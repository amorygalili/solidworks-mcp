"""The pywin32 marshalling shims, tested against reproduced pathologies.

None of this needs SOLIDWORKS running.
"""

from __future__ import annotations

import pytest

from swmcp.com.classify import classify, hresult_of, raw_hresult, to_envelope
from swmcp.com.marshal import (
    call_with_outparams,
    get_com_member,
    normalize_bytes,
    normalize_sequence,
    try_com_member,
)
from tests.fakes.com import (
    ByRefVariant,
    FakeComError,
    MemberNotFoundDoc,
    MethodModeDoc,
    PropertyModeDoc,
    TupleReturningApp,
    VariantMutatingApp,
    disp_exception,
)

# --- property / method duality ------------------------------------------------


@pytest.mark.parametrize("doc", [PropertyModeDoc(), MethodModeDoc(), MemberNotFoundDoc()])
def test_the_same_call_works_in_every_binding_mode(doc):
    """SOLIDWORKS 2026 late-binds GetTitle as a str; a generated proxy makes it a method."""
    assert get_com_member(doc, "GetTitle") == "bracket.SLDPRT"


def test_property_mode_is_the_confirmed_live_behaviour():
    doc = PropertyModeDoc()
    with pytest.raises(TypeError, match="not callable"):
        doc.GetTitle()  # what a naive call site does
    assert get_com_member(doc, "GetTitle") == "bracket.SLDPRT"


def test_member_not_found_is_classified_by_hresult_not_message():
    """A localized Windows must behave identically."""
    localized = MemberNotFoundDoc(message="\u627e\u4e0d\u5230\u6210\u5458\u3002")
    english = MemberNotFoundDoc(message="Member not found.")
    assert get_com_member(localized, "GetTitle") == get_com_member(english, "GetTitle")


def test_a_real_com_failure_still_propagates():
    class Broken:
        @property
        def GetTitle(self):  # noqa: N802
            def member():
                raise FakeComError(0x800706BA, "RPC server unavailable")

            return member

    with pytest.raises(FakeComError):
        get_com_member(Broken(), "GetTitle")


def test_arguments_force_method_invocation():
    class WithArgs:
        def GetUserPreferenceStringValue(self, preference):  # noqa: N802
            return f"pref-{preference}"

    assert get_com_member(WithArgs(), "GetUserPreferenceStringValue", 8) == "pref-8"


def test_missing_attribute_raises_unless_a_default_is_given():
    doc = PropertyModeDoc()
    with pytest.raises(AttributeError):
        get_com_member(doc, "NotAMember")
    assert get_com_member(doc, "NotAMember", default="fallback") == "fallback"


def test_try_com_member_degrades_instead_of_failing_a_whole_read():
    class Broken:
        @property
        def Density(self):  # noqa: N802
            def member():
                raise FakeComError(0x80004005, "E_FAIL")

            return member

    assert try_com_member(Broken(), "Density", default=None) is None


# --- out-parameters -----------------------------------------------------------


@pytest.mark.parametrize("app_class", [VariantMutatingApp, TupleReturningApp])
def test_out_parameters_work_in_both_binding_modes(app_class):
    app = app_class(document="MODEL", errors=2, warnings=8)
    errors, warnings = ByRefVariant(0), ByRefVariant(0)

    document, out_values = call_with_outparams(
        app.OpenDoc6,
        r"C:\cad\bracket.SLDPRT",
        1,
        0,
        "",
        errors,
        warnings,
        outparams=(errors, warnings),
    )

    assert document == "MODEL"
    assert out_values == [2, 8], "both bindings must report the same errors and warnings"
    assert app.calls == [(r"C:\cad\bracket.SLDPRT", 1, 0, "")]


def test_the_tuple_binding_also_updates_the_variants():
    """So a call site that reads slot.value directly behaves the same either way."""
    app = TupleReturningApp(errors=4, warnings=0)
    errors, warnings = ByRefVariant(0), ByRefVariant(0)
    call_with_outparams(
        app.OpenDoc6, "p", 1, 0, "", errors, warnings, outparams=(errors, warnings)
    )
    assert errors.value == 4
    assert warnings.value == 0


def test_a_plain_return_value_is_not_mistaken_for_outparams():
    def method(_a, out):
        out.value = 7
        return ("this", "is", "the", "answer")

    slot = ByRefVariant(0)
    result, outs = call_with_outparams(method, 1, slot, outparams=(slot,))
    assert result == ("this", "is", "the", "answer")
    assert outs == [7]


# --- SAFEARRAY normalization --------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [b"\x01\x02\xff", bytearray(b"\x01\x02\xff"), (1, 2, 255), [1, 2, 255], memoryview(b"\x01\x02\xff")],
)
def test_persist_reference_blobs_normalize_identically(value):
    """A reference captured under one binding must resolve under the other."""
    assert normalize_bytes(value) == b"\x01\x02\xff"


def test_unnormalizable_blobs_are_none_not_a_crash():
    assert normalize_bytes(None) is None
    assert normalize_bytes("not a blob") is None
    assert normalize_bytes([1, "two"]) is None


def test_sequences_normalize_from_every_com_shape():
    assert normalize_sequence(None) == []
    assert normalize_sequence(("a", "b")) == ["a", "b"]
    assert normalize_sequence("lone") == ["lone"], "a single object is a one-item collection"


# --- classification -----------------------------------------------------------


def test_disp_e_exception_is_unwrapped_to_the_real_cause():
    exc = disp_exception(0x800706BA)
    assert raw_hresult(exc) == 0x80020009
    assert hresult_of(exc) == 0x800706BA, "the wrapper hides the code that matters"

    verdict = classify(exc)
    assert verdict.code == "COM_RPC_SERVER_UNAVAILABLE"
    assert verdict.disconnected
    assert verdict.wrapped_hresult == 0x80020009


def test_busy_is_retryable_and_invalid_arg_is_not():
    assert classify(FakeComError(0x8001010A)).retryable
    assert not classify(FakeComError(0x80070057)).retryable


def test_a_non_com_exception_is_categorised_as_worker():
    verdict = classify(ValueError("plain python failure"))
    assert verdict.category == "worker"
    assert verdict.code == "WORKER_ERROR"
    assert verdict.hresult is None


def test_an_unknown_hresult_is_still_reported_with_its_number():
    verdict = classify(FakeComError(0x80041234))
    assert verdict.code == "COM_ERROR"
    assert verdict.formatted_hresult == "0x80041234"


def test_the_envelope_carries_remediation_and_the_unwrap_note():
    envelope = to_envelope(disp_exception(0x8001010A), com_interface="IModelDoc2.EditRebuild3")
    assert envelope.code == "COM_SERVER_BUSY"
    assert envelope.hresult == "0x8001010A"
    assert envelope.com_interface == "IModelDoc2.EditRebuild3"
    assert any("dialog" in step for step in envelope.remediation)
    assert envelope.context["wrapped_hresult"] == "0x80020009"


def test_solidworks_description_wins_over_the_generic_table_text():
    exc = disp_exception(0x80004005, description="Sketch is not fully defined")
    assert classify(exc).message == "Sketch is not fully defined"
