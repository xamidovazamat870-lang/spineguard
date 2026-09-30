## v12 — Yakuniy: replay-tuning, hujjat, avtostart, tozalash (Stage 12)

- **tools/replay.py** (new): `python -m tools.replay LOG.csv [--set key=val ...] [--sensitivity ...] [--baseline PATH] [--calib-rows N]` replays a `--log` CSV's raw per-channel metrics through `PostureMonitor` with no camera/mediapipe dependency. Auto-calibrates a baseline from the first `Normal`-status rows (or accepts `--baseline`), then prints an alert timeline, a false-alert estimate (alerts fired on frames the original log marked `Normal`), and per-channel validity/trigger stats. Tested against synthetic CSVs (`tests/test_replay.py`).
- **config.py**: `Config.load()` now warns once to stderr if deprecated keys (`enter_deg`, `exit_deg`, `left_threshold`, `right_threshold`) are present in `config.json`, instead of silently ignoring them.
- **README.md**: config table corrected (deprecated keys marked as such; Stage 9-11 fields — `shoulder_deg`, `head_deg`, `neck_deg`, `left_factor`, `right_factor`, `sensitivity`, `use_world`, `auto_reanchor`, etc. — documented, previously missing). New "Sozlashni moslashtirish (replay bilan)" section: log → replay → config workflow and a table of which parameter affects what.
- **Makefile**: added `make sounds` (= `--list-sounds`) and `make profiles` (= `--profiles`) targets, both camera-free.
- **Cleanup**: removed unused imports (`tgf/capture.py`, `tgf/cli.py`, `tgf/pipeline.py`) and a dead duplicate `_NOPOSE_FPS` constant in `capture.py`; verified with `pyflakes`.
- **reports/DEVICE_CHECKLIST.md** (new): short end-user real-device test checklist (tilt with/without shoulder, moving/turning the laptop, second-monitor head turn, sound swap, `--stats` p95/CPU%, 10-minute quiet sit).
- `__version__` = 12.0.0.



- **profiles.py** (new): `ProfileBank` — up to `max_profiles` (LRU) `{ctx: (cx, scale, body_yaw), baseline, last_used}` entries, persisted atomically to `profiles.json` next to `calibration.json`. `match()` finds the nearest known context within `ctx_dx/ctx_scale/ctx_yaw` tolerance. Corrupt file → empty bank. Existing `calibration.json` migrates in as the first profile.
- **pipeline.py**: Detects a stable context shift (`ctx_settle_sec`, low velocity) away from the active profile. Known context → quiet monitor/baseline swap. Unknown context → alerts pause, non-blocking Stage-8-style calibration starts, then a new profile is saved. Safety: never auto-learns while `Tilt`/alert is active (waits for `Normal`); rejects a new baseline whose shoulder value differs from the nearest profile by more than `reanchor_roll_guard`; pure posture drift with unchanged context never re-anchors.
- **config.py**: New fields `auto_reanchor=True`, `ctx_dx=0.15`, `ctx_scale=0.20`, `ctx_yaw=20.0`, `ctx_settle_sec=4.0`, `max_profiles=6`, `away_sec=20.0`, `reanchor_roll_guard=15.0`. Fixed a `sanitize()` bug where every bool field was silently reset to its default (inherited from Stage 9/10; blocked `auto_reanchor=False` / `--no-auto` from ever taking effect).
- **cli.py**: `--no-auto` disables auto re-anchor; `--profiles` lists saved profiles and exits; `--reset-profiles` clears them and exits; `p` key prints the live profile list to stderr. Overlay shows "Yangi joylashuv: to'g'ri o'tiring…" during a new-context calibration.

## v10 — Yaw-invariant angle + turn/edge gating (Stage 10)

- **geometry.py**: Added `Point3D`, `Landmarks3D`, `PoseContext`, `roll3d_deg()` (`atan2(dy, hypot(dx,dz))`, yaw-invariant), `neck3d_deg()`, `compute_pose_context()` (`cx`, `scale`, `body_yaw_deg`, `head_yaw_proxy`, `edge`). `Landmarks` gained optional `nose`.
- **pose.py**: New `process_full()` returns `(Landmarks, Landmarks3D | None)`; reads `pose_world_landmarks` only when `cfg.use_world=True`. `process()` kept as a thin wrapper.
- **monitor.py**: `VALID_STATUSES` gained `"Turned"`. `update()` takes optional `ctx: PoseContext`: gates `head` channel when `|head_yaw_proxy| > head_yaw_max`; scales shoulder/neck weight 0.5× when `|body_yaw_deg| > body_yaw_max`, 0× above `body_yaw_invalid`; scales all channels by edge proximity. If no channel usable but person visible → `"Turned"` (hold-timer frozen, not reset, no alert).
- **config.py**: New fields `use_world` (default `False`), `head_yaw_max=0.6`, `body_yaw_max=35.0`, `body_yaw_invalid=55.0`, `edge_margin=0.08`.
- **pipeline.py**: `Result` gains `ctx: PoseContext | None`; computed each frame and passed into `monitor.update()`.
- **overlay.py**: `"Turned"` color; optional `ctx` text (cx/scale/yaw/edge); `label` param to localize on-screen text independent of the color key.
- **cli.py**: `"Turned"` shown as "Burilgan/Chetda"; CSV log gains `body_yaw_deg, head_yaw_proxy, cx, scale, edge` columns.

## v9 — Shoulder sensitivity: per-channel detection (Stage 9)

- **geometry.py**: `Metrics` fields are now `Optional[float]` per channel (shoulder, head, neck, lean). `compute_metrics` returns `None` only if all channels invalid; per-channel visibility thresholds (`visibility_min_shoulder=0.35`). Added `neck_deg()`.
- **calibration.py**: `Baseline` gains `neck`, `sigma_shoulder/head/neck` fields; old JSON loads with default sigmas. `Calibrator.result()` filters outliers, raises `CalibrationError` on excessive movement. New `load_baseline`/`save_baseline` helpers.
- **monitor.py**: Fused score `S = Σ w_i·d_i/thr_i` (renormalized over valid channels). Per-channel thresholds: `thr_i = max(cfg_i, 3·σ_i) · factor · sensitivity_scale`. `State.reason` added. `left_factor=0.85` makes left trigger easier.
- **config.py**: New fields: `shoulder_deg`, `head_deg`, `neck_deg`, `left_factor`, `right_factor`, `exit_ratio`, `sensitivity`, `visibility_min_shoulder`. Deprecated: `enter_deg`, `exit_deg`, `left_threshold`, `right_threshold` (read but ignored).
- **pose.py**: Removed per-point visibility gate (moved to `compute_metrics`).
- **cli.py / pipeline.py**: `--sensitivity`, `--model` CLI args; updated baseline I/O to use calibration helpers.
- **overlay.py**: Shows per-channel deltas (sh/hd/nk/ln).

## v8 — Smooth operation (Stage 8)

- **filters.py**: Added `OneEuroFilter` (1€, Casiez et al. 2012); `MovingAverage.update()` gains `t=` kwarg for API compat. Config: `filter` (`"oneeuro"|"ma"`), `oe_min_cutoff`, `oe_beta`.
- **capture.py** (new): `LatestFrameGrabber` — daemon thread reads camera at `capture_fps`, exposes only the newest frame via `get_new(last_seq)`.
- **camera.py**: Refactored to use `LatestFrameGrabber`; `read()` returns the latest buffered frame without blocking.
- **pipeline.py** (new): `Pipeline.process()` encapsulates inference + non-blocking calibration state machine (`IDLE→WAITING_PERSON→CALIBRATING→RUNNING`). Calibration progress 0..1 exposed for overlay.
- **cli.py**: Debug mode runs inference in worker thread, `imshow/waitKey` at ~30 Hz in main thread. `--log PATH` CSV logging, `--stats` p50/p95 every 5 s to stderr.
- **pose.py**: `model_complexity` and `mp_smooth` now read from config.
- **config.py**: New fields: `filter`, `oe_min_cutoff`, `oe_beta`, `capture_fps`, `mp_smooth`, `model_complexity`.

# Changelog

## v7
- Yangi `tgf/sounds.py`: `list_system_sounds()`, `resolve_sound(spec)` (tizim nomi yoki fayl yo'li).
- `Config`: `sound`, `sound_left`, `sound_right`, `volume`, `repeat`, `repeat_gap_sec` qo'shildi (eski config buzilmaydi).
- `Alerter`: `fire(side)` endi chap/o'ng uchun alohida ovoz tanlaydi; `tick(now)` bilan thread'siz takror (`repeat`/`repeat_gap_sec`); `preview(spec)` cooldown'ni mensimay sinov uchun; ovoz topilmasa `Tink`ga, keyin `osascript`ga tushadi.
- `cli.py`: `--sound`, `--volume`, `--list-sounds`, `--test-sound` qo'shildi; asosiy siklga `alerter.tick()`; debug oynada `s` — tizim tovushi bo'ylab aylanish + sinov + `cfg.save()`.
- `overlay.draw()`ga ixtiyoriy `extra: str` — joriy ovoz nomini oyna pastida ko'rsatadi.
- Testlar: `tests/test_sounds.py` (yangi), `tests/test_alerts.py` (sound resolution mock bilan qayta yozildi + repeat/volume/side testlari).

## v1
- Config dataclass + JSON load/save qo'shildi.
- Sof geometriya funksiyalari: roll_deg, lean_ratio, compute_metrics.
- MovingAverage filtri (deque asosida).
- 12 ta pytest test qo'shildi, barchasi o'tdi.

## v2
- Camera qo'shildi: cv2.VideoCapture, FPS cheklash, macOS ruxsat xatosi.
- PoseEstimator qo'shildi: mediapipe pose, model_complexity=0.
- Debug overlay qo'shildi: skeleton chiziqlari, burchak matni, status rangi.
- demo_debug.py vaqtinchalik oyna qo'shildi.

## v3
- Calibrator/Baseline qo'shildi: medianaga asoslangan kalibratsiya.
- PostureMonitor qo'shildi: delta+silliqlash, chap/o'ng hysteresis, hold_sec asosida alert.
- 8 ta yangi pytest test (test_monitor.py), sun'iy vaqt bilan.
- demo_debug.py: 'c' kalibratsiya va status/ALERT ko'rsatish qo'shildi.

## v4
- Alerter qo'shildi: afplay (bloklamas) + osascript fallback, cooldown_sec.
- cli.py va __main__.py qo'shildi: argparse, debug/headless, SIGINT/SIGTERM/SIGUSR1, baseline persistensiya.
- NoPose holatida avtomatik 1 FPS.
- demo_debug.py o'chirildi (cli.py ga integratsiya).
- 4 ta yangi pytest test (test_alerts.py, subprocess mock).

## v5
- Xato tuzatildi: `roll_deg`da x-farq belgisi teskari edi — LEFT/RIGHT tilt yo'nalishi haqiqiy holatga teskari chiqardi.
- Xato tuzatildi: `cli.py` debug overlayga `metrics` o'rniga doim `None` uzatilayotgan edi.
- To'liq `README.md`: o'rnatish, ishga tushirish, sozlamalar jadvali, kalibratsiya, muammolar bo'limi.
- `scripts/install_launchd.sh`, `scripts/uninstall_launchd.sh`, `scripts/com.tgf.posture.plist` — headless avtostart (LaunchAgents).
- Yakuniy tekshiruv: py_compile va 24 ta pytest — barchasi o'tdi.

## v6 (0.2.0)
- Xato: burchak normallashtirilgan koordinatada (4:3) hisoblanib ~33% oshib ketardi — endi `aspect` bilan piksel fazosida.
- Xato: `install_launchd.sh` tizim `python3` ni ishlatardi (mediapipe yo'q → crash-loop) — endi `.venv/bin/python`, import tekshiruvi bilan.
- Xato: `KeepAlive=true` + xato bilan chiqish → cheksiz qayta ishga tushish. Endi `SuccessfulExit=false`, `ThrottleInterval=30`, kamera uchun ichki backoff-retry.
- Xato: kadr `None` bo'lsa asosiy sikl 100% CPU bilan aylanardi — endi pauza + 25 xatodan so'ng kamerani qayta ochish (sleep/wake, kamera band).
- Xato: kalibratsiya muvaffaqiyatsiz bo'lsa (login paytida odam yo'q) monitor hech qachon yaratilmasdi — endi har 10 s qayta uriniladi.
- Xato: NoPose (1 FPS) holatida qayta kalibratsiya namuna yetishmasligidan yiqilardi — kalibratsiya normal FPS'da.
- Xato: bitta tushib qolgan kadr hold-taymerni nolga tushirardi — `nopose_grace_sec` (1.5 s); uzoq NoPose'da filtrlar tozalanadi.
- Xato: `--config` boshqa joyga ko'rsatilsa ham baseline `~/.tgf`ga yozilardi — endi config yonida.
- Xato: buzuq `calibration.json`/`config.json` (masalan `[]`, `"fps":"x"`) crash qilardi — validatsiya + clamp.
- `opencv-python` + `mediapipe` (`opencv-contrib-python` ni tortadi) to'qnashuvi — endi pyproject'da pinlangan.
- afplay jarayonlari yig'ib olinadi (zombie yo'q), ovoz xatosida bildirishnoma.
- macOS: AVFoundation backend, aspect saqlanadigan resize, GUI'da NoPose sekinlashtirilmaydi.
- Dev kanali: `TGF_CHANNEL=dev` → `~/.tgf-dev`, launchd label `com.tgf.posture.dev`. `launchctl bootstrap/bootout` (load/unload eskirgan).
- `pyproject.toml`, `Makefile`, `tgf --version`, atomik yozish, 7 ta yangi test.
