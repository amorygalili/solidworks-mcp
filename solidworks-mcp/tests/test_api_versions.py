"""Check every SOLIDWORKS API call in this package against the installed type library.

``FeatureCircularPattern5`` declares fourteen parameters. Calling it with thirteen
raises "Parameter not optional" — a message that names neither the member nor the
count — and that shipped, because no test ever called a circular pattern. The type
library knows the answer, so the answer should be asserted rather than discovered in a
model that quietly came out wrong.

These checks read ``generated/swapi.json``, so they need no running SOLIDWORKS.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from swmcp.com import apiver

SOURCE_ROOT = Path(__file__).resolve().parent.parent / "src" / "swmcp"


@pytest.fixture(scope="module")
def call_sites():
    sites = apiver.scan_source()
    assert sites, "the scanner found no API calls at all, which cannot be right"
    return sites


def test_every_call_passes_a_declared_number_of_arguments(call_sites):
    """The check that would have caught the circular-pattern bug."""
    problems = []
    for site in call_sites:
        allowed = apiver.arities(site.member)
        if site.argument_count not in allowed:
            problems.append(
                f"{site.source}:{site.line} calls {site.member} with "
                f"{site.argument_count} argument(s); the type library declares "
                f"{sorted(allowed)}"
            )
    assert not problems, "argument counts disagree with sldworks.tlb:\n" + "\n".join(problems)


def test_no_call_reaches_a_member_that_does_not_exist():
    """The check that would have caught ``SketchMove``.

    ``ISketchManager`` has no ``SketchMove``, ``SketchRotate``, or ``SketchScale`` — the
    sketch transforms live on ``IModelDoc2`` under different names. Three of the six
    operations ``sw_sketch_modify`` advertises therefore failed with a bare COM error
    until this scan named them. The arity check cannot find this class of bug, because
    it can only measure members the type library knows about.
    """
    unknown = apiver.scan_unknown_members()
    assert not unknown, "these look like SOLIDWORKS calls but are on no interface:\n" + "\n".join(
        f"  {site.source}:{site.line} {site.member}({site.argument_count})" for site in unknown
    )


def test_every_member_called_exists_on_this_release(call_sites):
    """A version-suffixed member that is not installed fails opaquely at runtime."""
    unknown = sorted(
        {site.member for site in call_sites if not apiver.interfaces_declaring(site.member)}
    )
    assert not unknown, f"these members are not in the API table: {unknown}"


def test_out_only_parameters_are_understood(call_sites):
    """Guard the rule that makes the arity check usable rather than noisy.

    ``IFeature::GetErrorCode2(IsWarning)`` has one parameter, and it is pure-out, so a
    zero-argument call is correct. If that distinction were lost the arity check would
    fire on a dozen correct call sites and get switched off.
    """
    assert apiver.arities("GetErrorCode2") == {0, 1}
    assert apiver.arities("GetMaterialPropertyName2") == {1, 2}

    # SaveAs's Errors and Warnings are in/out, so they must still be passed. The union
    # also contains IModelDoc2::SaveAs(Name), which is a different member of the same
    # name — the price of resolving a call without knowing its receiver's interface.
    extension = apiver.members("IModelDocExtension")["SaveAs"]
    assert len(extension["params"]) == 6
    assert extension["flags"][-2:] == [3, 3], "Errors and Warnings are FIN | FOUT"
    assert apiver.arities("SaveAs") == {1, 6}


def test_the_version_report_places_each_call_in_its_family():
    report = apiver.family_report("IFeatureManager", "FeatureLinearPattern4")

    assert report.family == "FeatureLinearPattern"
    assert report.used_version == 4
    assert "FeatureLinearPattern" in report.available, "the unsuffixed member is version 1"
    assert report.newest_version >= report.used_version
    assert report.parameter_count == 20


def test_split_version_treats_an_unsuffixed_member_as_version_one():
    assert apiver.split_version("FeatureExtrusion3") == ("FeatureExtrusion", 3)
    assert apiver.split_version("FeatureExtrusion") == ("FeatureExtrusion", 1)
    assert apiver.split_version("Select2") == ("Select", 2)
    assert apiver.split_version("GetTitle") == ("GetTitle", 1)


def test_the_usage_report_says_where_a_newer_member_exists():
    """DISC-005: being one version behind is reported, never silently corrected."""
    report = apiver.usage_report()

    assert report["table"]["typelib_major"] >= 30
    assert report["families"], "the handlers do call versioned members"
    assert report["warnings"] == [], report["warnings"]
    for entry in report["families"]:
        assert entry["used"] in entry["available"]
        assert entry["is_newest"] == (entry["used"] == entry["newest"])
    assert "never selected" in report["note"], (
        "the report must be explicit that it does not upgrade anything by itself"
    )


def test_the_scanner_ignores_calls_it_cannot_count(tmp_path):
    """A splatted call has no countable arity, so it must be skipped, not guessed."""
    module = tmp_path / "swmcp" / "fake.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "def go(doc, args):\n"
        "    doc.FeatureExtrusion3(*args)\n"
        "    doc.FeatureExtrusion3(1, 2)\n",
        encoding="utf-8",
    )

    found = apiver.scan_source(module.parent)
    assert [site.argument_count for site in found] == [2]


def test_the_scanner_reads_the_duality_shims(tmp_path):
    """Most calls go through try_com_member, so the shim form has to be understood."""
    module = tmp_path / "swmcp" / "fake.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "def go(doc):\n"
        '    try_com_member(doc, "EditRebuild3", default=None)\n'
        '    get_com_member(doc, "GetUserPreferenceToggle", 1)\n',
        encoding="utf-8",
    )

    found = {site.member: site.argument_count for site in apiver.scan_source(module.parent)}
    assert found == {"EditRebuild3": 0, "GetUserPreferenceToggle": 1}


def test_the_api_table_covers_the_interfaces_the_handlers_use():
    """A member on an uncaptured interface is unchecked, so the gap must be visible."""
    names = apiver.interface_names()
    for required in ("IFeatureManager", "ISketchManager", "IModelDoc2", "IModelDocExtension"):
        assert required in names
    assert apiver.table_info()["member_count"] > 1000


def test_no_call_relies_on_the_result_of_a_void_member():
    """A ``void`` member returns nothing; treating that as an answer invents a signal.

    ``IFeatureManager::InsertRib`` is declared void, and reading its ``None`` as
    failure once reported ``RIB_FAILED`` for a rib that had built correctly and added
    1,750 mm³. The argument-count scan cannot see this class of mistake — the call is
    perfectly well formed — so the return type is checked separately.
    """
    from swmcp.com.apiver import scan_void_results

    offenders = scan_void_results()

    assert not offenders, "these keep the result of a call that returns nothing:\n" + "\n".join(
        f"  {site.source}:{site.line} {site.member}()" for site in offenders
    )


def test_the_table_records_return_types_at_all():
    """The check above is worthless if the generated table stopped carrying the flag."""
    from swmcp.com.apiver import members, returns_void

    assert returns_void("InsertRib"), "IFeatureManager::InsertRib is declared void"
    assert not returns_void("Add2"), "IEquationMgr::Add2 returns the new index"
    assert all(
        "returns_void" in entry for entry in members("IFeatureManager").values()
    ), "every member needs the flag, or the scan silently passes everything"
