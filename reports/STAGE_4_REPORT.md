# Stage 4 Report

**Maqsad:** Ogohlantirish (alerts), CLI, headless rejim, signal boshqaruvi, baseline persistensiya.

**Yangi fayllar:**
- `tgf/alerts.py` — `Alerter` (bloklamas `afplay` Popen, xatoda `osascript` fallback, cooldown_sec).
- `tgf/cli.py` — `main()`, argparse, `_Runner` (kamera/pose sikli, debug/headless, signal, kalibratsiya, baseline saqlash/yuklash, NoPose'da 1 FPS).
- `tgf/__main__.py` — `python -m tgf` uchun kirish nuqtasi.
- `tests/test_alerts.py` — 4 ta test (subprocess.Popen va time.monotonic mock qilingan): birinchi chaqiruv, cooldown ichida bostirilishi, cooldowndan keyin ruxsat, Popen xatosida fallback.

**O'zgargan fayllar:**
- `tgf/demo_debug.py` — o'chirildi (funksionallik `cli.py`ga integratsiya qilindi).

**Qarorlar:**
- `Alerter.fire()`: `time.monotonic()` bilan cooldown tekshiriladi; `subprocess.Popen` DEVNULL bilan bloklanmaydi; `OSError`da `osascript -e display notification` fallback ishlaydi.
- `cli._Runner`: SIGINT/SIGTERM `_running=False` qo'yadi (loop tugab, `finally`da camera/pose yopiladi); SIGUSR1 `_recalibrate_requested=True` qo'yadi, keyingi iteratsiyada qayta kalibratsiya bo'ladi.
- Baseline `~/.tgf/calibration.json`ga JSON sifatida saqlanadi; ishga tushganda `--calibrate` bo'lmasa avval shu fayldan yuklanadi, topilmasa/yaroqsiz bo'lsa avtomatik kalibratsiya ishga tushadi.
- `status == "NoPose"` bo'lsa `cam._interval` 1 FPS ga, aks holda `cfg.fps`ga qaytariladi (real vaqt sikli ichida, testlarga ta'sir qilmaydi).
- Debug oynasi `cli.py` ichida shartli `import cv2` bilan faqat `--headless` bo'lmasa ishlaydi (headless rejimda cv2 talab qilinmaydi).

**Ishga tushirish/test:**
```
pip install -r requirements.txt
python -m pytest -q
python -m tgf                     # debug oyna, birinchi ishga tushishda kalibratsiya
python -m tgf --headless --fps 6  # faqat alert, oynasiz
```

**Test natijasi:** `py_compile` barcha fayllar uchun OK. `pytest -q` — **24/24 muvaffaqiyatli** (20 eski + 4 yangi alerts testi). `python -m tgf --help` argparse ishlashi tasdiqlandi.

**Ma'lum kamchiliklar:**
- Haqiqiy SIGUSR1/SIGINT signal oqimi va real kamera bilan uzoq muddatli ishlash sandboxda sinovdan o'tkazilmadi (faqat statik/importa asoslangan tekshiruv).
- `cli.py`da to'liq end-to-end oqim (kalibratsiya→monitor→alert) integratsion test bilan qoplanmagan, faqat qism-modullar (`alerts`, `monitor`, `calibration`) alohida testlangan.

**Keyingi stage uchun eslatma:** Barcha modullar (`config`, `geometry`, `filters`, `camera`, `pose`, `overlay`, `calibration`, `monitor`, `alerts`, `cli`, `__main__`) tayyor. Keyingi stage — sayqal/polish, README yangilash, yoki packaging (masalan setup.py/pyproject, macOS menu-bar icon) bo'lishi mumkin.
