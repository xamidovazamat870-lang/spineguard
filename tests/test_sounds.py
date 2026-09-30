import pytest

from tgf import sounds


@pytest.fixture
def fake_sounds_dir(tmp_path, monkeypatch):
    d = tmp_path / "Sounds"
    d.mkdir()
    (d / "Tink.aiff").write_bytes(b"x")
    (d / "Glass.aiff").write_bytes(b"x")
    (d / "Funk.wav").write_bytes(b"x")
    (d / "readme.txt").write_bytes(b"x")  # non-sound extension, ignored
    monkeypatch.setattr(sounds, "SYSTEM_DIR", d)
    return d


def test_list_system_sounds_sorted_no_ext(fake_sounds_dir):
    names = sounds.list_system_sounds()
    assert names == ["Funk", "Glass", "Tink"]


def test_list_system_sounds_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "SYSTEM_DIR", tmp_path / "does_not_exist")
    assert sounds.list_system_sounds() == []


def test_resolve_sound_system_name(fake_sounds_dir):
    p = sounds.resolve_sound("Glass")
    assert p == fake_sounds_dir / "Glass.aiff"


def test_resolve_sound_unknown_system_name(fake_sounds_dir):
    assert sounds.resolve_sound("NoSuchSound") is None


def test_resolve_sound_absolute_path(tmp_path):
    f = tmp_path / "custom.wav"
    f.write_bytes(b"x")
    assert sounds.resolve_sound(str(f)) == f


def test_resolve_sound_absolute_path_missing(tmp_path):
    f = tmp_path / "missing.wav"
    assert sounds.resolve_sound(str(f)) is None


def test_resolve_sound_home_relative(tmp_path, monkeypatch):
    home_sounds = tmp_path / "home"
    home_sounds.mkdir()
    f = home_sounds / "mine.m4a"
    f.write_bytes(b"x")
    monkeypatch.setenv("HOME", str(home_sounds))
    assert sounds.resolve_sound("~/mine.m4a") == f


def test_resolve_sound_empty_spec():
    assert sounds.resolve_sound("") is None


def test_resolve_sound_bad_extension_path(tmp_path):
    f = tmp_path / "custom.txt"
    f.write_bytes(b"x")
    assert sounds.resolve_sound(str(f)) is None
