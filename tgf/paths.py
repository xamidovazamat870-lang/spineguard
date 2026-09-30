"""Per-channel data locations (stable vs dev never share state)."""
from __future__ import annotations

import os
from pathlib import Path


def channel() -> str:
    return "dev" if os.environ.get("TGF_CHANNEL", "").strip().lower() == "dev" else "stable"


def home_dir() -> Path:
    """TGF_HOME wins; else ~/.tgf (stable) or ~/.tgf-dev (dev)."""
    override = os.environ.get("TGF_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / (".tgf-dev" if channel() == "dev" else ".tgf")


def default_config_path() -> Path:
    return home_dir() / "config.json"


def baseline_path_for(config_path: str | Path) -> Path:
    """Baseline lives next to the config file in use."""
    return Path(config_path).expanduser().with_name("calibration.json")
