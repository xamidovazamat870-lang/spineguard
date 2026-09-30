from pathlib import Path

from tgf.calibration import Baseline
from tgf.config import Config
from tgf.geometry import Metrics, PoseContext
from tgf.pipeline import Pipeline, CalibState, ReanchorReason
from tgf.profiles import ProfileBank, ProfileContext


def _cfg(**kw) -> Config:
    c = Config()
    for k, v in kw.items():
        setattr(c, k, v)
    c.ctx_settle_sec = 1.0  # keep tests fast
    return c.sanitize()


def _bl(shoulder=0.0) -> Baseline:
    return Baseline(shoulder=shoulder, head=0.0, lean=0.0, sigma_shoulder=0.2, sigma_head=0.2, sigma_neck=0.2)


def _metrics(shoulder=0.0) -> Metrics:
    return Metrics(shoulder=shoulder, head=0.0, neck=0.0, lean=0.0)


def _ctx(cx=0.5, scale=0.3, yaw=0.0) -> PoseContext:
    return PoseContext(cx=cx, scale=scale, body_yaw_deg=yaw, head_yaw_proxy=0.0, edge=False)


class _FakeEstimator:
    """Feeds pre-baked (Landmarks-free) results by monkeypatching process()."""


def _drive_ctx(pipeline: Pipeline, metrics: Metrics, ctx: PoseContext, now: float, n: int = 1, dt: float = 0.2):
    """Directly exercise the RUNNING-branch context logic without a real
    pose estimator, by calling the internal helpers the way process() would.
    Returns (any_reanchor_seen, last_state) plus the advanced clock."""
    t = now
    last_state = None
    seen_reanchor = None
    for _ in range(n):
        reanchor = pipeline._maybe_reanchor(ctx, t, t)
        if reanchor is not None:
            seen_reanchor = reanchor
        last_state = pipeline._monitor.update(metrics, t, ctx) if pipeline._monitor else None
        t += dt
    return (seen_reanchor, last_state), t


def test_context_shift_starts_new_profile_without_false_alert(tmp_path: Path):
    cfg = _cfg()
    base_ctx = _ctx(cx=0.3, scale=0.3)
    pipeline = Pipeline(cfg, tmp_path / "calibration.json", existing_baseline=_bl())
    pipeline._active_profile = pipeline.bank.upsert(pipeline._to_profile_ctx(base_ctx), _bl())

    shifted_ctx = _ctx(cx=0.6, scale=0.3)  # cx shift of 0.3 >> ctx_dx tolerance
    now = 0.0
    (reanchor, state), now = _drive_ctx(pipeline, _metrics(0.0), shifted_ctx, now, n=10)

    # After settle time, pipeline should enter CALIBRATING for the new context
    # (no known profile matches), never firing a Tilt alert in the meantime.
    assert pipeline._calib_state == CalibState.CALIBRATING
    assert state is not None and state.alert is False


def test_return_to_known_profile_switches_quietly(tmp_path: Path):
    cfg = _cfg()
    pipeline = Pipeline(cfg, tmp_path / "calibration.json", existing_baseline=_bl(shoulder=1.0))
    ctx_a = _ctx(cx=0.3, scale=0.3)
    ctx_b = _ctx(cx=0.8, scale=0.3)
    pipeline._active_profile = pipeline.bank.upsert(pipeline._to_profile_ctx(ctx_a), _bl(shoulder=1.0))
    pipeline.bank.upsert(pipeline._to_profile_ctx(ctx_b), _bl(shoulder=9.0))

    now = 0.0
    (reanchor, _), now = _drive_ctx(pipeline, _metrics(0.0), ctx_b, now, n=10)
    assert reanchor == ReanchorReason.SWITCHED
    assert pipeline._monitor.baseline.shoulder == 9.0


def test_pure_posture_change_without_context_shift_never_reanchors(tmp_path: Path):
    cfg = _cfg()
    pipeline = Pipeline(cfg, tmp_path / "calibration.json", existing_baseline=_bl())
    ctx = _ctx(cx=0.5, scale=0.3)
    pipeline._active_profile = pipeline.bank.upsert(pipeline._to_profile_ctx(ctx), _bl())

    now = 0.0
    # Same context every frame, but shoulder metric drifts by 10 deg (a real lean).
    for _ in range(20):
        reanchor = pipeline._maybe_reanchor(ctx, now, now)
        state = pipeline._monitor.update(_metrics(10.0), now, ctx)
        now += 0.2
    assert pipeline._calib_state == CalibState.RUNNING  # never entered CALIBRATING
    assert state.status in ("Tilt Left", "Tilt Right")


def test_auto_learn_suppressed_while_tilted(tmp_path: Path):
    cfg = _cfg()
    pipeline = Pipeline(cfg, tmp_path / "calibration.json", existing_baseline=_bl())
    ctx = _ctx(cx=0.3, scale=0.3)
    pipeline._active_profile = pipeline.bank.upsert(pipeline._to_profile_ctx(ctx), _bl())

    now = 0.0
    # Get into Tilt state at the *original* context first.
    for _ in range(5):
        pipeline._maybe_reanchor(ctx, now, now)
        pipeline._monitor.update(_metrics(10.0), now, ctx)
        now += 0.2

    shifted_ctx = _ctx(cx=0.7, scale=0.3)
    started_calibrating = False
    for _ in range(30):
        pipeline._maybe_reanchor(shifted_ctx, now, now)
        pipeline._monitor.update(_metrics(10.0), now, shifted_ctx) if pipeline._monitor else None
        if pipeline._calib_state == CalibState.CALIBRATING:
            started_calibrating = True
        now += 0.2
    # Because the monitor stays "Tilt Left" the whole time (never returns to
    # Normal), auto-learn must never kick in.
    assert not started_calibrating


def test_sigma_or_roll_guard_rejects_bad_calibration(tmp_path: Path):
    cfg = _cfg(reanchor_roll_guard=5.0)
    pipeline = Pipeline(cfg, tmp_path / "calibration.json", existing_baseline=_bl(shoulder=0.0))
    ctx = _ctx(cx=0.5, scale=0.3)
    nearest = pipeline.bank.upsert(pipeline._to_profile_ctx(_ctx(cx=0.9, scale=0.3)), _bl(shoulder=0.0))

    bad_baseline = _bl(shoulder=50.0)  # wildly different from nearest known profile
    accepted = pipeline._accept_new_baseline(bad_baseline, ctx, ReanchorReason.NEW)
    assert accepted is False


def test_lru_cap_seven_profiles(tmp_path: Path):
    cfg = _cfg(max_profiles=6)
    pipeline = Pipeline(cfg, tmp_path / "calibration.json", existing_baseline=_bl())
    for i in range(7):
        pctx = ProfileContext(cx=0.5 * i, scale=0.3)
        pipeline.bank.upsert(pctx, _bl(), now=float(i))
    assert len(pipeline.bank.profiles) == 6


def test_auto_reanchor_false_preserves_stage10_behavior(tmp_path: Path):
    cfg = _cfg(auto_reanchor=False)
    pipeline = Pipeline(cfg, tmp_path / "calibration.json", existing_baseline=_bl())
    ctx = _ctx(cx=0.5, scale=0.3)
    pipeline._active_profile = pipeline.bank.upsert(pipeline._to_profile_ctx(ctx), _bl())

    shifted_ctx = _ctx(cx=0.9, scale=0.3)
    now = 0.0
    for _ in range(20):
        reanchor = pipeline._maybe_reanchor(shifted_ctx, now, now)
        now += 0.2
    assert pipeline._calib_state == CalibState.RUNNING
    assert reanchor is None
