"""Apply SOLIDWORKS user preferences for the length of one operation, then put them back.

These are application-wide settings that belong to whoever is using SOLIDWORKS, not to
the caller of one tool. Changing them permanently as a side effect would be rude, and
it would also make each operation's behaviour depend on whatever ran before it.

The restore has to be unconditional. A preference left set changes how SOLIDWORKS
behaves for every later action, with nothing on screen to explain it - the same class
of fault as leaving ``AddToDB`` on, which silently changes how every sketch the user
later draws by hand is inferenced.
"""

from __future__ import annotations

import contextlib
from typing import Any

from swmcp.com import swconst
from swmcp.com.marshal import try_com_member


class Preferences:
    """A set of preference changes that knows how to undo itself.

    Each setter records the previous value the *first* time it touches a given
    preference, so applying the same one twice still restores the user's original
    rather than an intermediate.
    """

    def __init__(self, app: Any) -> None:
        self.app = app
        self.integers: dict[int, int] = {}
        self.toggles: dict[int, bool] = {}
        self.applied: dict[str, Any] = {}

    def set_integer(self, name: str, value: int, *, label: str, shown: Any) -> None:
        code = swconst.value("swUserPreferenceIntegerValue_e", name)
        previous = try_com_member(self.app, "GetUserPreferenceIntegerValue", code, default=None)
        if isinstance(previous, int):
            self.integers.setdefault(code, previous)
        try_com_member(self.app, "SetUserPreferenceIntegerValue", code, value, default=None)
        self.applied[label] = shown

    def set_toggle(self, name: str, value: bool, *, label: str, shown: Any) -> None:
        code = swconst.value("swUserPreferenceToggle_e", name)
        previous = try_com_member(self.app, "GetUserPreferenceToggle", code, default=None)
        if previous is not None:
            self.toggles.setdefault(code, bool(previous))
        try_com_member(self.app, "SetUserPreferenceToggle", code, value, default=None)
        self.applied[label] = shown

    def restore(self) -> None:
        for code, previous in self.integers.items():
            with contextlib.suppress(Exception):
                self.app.SetUserPreferenceIntegerValue(code, previous)
        for code, previous in self.toggles.items():
            with contextlib.suppress(Exception):
                self.app.SetUserPreferenceToggle(code, previous)
