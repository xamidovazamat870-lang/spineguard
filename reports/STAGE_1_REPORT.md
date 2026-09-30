# Stage 1 Report

**Maqsad:** Loyiha poydevori — config, sof geometriya, filtr va testlar.

**Yangi fayllar:**
- `tgf/__init__.py` — paket init, versiya.
- `tgf/config.py` — `Config` dataclass, JSON load/save, noma'lum kalitlar e'tiborsiz.
- `tgf/geometry.py` — `roll_deg`, `lean_ratio`, `compute_metrics`, `Point`/`Landmarks`/`Metrics`.
- `tgf/filters.py` — `MovingAverage` (deque asosida).
- `tests/test_geometry.py` — 12 ta test.
- `requirements.txt`, `README.md`.

**O'zgargan fayllar:** Yo'q (birinchi stage).

**Qarorlar:**
- `roll_deg`: `atan2(a.y-b.y, b.x-a.x)` — musbat = chap tomon pastda (spec talabiga mos, image koordinatada y pastga o'sadi).
- Burchak `(-90, 90]` ga `_normalize_angle` bilan keltiriladi.
- `lean_ratio` shoulder_width=0 holatida 0.0 qaytaradi (division-by-zero himoyasi).

**Ishga tushirish/test:**
```
python -m py_compile tgf/*.py tests/*.py
python -m pytest -q   # yoki sandboxda pytest yo'q bo'lsa qo'lda runner
```

**Test natijasi:** Sandbox'da internet yo'qligi sabab `pytest` o'rnatilmadi; testlar qo'lda yozilgan runner orqali ishga tushirildi — **12/12 muvaffaqiyatli**.

**Ma'lum kamchiliklar:**
- `pytest` sandboxda tekshirilmadi (paket yo'q); foydalanuvchi mashinasida `pip install -r requirements.txt` dan keyin `pytest -q` bilan qayta tasdiqlash tavsiya etiladi.
- camera/pose/overlay/calibration/monitor/alerts/cli modullari hali yozilmagan (keyingi stagelar).

**Keyingi stage uchun eslatma:** `tgf/camera.py`, `tgf/pose.py` — cv2/mediapipe kerak bo'ladi, sandboxda import qilib bo'lmasligi mumkin (faqat syntax/py_compile bilan tekshirish kifoya).
