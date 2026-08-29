"""Live cover for sweep (FEAT-004) and loft (FEAT-005).

Written to the cost policy in ``CLAUDE.md``: the document is **module-scoped**, so the
~6s that ``sw_doc_new`` and ``sw_doc_close`` cost is paid once for the whole file rather
than once per test. Each test still builds its own sketches, and asserts on the volume
*delta* the result already reports, so tests can share a document without caring what
earlier ones left in it.

The sweep numbers are exact — a circle swept along a straight line is a cylinder, and
the probe matched pi*r^2*L to 13 significant figures. The loft numbers deliberately are
not: SOLIDWORKS lofts a B-spline surface through the sections, so a loft between two
circles is *not* an exact frustum and measured 0.0036% under the closed form. Those
assertions use a relative tolerance, and saying so here is the point — a later reader
loosening an exact assertion without knowing why would be guessing.
"""

from __future__ import annotations

import math

import pytest

pytestmark = [pytest.mark.live, pytest.mark.slow]

PROFILE_R = 5.0
PATH_LEN = 50.0
CYLINDER_MM3 = math.pi * PROFILE_R**2 * PATH_LEN

LOFT_LOWER_R, LOFT_UPPER_R, LOFT_GAP = 10.0, 5.0, 50.0
FRUSTUM_MM3 = (math.pi * LOFT_GAP / 3.0) * (
    LOFT_LOWER_R**2 + LOFT_LOWER_R * LOFT_UPPER_R + LOFT_UPPER_R**2
)


@pytest.fixture(scope="module")
def shared_part(dispatcher, scratch_root):
    """One document for the whole module. See the cost policy in CLAUDE.md.

    Scoped to the module rather than the function on purpose: a per-test document costs
    ~6s in create and close alone, which for this file would be most of its runtime.
    """
    target = scratch_root / "swmcp_sweep_loft.SLDPRT"
    for stale in scratch_root.glob("swmcp_sweep_loft*.SLDPRT"):
        stale.unlink(missing_ok=True)

    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    assert made.get("ok"), made.get("error")
    dispatcher.call("sw_doc_save", {"output_path": str(target)})
    title = target.name
    yield title

    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": title}, "save_first": "discard", "confirm": True},
    )


@pytest.fixture
def call(call, shared_part):
    """Every call in this module is addressed at the shared document, never 'active'."""

    def _call(name: str, arguments: dict | None = None, *, expect_ok: bool = True) -> dict:
        args = dict(arguments or {})
        args.setdefault("document", {"title": shared_part})
        return call(name, args, expect_ok=expect_ok)

    return _call


@pytest.fixture
def isolated_call(dispatcher, scratch_root, unique_name):
    """A private document, for the one test that will not run in the shared one.

    Module scope is the default here because it is roughly four times faster, but it
    couples tests through one document, and this test is where that bit. Its middle
    profile - a small circle on an offset plane - reproducibly fails to be created once
    the shared document has the whole module's history in it, and *only* then.

    Ruled out by probing, each in its own document: the radius, the plane offset, the
    centre, whether a solid body exists, coincident planes, the exact preceding loft
    sequence, and residue from the deliberately-failed sweep above. All of them create
    the circle happily. The cause is still open; ``sw_sketch_add_geometry`` reports the
    failure honestly rather than silently succeeding, so this is a test-isolation
    problem rather than a tool that lies. Isolating it here is deliberate and narrow -
    not a way of making a red test green.
    """
    target = scratch_root / f"{unique_name}.SLDPRT"
    for stale in scratch_root.glob(f"{unique_name}*.SLDPRT"):
        stale.unlink(missing_ok=True)

    made = dispatcher.call("sw_doc_new", {"doc_type": "part"})
    assert made.get("ok"), made.get("error")
    dispatcher.call("sw_doc_save", {"output_path": str(target)})
    title = target.name

    def _call(name: str, arguments: dict | None = None, *, expect_ok: bool = True) -> dict:
        args = dict(arguments or {})
        args.setdefault("document", {"title": title})
        payload = dispatcher.call(name, args)
        if expect_ok and not payload.get("ok"):
            error = payload["error"]
            raise AssertionError(f"{name} failed: [{error['code']}] {error['message']}")
        return payload

    yield _call

    dispatcher.call(
        "sw_doc_close",
        {"document": {"title": title}, "save_first": "discard", "confirm": True},
    )


def _sketch(call, on: dict, entities: list[dict]) -> str:
    """Create a sketch and prove it survived.

    SOLIDWORKS discards a sketch that ends up empty, but the name counter has already
    advanced by then - so the next feature that references the name fails with "could
    not select", far from the cause. Checking here turns that into an immediate,
    specific failure.
    """
    started = call("sw_sketch_start", {"on": on})["result"]
    added = call("sw_sketch_add_geometry", {"entities": entities})["result"]
    call("sw_sketch_exit")
    name = started["sketch_name"]

    present = {item["name"] for item in call("sw_sketch_list")["result"]["sketches"]}
    assert name in present, (
        f"{name} was created on {on} but is not in the tree afterwards. "
        f"sw_sketch_add_geometry reported {added}. "
        f"An empty sketch is discarded by SOLIDWORKS while the name counter still moves on."
    )
    return name


def _circle(call, on: dict, radius: float, centre=(0.0, 0.0)) -> str:
    return _sketch(call, on, [{"type": "circle", "center": list(centre), "radius": radius}])


def _line(call, on: dict, start, end) -> str:
    return _sketch(call, on, [{"type": "line", "start": list(start), "end": list(end)}])


def _delta(result: dict) -> float:
    return result["volume_mm3_after"] - result["volume_mm3_before"]


# --- sweep (FEAT-004) ---------------------------------------------------------


def test_a_sweep_measures_exactly_what_the_cylinder_should(call):
    """A circle swept along a straight line is a cylinder, so arithmetic knows the answer."""
    profile = _circle(call, {"standard_plane": "front"}, PROFILE_R)
    path = _line(call, {"standard_plane": "top"}, (0, 0), (0, PATH_LEN))

    swept = call(
        "sw_feature_sweep",
        {"profile_sketch": profile, "path_sketch": path, "name": "Rod"},
    )["result"]

    assert swept["feature_name"] == "Rod"
    assert swept["mode"] == "boss"
    assert swept["guide_curve_count"] == 0
    assert _delta(swept) == pytest.approx(CYLINDER_MM3, rel=1e-9)
    assert all(check["passed"] for check in swept["verification"]["checks"])
    assert swept["reference"]["tool_args"]["ref"], "the feature must come back addressable"


def test_a_thin_sweep_makes_a_tube_not_a_rod(call):
    """A 1 mm wall turns the same profile into an annulus: pi*((R+t)^2-R^2)*L."""
    thickness = 1.0
    profile = _circle(call, {"standard_plane": "front"}, PROFILE_R, centre=(40, 0))
    path = _line(call, {"standard_plane": "top"}, (40, 0), (40, PATH_LEN))

    swept = call(
        "sw_feature_sweep",
        {
            "profile_sketch": profile,
            "path_sketch": path,
            "thin_thickness": thickness,
            "name": "Tube",
        },
    )["result"]

    # Outward is SOLIDWORKS' own default and was measured, not assumed: the wall lands
    # between r=5 and r=6, not between r=4 and r=5.
    outer = math.pi * ((PROFILE_R + thickness) ** 2 - PROFILE_R**2) * PATH_LEN
    assert _delta(swept) == pytest.approx(outer, rel=1e-6)
    assert _delta(swept) < CYLINDER_MM3, "a tube must hold less than the solid rod"


def test_an_inward_thin_sweep_keeps_the_profile_as_the_outer_wall(call):
    """The other direction, so the mapping is pinned rather than half-tested."""
    thickness = 1.0
    profile = _circle(call, {"standard_plane": "front"}, PROFILE_R, centre=(60, 0))
    path = _line(call, {"standard_plane": "top"}, (60, 0), (60, PATH_LEN))

    swept = call(
        "sw_feature_sweep",
        {
            "profile_sketch": profile,
            "path_sketch": path,
            "thin_thickness": thickness,
            "thin_direction": "inward",
            "name": "InnerTube",
        },
    )["result"]

    inner = math.pi * (PROFILE_R**2 - (PROFILE_R - thickness) ** 2) * PATH_LEN
    assert _delta(swept) == pytest.approx(inner, rel=1e-6)


def test_a_sweep_cut_removes_the_volume_it_swept(call):
    """The cut path runs through a block, so the material removed is the same cylinder."""
    call("sw_sketch_start", {"on": {"standard_plane": "front"}})
    call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [80, -15], "opposite": [110, 15]}]},
    )
    call("sw_sketch_exit")
    # Mid-plane, so the block straddles the profile plane and the cut reaches material
    # whichever way the path runs. A one-sided block makes this test a direction guess.
    call(
        "sw_feature_extrude_boss",
        {"depth": 80, "end_condition": "mid_plane", "name": "CutBlock"},
    )

    profile = _circle(call, {"standard_plane": "front"}, 4.0, centre=(95, 0))
    path = _line(call, {"standard_plane": "top"}, (95, 0), (95, 40))

    cut = call(
        "sw_feature_sweep",
        {"profile_sketch": profile, "path_sketch": path, "mode": "cut", "name": "Bore"},
    )["result"]

    assert cut["mode"] == "cut"
    assert _delta(cut) == pytest.approx(-math.pi * 16.0 * 40.0, rel=1e-6)
    assert all(check["passed"] for check in cut["verification"]["checks"])


def test_an_open_profile_is_refused_for_a_boss_sweep(call):
    """A boss sweep needs a closed profile; SOLIDWORKS refuses an open one."""
    profile = _line(call, {"standard_plane": "front"}, (200, 0), (210, 0))
    path = _line(call, {"standard_plane": "top"}, (200, 0), (200, 20))

    payload = call(
        "sw_feature_sweep",
        {"profile_sketch": profile, "path_sketch": path},
        expect_ok=False,
    )

    assert not payload["ok"]
    assert payload["error"]["code"] == "SWEEP_FAILED"
    assert any("closed profile" in step for step in payload["error"]["remediation"])


def test_a_sketch_that_does_not_exist_is_named_in_the_error(call):
    payload = call(
        "sw_feature_sweep",
        {"profile_sketch": "NoSuchSketch", "path_sketch": "AlsoMissing"},
        expect_ok=False,
    )

    assert payload["error"]["code"] == "SKETCH_NOT_SELECTABLE"
    assert payload["error"]["context"]["missing"] == ["NoSuchSketch"]
    assert payload["error"]["context"]["role"] == "profile"


def test_a_sweep_without_a_path_is_a_schema_error(call):
    payload = call("sw_feature_sweep", {"profile_sketch": "Anything"}, expect_ok=False)
    assert payload["error"]["category"] == "validation"


# --- loft (FEAT-005) ----------------------------------------------------------


def test_a_loft_between_two_circles_approximates_the_frustum(call):
    """Deliberately a relative tolerance: the loft is a B-spline, not an exact cone.

    The probe measured 0.0036% under the closed form. Asserting equality here would be
    asserting something untrue, and loosening it later without this note would look
    like covering up a regression.
    """
    lower = _circle(call, {"standard_plane": "front"}, LOFT_LOWER_R, centre=(-60, 0))
    call(
        "sw_datum_plane_create",
        {"method": "offset", "standard_plane": "front", "distance": LOFT_GAP, "name": "LoftTop"},
    )
    upper = _circle(call, {"plane_name": "LoftTop"}, LOFT_UPPER_R, centre=(-60, 0))

    lofted = call(
        "sw_feature_loft",
        {"profile_sketches": [lower, upper], "name": "Cone"},
    )["result"]

    assert lofted["feature_name"] == "Cone"
    assert lofted["profile_sketches"] == [lower, upper]
    assert _delta(lofted) == pytest.approx(FRUSTUM_MM3, rel=1e-3)
    assert _delta(lofted) != pytest.approx(FRUSTUM_MM3, rel=1e-12), (
        "if this ever becomes exact, the surface model changed and the note above is stale"
    )
    assert all(check["passed"] for check in lofted["verification"]["checks"])


def test_a_loft_runs_through_every_profile_it_was_given(isolated_call):
    """Three sections, so the middle one has to actually participate.

    Uses its own document - see the ``isolated_call`` fixture for why, and for what was
    ruled out first.
    """
    call = isolated_call
    bottom = _circle(call, {"standard_plane": "front"}, 8.0, centre=(-120, 0))
    for name, distance in (("WaistMid", 25.0), ("WaistTop", 50.0)):
        call(
            "sw_datum_plane_create",
            {
                "method": "offset",
                "standard_plane": "front",
                "distance": distance,
                "name": name,
            },
        )
    middle = _circle(call, {"plane_name": "WaistMid"}, 2.0, centre=(-120, 0))
    top = _circle(call, {"plane_name": "WaistTop"}, 8.0, centre=(-120, 0))

    # SOLIDWORKS silently discards a sketch that ends up empty, and the loft would then
    # fail with "could not select" - which reads like a handler bug rather than a
    # missing sketch. Check the tree first so a failure here names the real cause.
    present = {s["name"] for s in call("sw_sketch_list")["result"]["sketches"]}
    assert {bottom, middle, top} <= present, (
        f"a profile sketch is missing from the tree before lofting: "
        f"wanted {[bottom, middle, top]}, tree has {sorted(present)}"
    )

    lofted = call(
        "sw_feature_loft",
        {"profile_sketches": [bottom, middle, top], "name": "Waisted"},
    )["result"]

    assert lofted["profile_sketches"] == [bottom, middle, top]
    # A straight 8->8 tube would be pi*64*50; the 2 mm waist must pull it well under.
    straight_tube = math.pi * 64.0 * 50.0
    assert 0 < _delta(lofted) < straight_tube * 0.6, "the middle profile was ignored"


def test_a_loft_needs_at_least_two_profiles(call):
    payload = call("sw_feature_loft", {"profile_sketches": ["OnlyOne"]}, expect_ok=False)
    assert payload["error"]["category"] == "validation"


def test_a_loft_naming_a_missing_profile_says_which_one(call):
    payload = call(
        "sw_feature_loft",
        {"profile_sketches": ["Ghost1", "Ghost2"]},
        expect_ok=False,
    )
    assert payload["error"]["code"] == "SKETCH_NOT_SELECTABLE"
    assert payload["error"]["context"]["missing"] == ["Ghost1", "Ghost2"]
