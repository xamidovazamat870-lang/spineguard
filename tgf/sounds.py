"""Sound spec resolution: system sound name or file path -> playable Path."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

SYSTEM_DIR = Path("/System/Library/Sounds")
_EXTS = (".aiff", ".wav", ".mp3", ".m4a", ".caf")


def list_system_sounds() -> List[str]:
    """Names (no extension) of playable files in SYSTEM_DIR, sorted; [] if missing."""
    try:
        if not SYSTEM_DIR.is_dir():
            return []
        names = {p.stem for p in SYSTEM_DIR.iterdir() if p.suffix.lower() in _EXTS and p.is_file()}
    except OSError:
        return []
    return sorted(names)


def resolve_sound(spec: str) -> Optional[Path]:
    """"Glass" -> system sound path; "~/x.wav" or absolute path -> Path if it exists; else None."""
    spec = (spec or "").strip()
    if not spec:
        return None
    p = Path(spec).expanduser()
    if p.is_absolute() or spec.startswith("~") or "/" in spec:
        try:
            if p.is_file() and p.suffix.lower() in _EXTS:
                return p
        except OSError:
            pass
        return None
    for ext in _EXTS:
        cand = SYSTEM_DIR / f"{spec}{ext}"
        try:
            if cand.is_file():
                return cand
        except OSError:
            continue
    return None
