"""A bounding box that bounds the surfaces is not one that bounds the material.

``IBody2::GetBodyBox`` is what ``sw_measure`` has always reported, and on anything
spline-shaped it reads large: it bounds the underlying surface definition rather than
the trimmed body. Measured on 2026 (34.3.0) with a spline profile whose apex was
specified at exactly y=10mm:

    GetBodyBox      y max = 10.843455 mm
    GetExtremePoint y max = 10.000000 mm

0.84mm of material that is not there. The same call is exact on analytic geometry - a
cylinder r=10 and a 10x5x20 box both agreed to the micron - which is why this cannot
be corrected by a blanket fudge and has to be measured per body.

That is the same fault that reported a helical gear as 47.48mm across a 46.57mm OD.
Nearly a millimetre of phantom size misleads a clearance check in the dangerous
direction, so the reading now names itself.
"""

from __future__ import annotations

import pytest

from swmcp.handlers.feature import _aggregate_bodies, tight_body_box

MM = 0.001

#: The six GetExtremePoint answers for the spline body above, in metres, exactly as
#: pywin32 returns them: the method's own success flag, then the point.
SPLINE_EXTREMES = {
    (1.0, 0.0, 0.0): (True, 0.060, 0.0, 0.010),
    (-1.0, 0.0, 0.0): (True, 0.040, 0.0, 0.010),
    (0.0, 1.0, 0.0): (True, 0.050, 0.010, 0.010),
    (0.0, -1.0, 0.0): (True, 0.060, 0.0, 0.010),
    (0.0, 0.0, 1.0): (True, 0.055753689, 0.007315546, 0.010),
    (0.0, 0.0, -1.0): (True, 0.055753689, 0.007315546, 0.0),
}
#: What GetBodyBox said about that same body: 0.843455mm too tall.
SPLINE_FAST_BOX = (0.040, 0.0, 0.0, 0.060, 0.010843455, 0.010)


class FakeBody:
    def __init__(self, fast_box, extremes, *, volume=1e-6) -> None:
        self.Name = "Boss-Extrude1"
        self.GetBodyBox = fast_box
        self._extremes = extremes
        self._volume = volume

    def GetExtremePoint(self, x, y, z):
        found = self._extremes.get((x, y, z))
        if found is None:
            raise AttributeError("no extreme point in that direction")
        return found

    def GetMassProperties(self, _density):
        # Solid layout: centre of mass, area, volume, mass, then inertia.
        return (0.0, 0.0, 0.0, 1e-4, self._volume, self._volume * 1000.0, 0, 0, 0)

    def GetFaces(self):
        return ()

    def GetEdges(self):
        return ()


def spline_body():
    return FakeBody(SPLINE_FAST_BOX, SPLINE_EXTREMES)


# --- the reader ------------------------------------------------------------------


def test_the_tight_box_is_assembled_from_six_directions():
    box = tight_body_box(spline_body())
    assert box == pytest.approx([0.040, 0.0, 0.0, 0.060, 0.010, 0.010])


def test_the_tight_box_catches_the_phantom_height():
    """The number this whole module is about, stated as the difference it makes."""
    tight = tight_body_box(spline_body())
    overstated_mm = (SPLINE_FAST_BOX[4] - tight[4]) * 1000
    assert overstated_mm == pytest.approx(0.843455, abs=1e-6)


def test_a_body_that_will_not_answer_gives_no_tight_box():
    """None means "could not measure", which the caller is told about."""
    assert tight_body_box(FakeBody(SPLINE_FAST_BOX, {})) is None


def test_a_short_return_is_refused_rather_than_indexed():
    """Three values would mean the success flag is absent and every slot shifts by one.

    Reading a 3-tuple as though it were the 4-tuple this build returns would silently
    take the wrong coordinate for every direction, which is worse than no box at all.
    """
    three = dict.fromkeys(SPLINE_EXTREMES, (0.060, 0.0, 0.010))
    assert tight_body_box(FakeBody(SPLINE_FAST_BOX, three)) is None


# --- how the aggregate reports itself ----------------------------------------------


def test_the_default_is_the_cheap_box_and_says_so():
    totals = _aggregate_bodies([spline_body()], 1000.0)
    assert totals["box_method"] == "body_box"
    assert totals["box"] == pytest.approx(list(SPLINE_FAST_BOX))


def test_asking_for_tight_changes_the_box_and_the_label():
    totals = _aggregate_bodies([spline_body()], 1000.0, tight=True)
    assert totals["box_method"] == "extreme_point"
    assert totals["box"][4] == pytest.approx(0.010)
    # The cheap reading is kept so the difference can be reported rather than lost.
    assert totals["fast_box"][4] == pytest.approx(0.010843455)


def test_a_body_that_cannot_be_measured_falls_back_and_is_counted():
    """A box missing a body would be worse than one that is slightly large.

    So the loose reading is used for that body, the count says it happened, and the
    method stays 'body_box' so nothing downstream calls the result exact.
    """
    totals = _aggregate_bodies([FakeBody(SPLINE_FAST_BOX, {})], 1000.0, tight=True)
    assert totals["box_unmeasured_bodies"] == 1
    assert totals["box_method"] == "body_box"
    assert totals["box"] == pytest.approx(list(SPLINE_FAST_BOX))


def test_several_bodies_union_their_tight_boxes():
    far = FakeBody(
        (0.100, 0.0, 0.0, 0.120, 0.005, 0.010),
        {
            (1.0, 0.0, 0.0): (True, 0.120, 0.0, 0.0),
            (-1.0, 0.0, 0.0): (True, 0.100, 0.0, 0.0),
            (0.0, 1.0, 0.0): (True, 0.100, 0.005, 0.0),
            (0.0, -1.0, 0.0): (True, 0.100, 0.0, 0.0),
            (0.0, 0.0, 1.0): (True, 0.100, 0.0, 0.010),
            (0.0, 0.0, -1.0): (True, 0.100, 0.0, 0.0),
        },
    )
    totals = _aggregate_bodies([spline_body(), far], 1000.0, tight=True)
    assert totals["box"] == pytest.approx([0.040, 0.0, 0.0, 0.120, 0.010, 0.010])


def test_analytic_geometry_measures_the_same_either_way():
    """The false-positive guard: tight must not move a box that was already right.

    A 10x5x20 box reported identical readings from both calls on the real session, so
    a difference here would mean the tight path is wrong, not that the fast one was.
    """
    exact = (0.0, 0.0, 0.0, 0.010, 0.005, 0.020)
    cube = FakeBody(
        exact,
        {
            (1.0, 0.0, 0.0): (True, 0.010, 0.005, 0.020),
            (-1.0, 0.0, 0.0): (True, 0.0, 0.005, 0.020),
            (0.0, 1.0, 0.0): (True, 0.010, 0.005, 0.020),
            (0.0, -1.0, 0.0): (True, 0.010, 0.0, 0.020),
            (0.0, 0.0, 1.0): (True, 0.010, 0.005, 0.020),
            (0.0, 0.0, -1.0): (True, 0.010, 0.005, 0.0),
        },
    )
    fast = _aggregate_bodies([cube], 1000.0)
    tight = _aggregate_bodies([cube], 1000.0, tight=True)
    assert tight["box"] == pytest.approx(fast["box"])
