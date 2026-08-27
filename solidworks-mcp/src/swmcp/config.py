"""Process configuration, parsed once from the environment.

Everything tunable is an ``SWMCP_*`` variable so a deployment can tighten policy
without code changes. The important default is that :attr:`SwmcpConfig.allowed_roots`
is **empty when unset**, which makes output path checking fail closed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from swmcp.catalog.spec import TIER_ORDER, Tier

TierSetting = Tier | Literal["all"]


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _number(name: str, default: float, *, minimum: float | None = None) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if minimum is not None and value < minimum:
        return default
    return value


def _tier(name: str, default: TierSetting = "core") -> TierSetting:
    raw = (os.environ.get(name) or "").strip().lower()
    if raw == "all":
        return "all"
    if raw in TIER_ORDER:
        return raw  # type: ignore[return-value]
    return default


def parse_roots(raw: str | None) -> tuple[Path, ...]:
    """Split ``SWMCP_ALLOWED_ROOTS``.

    Semicolon-separated, because a colon separator is unusable next to drive letters.
    Normalization is deferred to :mod:`swmcp.safety.paths` so both share one routine.
    """
    if not raw:
        return ()
    parts = [chunk.strip() for chunk in raw.split(";")]
    return tuple(Path(part) for part in parts if part)


@dataclass(frozen=True, slots=True)
class SwmcpConfig:
    allowed_roots: tuple[Path, ...] = ()
    tool_tier: TierSetting = "core"

    checkpoint_debounce_s: float = 45.0
    checkpoint_keep: int = 50
    checkpoint_dir: Path | None = None
    allow_uncheckpointed: bool = False

    audit_path: Path | None = None

    enable_lowlevel_write: bool = False
    early_binding: bool = False

    call_timeout_s: float = 300.0
    com_lock_timeout_s: float = 120.0
    worker_start_timeout_s: float = 15.0

    retry_attempts: int = 3
    retry_initial_s: float = 0.15
    retry_max_s: float = 2.0

    max_candidates: int = 2000
    max_batch_items: int = 500

    env: dict[str, str] = field(default_factory=dict, compare=False)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> SwmcpConfig:
        source = dict(environ if environ is not None else os.environ)
        previous = dict(os.environ)
        try:
            if environ is not None:
                os.environ.clear()
                os.environ.update(source)
            checkpoint_dir = (source.get("SWMCP_CHECKPOINT_DIR") or "").strip()
            audit_path = (source.get("SWMCP_AUDIT_PATH") or "").strip()
            return cls(
                allowed_roots=parse_roots(source.get("SWMCP_ALLOWED_ROOTS")),
                tool_tier=_tier("SWMCP_TOOL_TIER"),
                checkpoint_debounce_s=_number("SWMCP_CHECKPOINT_DEBOUNCE_SEC", 45.0, minimum=0.0),
                checkpoint_keep=int(_number("SWMCP_CHECKPOINT_KEEP", 50.0, minimum=1.0)),
                checkpoint_dir=Path(checkpoint_dir) if checkpoint_dir else None,
                allow_uncheckpointed=_flag("SWMCP_ALLOW_UNCHECKPOINTED"),
                audit_path=Path(audit_path) if audit_path else None,
                enable_lowlevel_write=_flag("SWMCP_ENABLE_LOWLEVEL_WRITE"),
                early_binding=_flag("SWMCP_EARLY_BINDING"),
                call_timeout_s=_number("SWMCP_CALL_TIMEOUT_S", 300.0, minimum=1.0),
                com_lock_timeout_s=_number("SWMCP_COM_LOCK_TIMEOUT_S", 120.0, minimum=1.0),
                worker_start_timeout_s=_number("SWMCP_WORKER_START_TIMEOUT_S", 15.0, minimum=1.0),
                retry_attempts=int(_number("SWMCP_RETRY_ATTEMPTS", 3.0, minimum=1.0)),
                retry_initial_s=_number("SWMCP_RETRY_INITIAL_S", 0.15, minimum=0.0),
                retry_max_s=_number("SWMCP_RETRY_MAX_S", 2.0, minimum=0.0),
                max_candidates=int(_number("SWMCP_MAX_CANDIDATES", 2000.0, minimum=1.0)),
                max_batch_items=int(_number("SWMCP_MAX_BATCH_ITEMS", 500.0, minimum=1.0)),
                env={k: v for k, v in source.items() if k.startswith("SWMCP_")},
            )
        finally:
            if environ is not None:
                os.environ.clear()
                os.environ.update(previous)


_CONFIG: SwmcpConfig | None = None


def get_config() -> SwmcpConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = SwmcpConfig.from_env()
    return _CONFIG


def set_config(config: SwmcpConfig | None) -> None:
    """Override the process config (tests, and the CLI before the server starts)."""
    global _CONFIG
    _CONFIG = config
