# Stage 3 Report

**Maqsad:** Kalibratsiya va postura holat mashinasi (hysteresis + hold-based alert).

**Yangi fayllar:**
- `tgf/calibration.py` — `Baseline`, `Calibrator` (namuna yig'ish, medianadan baseline, yetarli namuna bo'lmasa `CalibrationError`).
- `tgf/monitor.py` — `State`, `PostureMonitor` (delta hisoblash, MovingAverage silliqlash, chap/o'ng hysteresis, hold_sec asosida alert).
- `tests/test_monitor.py` — 8 ta test (sun'iy `now`, real sleep yo'q).

**O'zgargan fayllar:**
- `tgf/demo_debug.py` — 'C' tugmasi bilan kalibratsiya (progress holati "Calibrating"), kalibratsiyadan keyin `PostureMonitor` ishga tushadi, status+ALERT matni oynada ko'rsatiladi.

**Qarorlar:**
- `PostureMonitor.update`: `combined = delta_shoulder + delta_head` — ikkala burchak birga chap/o'ng kuchini beradi; `left_mag`/`right_mag` musbat qismga ajratiladi.
- Kirish: `enter_deg` VA mos tomon `left_threshold`/`right_threshold` dan oshganda tilted holatga o'tadi. Chiqish: mos tomon miqdori `exit_deg` dan pastga tushgandagina Normal'ga qaytadi (hysteresis, "deadband"da tilted saqlanadi).
- `_since` faqat tilted holatga kirganda o'rnatiladi; `alert = (now - _since) >= hold_sec`, uzluksiz tilted bo'lishi shart — reset holatlar (Normal/NoPose) taymerni to'liq tozalaydi.
- `NoPose` yoki `m is None` — barcha holat (tilted, taymer, alert) reset qilinadi.
- `Calibrator` min_samples parametrik (`demo_debug` da `calib_sec * fps * 0.5` taxminiy).

**Ishga tushirish/test:**
```
pip install -r requirements.txt
python -m pytest -q
python -m tgf.demo_debug   # 'c' kalibratsiya, 'q' chiqish
```

**Test natijasi:** `py_compile` barcha fayllar uchun OK. `pytest -q` — **20/20 muvaffaqiyatli** (12 eski + 8 yangi monitor testi).

**Ma'lum kamchiliklar:**
- Haqiqiy kamera bilan kalibratsiya UI vizual tekshirilmadi (sandboxda kamera yo'q).
- alerts.py va cli.py hali yozilmagan.

**Keyingi stage uchun eslatma:** `tgf/alerts.py` (macOS bildirishnoma/tovush, cooldown_sec) va `tgf/cli.py` (`python -m tgf` argparse, headless/calibrate flag) navbatda. `PostureMonitor.update(...).alert` cooldown bilan `Alerter.fire()` ga bog'lanishi kerak.
