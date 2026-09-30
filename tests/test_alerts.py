from pathlib import Path
from unittest.mock import patch

from tgf.alerts import Alerter
from tgf.config import Config


def _cfg(**kw) -> Config:
    return Config(cooldown_sec=30.0, **kw)


class _FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


@patch("tgf.alerts.resolve_sound", return_value=Path("/System/Library/Sounds/Tink.aiff"))
@patch("tgf.alerts.subprocess.Popen")
def test_first_fire_calls_afplay(mock_popen, _mock_resolve):
    a = Alerter(_cfg(), clock=_FakeClock(0.0))
    result = a.fire()
    assert result is True
    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert args[0] == "afplay"
    assert "-v" in args


@patch("tgf.alerts.resolve_sound", return_value=Path("/System/Library/Sounds/Tink.aiff"))
@patch("tgf.alerts.subprocess.Popen")
def test_fire_within_cooldown_suppressed(mock_popen, _mock_resolve):
    clock = _FakeClock(0.0)
    a = Alerter(_cfg(), clock=clock)
    assert a.fire() is True
    clock.t = 5.0
    assert a.fire() is False
    assert mock_popen.call_count == 1


@patch("tgf.alerts.resolve_sound", return_value=Path("/System/Library/Sounds/Tink.aiff"))
@patch("tgf.alerts.subprocess.Popen")
def test_fire_after_cooldown_allowed(mock_popen, _mock_resolve):
    clock = _FakeClock(0.0)
    a = Alerter(_cfg(), clock=clock)
    assert a.fire() is True
    clock.t = 31.0
    assert a.fire() is True
    assert mock_popen.call_count == 2


@patch("tgf.alerts.resolve_sound", return_value=None)
@patch("tgf.alerts.subprocess.Popen")
def test_fire_fallback_when_sound_missing(mock_popen, _mock_resolve):
    """Unresolvable sound (and unresolvable Tink fallback) -> osascript notification, no crash."""
    a = Alerter(_cfg(), clock=_FakeClock(0.0))
    result = a.fire()
    assert result is True
    mock_popen.assert_called_once()
    fallback_args = mock_popen.call_args[0][0]
    assert fallback_args[0] == "osascript"


@patch("tgf.alerts.resolve_sound", return_value=Path("/System/Library/Sounds/Tink.aiff"))
@patch("tgf.alerts.subprocess.Popen", side_effect=OSError("no afplay"))
def test_fire_fallback_on_popen_error(mock_popen, _mock_resolve):
    a = Alerter(_cfg(), clock=_FakeClock(0.0))
    result = a.fire()
    assert result is True
    assert mock_popen.call_count == 2
    fallback_args = mock_popen.call_args_list[1][0][0]
    assert fallback_args[0] == "osascript"


@patch("tgf.alerts.resolve_sound", return_value=Path("/System/Library/Sounds/Tink.aiff"))
@patch("tgf.alerts.subprocess.Popen")
def test_repeat_sequence_via_tick(mock_popen, _mock_resolve):
    clock = _FakeClock(0.0)
    a = Alerter(_cfg(repeat=3, repeat_gap_sec=0.4), clock=clock)
    assert a.fire() is True
    assert mock_popen.call_count == 1
    a.tick(0.1)  # too early
    assert mock_popen.call_count == 1
    a.tick(0.4)  # gap elapsed -> 2nd play
    assert mock_popen.call_count == 2
    a.tick(0.7)  # too early for 3rd
    assert mock_popen.call_count == 2
    a.tick(0.8)  # gap elapsed -> 3rd play
    assert mock_popen.call_count == 3
    a.tick(5.0)  # no more pending repeats
    assert mock_popen.call_count == 3


@patch("tgf.alerts.resolve_sound", return_value=Path("/System/Library/Sounds/Tink.aiff"))
@patch("tgf.alerts.subprocess.Popen")
def test_volume_argument_passed(mock_popen, _mock_resolve):
    a = Alerter(_cfg(volume=0.5), clock=_FakeClock(0.0))
    a.fire()
    args = mock_popen.call_args[0][0]
    assert args[1] == "-v"
    assert args[2] == "0.5"


@patch("tgf.alerts.resolve_sound")
@patch("tgf.alerts.subprocess.Popen")
def test_side_specific_sound_selected(mock_popen, mock_resolve):
    mock_resolve.return_value = Path("/System/Library/Sounds/Glass.aiff")
    a = Alerter(_cfg(sound="Tink", sound_left="Glass", sound_right=""), clock=_FakeClock(0.0))
    a.fire(side="left")
    mock_resolve.assert_called_with("Glass")

    a2 = Alerter(_cfg(sound="Tink", sound_left="Glass", sound_right=""), clock=_FakeClock(0.0))
    a2.fire(side="right")
    mock_resolve.assert_called_with("Tink")  # sound_right empty -> falls back to cfg.sound


@patch("tgf.alerts.resolve_sound", return_value=Path("/System/Library/Sounds/Tink.aiff"))
@patch("tgf.alerts.subprocess.Popen")
def test_preview_ignores_cooldown(mock_popen, _mock_resolve):
    a = Alerter(_cfg(), clock=_FakeClock(0.0))
    assert a.fire() is True
    a.preview("Glass")
    a.preview("Glass")
    assert mock_popen.call_count == 3
