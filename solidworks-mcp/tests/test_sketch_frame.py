"""Where a sketch's own axes point in model space.

Every array in this file was read off SOLIDWORKS 2026 (34.3.0), not constructed to
suit the code. That matters because ``ISketch::ModelToSketchTransform`` is named for
the direction it does not conveniently give you, and its ``ArrayData`` is sixteen bare
doubles with no documented layout - so the formula

    model = R . (sketch - t)

is a measurement, and these are the measurements. The Top-plane and offset-from-Top
cases are the load-bearing ones: the first proves the rotation is applied as
sketch-to-model despite the property's name, and the second is the only case with a
non-identity rotation and a non-zero translation at once.

Provenance: a rectangle (0,0)->(10,-20) drawn on each plane and extruded 5mm, with the
resulting body's measured bounding box quoted beside each expectation.
"""

from __future__ import annotations

import pytest

from swmcp.sketching import sketch_frame

#: ArrayData as read from a sketch on each plane. Slots: 0-8 row-major rotation,
#: 9-11 translation (metres), 12 scale, 13-15 unused.
FRONT = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
TOP = [1, 0, 0, 0, 0, 1, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0]
RIGHT = [-0.0, 0, 1, -0.0, 1, 0, -1, 0, 0, 0, 0, 0, 1, 0, 0, 0]
OFFSET_FROM_FRONT = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, -0.025, 1, 0, 0, 0]
OFFSET_FROM_TOP = [1, 0, 0, 0, 0, 1, 0, -1, 0, 0, 0, -0.030, 1, 0, 0, 0]


class FakeSketch:
    def __init__(self, array) -> None:
        self.ModelToSketchTransform = _Transform(array)


class _Transform:
    def __init__(self, array) -> None:
        self.ArrayData = tuple(array)


def frame(array):
    return sketch_frame(FakeSketch(array))


# --- the standard planes ---------------------------------------------------------


def test_front_is_the_xy_plane():
    found = frame(FRONT)
    assert found["x_axis"] == [1, 0, 0]
    assert found["y_axis"] == [0, 1, 0]
    assert found["normal"] == [0, 0, 1]
    assert found["origin_mm"] == [0, 0, 0]
    assert found["maps"] == (
        "sketch +X -> model +X, sketch +Y -> model +Y, normal -> model +Z"
    )


def test_top_sends_sketch_y_to_negative_z():
    """The reading that had to be guessed and then confirmed from a swept body.

    Measured: a rectangle (0,0)->(10,-20) on Top, extruded 5mm, produced a body box of
    [0,0,0]->[10,5,20]. Sketch -Y became model +Z, so sketch +Y is model -Z.
    """
    found = frame(TOP)
    assert found["x_axis"] == [1, 0, 0]
    assert found["y_axis"] == [0, 0, -1]
    assert found["normal"] == [0, 1, 0]
    assert found["maps"] == (
        "sketch +X -> model +X, sketch +Y -> model -Z, normal -> model +Y"
    )


def test_right_is_the_yz_plane():
    found = frame(RIGHT)
    assert found["x_axis"] == [0, 0, -1]
    assert found["y_axis"] == [0, 1, 0]
    assert found["normal"] == [1, 0, 0]


@pytest.mark.parametrize("array", [FRONT, TOP, RIGHT])
def test_a_plane_through_the_origin_has_its_sketch_origin_there(array):
    assert frame(array)["origin_mm"] == [0, 0, 0]


# --- translation, and the two together --------------------------------------------


def test_an_offset_plane_reports_where_its_origin_actually_sits():
    """Front offset 25mm. The stored translation is NEGATIVE 0.025.

    Reading the slot as the answer would put the sketch at -25mm, on the wrong side of
    the model. Measured: the extruded body sat at z 25..30.
    """
    found = frame(OFFSET_FROM_FRONT)
    assert found["origin_mm"] == [0, 0, 25]
    assert found["normal"] == [0, 0, 1]


def test_rotation_and_translation_compose():
    """The case that could have falsified the formula: R != I and t != 0 together.

    A plane 30mm from Top. Measured body box [0,30,0]->[10,35,20] for a rectangle
    (0,0)->(10,-20) extruded 5mm, so the sketch origin is at model (0,30,0) and the
    extrude ran along model +Y.
    """
    found = frame(OFFSET_FROM_TOP)
    assert found["origin_mm"] == [0, 30, 0]
    assert found["x_axis"] == [1, 0, 0]
    assert found["y_axis"] == [0, 0, -1]
    assert found["normal"] == [0, 1, 0]


def test_the_four_corners_land_on_the_measured_body_box():
    """The whole formula, checked end to end against a real measurement.

    This is the assertion that would catch a transposed matrix, a sign error in the
    translation, or the two cancelling each other out - which is exactly what a case
    with only one of them non-trivial cannot do.
    """
    found = frame(OFFSET_FROM_TOP)
    origin = found["origin_mm"]
    x_axis, y_axis = found["x_axis"], found["y_axis"]

    corners = []
    for sx, sy in ((0, 0), (10, 0), (0, -20), (10, -20)):
        corners.append([
            origin[i] + x_axis[i] * sx + y_axis[i] * sy for i in range(3)
        ])

    assert corners == [
        [0, 30, 0],
        [10, 30, 0],
        [0, 30, 20],
        [10, 30, 20],
    ]


# --- refusing rather than guessing -------------------------------------------------


def test_a_transform_that_will_not_answer_is_reported_as_absent():
    """None means "unknown". A frame invented from a short array would be worse."""
    assert sketch_frame(FakeSketch([1, 0, 0])) is None
    assert sketch_frame(FakeSketch([])) is None


def test_a_sketch_with_no_transform_at_all_is_reported_as_absent():
    class Silent:
        pass

    assert sketch_frame(Silent()) is None


def test_an_unaligned_plane_states_the_vector_rather_than_naming_an_axis():
    """A plane at 45 degrees has no axis name, and must not be given a wrong one."""
    half = 2 ** -0.5
    angled = [half, -half, 0, half, half, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    maps = frame(angled)["maps"]
    assert "+X" not in maps.split("normal")[0].replace("sketch +X", "")
    assert "0.707107" in maps
