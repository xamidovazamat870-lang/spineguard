import json
from pathlib import Path

from tgf.calibration import Baseline
from tgf.profiles import (
    ProfileBank,
    ProfileContext,
    load_bank,
    save_bank,
    migrate_calibration,
)


def _bl(shoulder=1.0):
    return Baseline(shoulder=shoulder, head=0.0, lean=0.0)


def test_match_within_tolerance():
    bank = ProfileBank()
    ctx = ProfileContext(cx=0.5, scale=0.3, body_yaw_deg=0.0)
    bank.upsert(ctx, _bl())
    close = ProfileContext(cx=0.55, scale=0.31, body_yaw_deg=5.0)
    assert bank.match(close) is not None


def test_no_match_outside_tolerance():
    bank = ProfileBank()
    ctx = ProfileContext(cx=0.5, scale=0.3, body_yaw_deg=0.0)
    bank.upsert(ctx, _bl())
    far = ProfileContext(cx=0.9, scale=0.3, body_yaw_deg=0.0)
    assert bank.match(far) is None


def test_lru_eviction():
    bank = ProfileBank(max_profiles=3)
    for i in range(6):
        bank.upsert(ProfileContext(cx=i * 0.5 + 0.01, scale=0.2), _bl(), now=float(i))
    assert len(bank.profiles) == 3
    # newest 3 (i=3,4,5) should survive
    cxs = sorted(round(p.ctx.cx, 2) for p in bank.profiles)
    assert cxs == sorted(round(i * 0.5 + 0.01, 2) for i in (3, 4, 5))


def test_corrupt_json_gives_empty_bank(tmp_path: Path):
    p = tmp_path / "profiles.json"
    p.write_text("{not json", encoding="utf-8")
    bank = load_bank(p)
    assert bank.profiles == []


def test_save_and_load_roundtrip(tmp_path: Path):
    p = tmp_path / "profiles.json"
    bank = ProfileBank()
    bank.upsert(ProfileContext(cx=0.4, scale=0.25, body_yaw_deg=1.0), _bl(2.0))
    save_bank(bank, p)
    loaded = load_bank(p)
    assert len(loaded.profiles) == 1
    assert loaded.profiles[0].baseline.shoulder == 2.0
    assert json.loads(p.read_text())["profiles"][0]["ctx"]["cx"] == 0.4


def test_migration_from_calibration_json(tmp_path: Path):
    from tgf.calibration import save_baseline
    calib_path = tmp_path / "calibration.json"
    save_baseline(_bl(3.0), calib_path)
    migrated = migrate_calibration(calib_path)
    assert migrated is not None
    assert migrated.shoulder == 3.0


def test_upsert_updates_existing_profile_in_place():
    bank = ProfileBank()
    ctx = ProfileContext(cx=0.5, scale=0.3)
    bank.upsert(ctx, _bl(1.0))
    bank.upsert(ProfileContext(cx=0.51, scale=0.3), _bl(9.0))
    assert len(bank.profiles) == 1
    assert bank.profiles[0].baseline.shoulder == 9.0
