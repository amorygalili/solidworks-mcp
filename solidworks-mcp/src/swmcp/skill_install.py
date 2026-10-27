"""Install the agent skill that ships inside this package.

The skill is a directory of Markdown — ``SKILL.md``, which an agent reads first, and a
tool index generated from the catalog. The one thing it cannot know from inside the
package is *which Python* has ``swmcp`` installed, and an agent that guesses runs
``python`` and gets whichever interpreter is first on PATH. So installing copies the
directory and pins the interpreter that ran the install into the copy.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from swmcp import __version__

SKILL_SOURCE = Path(__file__).resolve().parent / "skill"
DEFAULT_DEST = Path.home() / ".claude" / "skills" / "solidworks"

LAUNCHER_START = "<!-- swmcp:launcher -->"
LAUNCHER_END = "<!-- /swmcp:launcher -->"

#: How an existing directory is recognised as an earlier install of this skill. Only
#: such a directory is ever replaced; anything else at the destination is left alone.
SKILL_NAME_LINE = "name: solidworks"


class SkillInstallError(Exception):
    """The skill could not be installed where it was asked to go."""


def pin_launcher(text: str, python: str) -> str:
    """Replace the launcher block in ``SKILL.md`` with a concrete interpreter."""
    start = text.find(LAUNCHER_START)
    end = text.find(LAUNCHER_END)
    if start < 0 or end < start:
        raise SkillInstallError("SKILL.md has no launcher block to pin")
    pinned = (
        f"{LAUNCHER_START}\n"
        f"`{python}`\n"
        "\n"
        f"Pinned by `solidworks-mcp install-skill` (swmcp {__version__}). If that path "
        "stops existing, re-run the install from wherever the package now lives.\n"
    )
    return text[:start] + pinned + text[end:]


def install_skill(
    dest: Path | None = None, *, force: bool = False, python: str | None = None
) -> Path:
    """Copy the skill to ``dest`` and pin the interpreter. Returns the directory."""
    target = Path(dest) if dest is not None else DEFAULT_DEST
    interpreter = python or Path(sys.executable).as_posix()

    if target.exists():
        if not force:
            raise SkillInstallError(f"{target} already exists; pass --force to replace it")
        marker = target / "SKILL.md"
        if not (marker.is_file() and SKILL_NAME_LINE in marker.read_text(encoding="utf-8")):
            raise SkillInstallError(
                f"{target} exists but is not an install of this skill, so it was left alone"
            )
        shutil.rmtree(target)

    shutil.copytree(SKILL_SOURCE, target, ignore=shutil.ignore_patterns("__pycache__"))
    skill = target / "SKILL.md"
    skill.write_text(pin_launcher(skill.read_text(encoding="utf-8"), interpreter), encoding="utf-8")
    return target
