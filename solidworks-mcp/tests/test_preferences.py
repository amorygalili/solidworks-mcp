"""Borrowing the user's settings, and giving them back.

These are application-wide SOLIDWORKS settings that belong to whoever is using the
program. An operation that changes one and does not put it back has made a lasting
change on their behalf without asking - and worse, an invisible one: the next thing
they do behaves differently with nothing on screen to explain it. That is the same
class of fault as leaving ``AddToDB`` set, which silently changed how every sketch
drawn afterwards was inferenced.

So the restore is tested here rather than live, because the properties that matter -
that it restores the *original* through repeated sets, and that one failing restore
does not abandon the others - are awkward to provoke against a real session and
trivial to state against a fake one.
"""

from __future__ import annotations

import pytest

from swmcp.com.preferences import Preferences

#: swUserPreferenceToggle_e codes, as resolved on 2026 (34.3.0).
PLANES, AXES, ORIGINS = 5, 4, 6


class FakeApp:
    def __init__(self, toggles=None, integers=None) -> None:
        self.toggles = dict(toggles or {})
        self.integers = dict(integers or {})
        self.refused_toggles: set[int] = set()
        self.writes: list[tuple[str, int, object]] = []

    def GetUserPreferenceToggle(self, code):
        return self.toggles[code]

    def SetUserPreferenceToggle(self, code, value):
        if code in self.refused_toggles:
            raise RuntimeError("SOLIDWORKS refused this preference")
        self.writes.append(("toggle", code, value))
        self.toggles[code] = value
        return True

    def GetUserPreferenceIntegerValue(self, code):
        return self.integers[code]

    def SetUserPreferenceIntegerValue(self, code, value):
        self.writes.append(("integer", code, value))
        self.integers[code] = value
        return True


def test_a_toggle_is_applied_and_then_put_back():
    app = FakeApp(toggles={PLANES: True})
    preferences = Preferences(app)

    preferences.set_toggle("swDisplayPlanes", False, label="planes", shown=False)
    assert app.toggles[PLANES] is False

    preferences.restore()
    assert app.toggles[PLANES] is True


def test_restoring_returns_the_original_not_the_previous_step():
    """Setting the same preference twice must not make the first change permanent.

    The second set reads back the value the first one wrote, so recording it would
    restore to the intermediate - leaving the user's real setting lost.
    """
    app = FakeApp(toggles={PLANES: True})
    preferences = Preferences(app)

    preferences.set_toggle("swDisplayPlanes", False, label="a", shown=False)
    preferences.set_toggle("swDisplayPlanes", False, label="b", shown=False)
    preferences.restore()

    assert app.toggles[PLANES] is True


def test_every_preference_is_restored_even_if_one_refuses():
    """A single stubborn setting must not strand the rest switched off."""
    app = FakeApp(toggles={PLANES: True, AXES: True, ORIGINS: True})
    preferences = Preferences(app)
    for name, code in (("swDisplayPlanes", PLANES), ("swDisplayAxes", AXES),
                       ("swDisplayOrigins", ORIGINS)):
        preferences.set_toggle(name, False, label=name, shown=False)
        assert app.toggles[code] is False

    app.refused_toggles = {AXES}
    preferences.restore()

    assert app.toggles[PLANES] is True
    assert app.toggles[ORIGINS] is True
    assert app.toggles[AXES] is False  # the one that refused, and only that one


def test_restore_is_safe_to_call_when_nothing_was_applied():
    app = FakeApp()
    Preferences(app).restore()
    assert app.writes == []


def test_what_was_applied_is_reported_for_the_result():
    app = FakeApp(toggles={PLANES: True})
    preferences = Preferences(app)
    preferences.set_toggle("swDisplayPlanes", False, label="swDisplayPlanes", shown=False)
    assert preferences.applied == {"swDisplayPlanes": False}


def test_an_unreadable_preference_is_still_written_but_not_restored():
    """If the old value could not be read there is nothing honest to restore it to.

    Guessing a default would be worse than leaving it: a wrong guess is an
    unannounced change to a setting the user chose.
    """
    class Unreadable(FakeApp):
        def GetUserPreferenceToggle(self, code):
            raise RuntimeError("cannot read")

    app = Unreadable(toggles={PLANES: True})
    preferences = Preferences(app)
    preferences.set_toggle("swDisplayPlanes", False, label="planes", shown=False)

    assert app.toggles[PLANES] is False
    preferences.restore()
    assert app.toggles[PLANES] is False


def test_integers_round_trip_the_same_way():
    stl_quality = 78  # swUserPreferenceIntegerValue_e, resolved on this build
    app = FakeApp(integers={stl_quality: 3})
    preferences = Preferences(app)
    preferences.set_integer("swSTLQuality", 1, label="stl_quality", shown="coarse")
    assert app.integers[stl_quality] == 1
    preferences.restore()
    assert app.integers[stl_quality] == 3


def test_an_unknown_preference_name_is_refused_rather_than_guessed():
    """swDisplayDimension reads like a member of this enum and is not one."""
    with pytest.raises(Exception, match="swDisplayDimension"):
        Preferences(FakeApp()).set_toggle(
            "swDisplayDimension", False, label="x", shown=False
        )
