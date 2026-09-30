# Stage 2 Report

**Maqsad:** Kamera, pose estimation va debug overlay.

**Yangi fayllar:**
- `tgf/camera.py` — `Camera` (cv2.VideoCapture, FPS cheklash, grab/retrieve, resize, close).
- `tgf/pose.py` — `PoseEstimator` (mp.solutions.pose, model_complexity=0, Landmarks|None).
- `tgf/overlay.py` — `draw()` (yelka/quloq chiziqlari, burchak matni, status rangi).
- `tgf/demo_debug.py` — vaqtinchalik demo oyna ('q' chiqish).

**O'zgargan fayllar:** Yo'q.

**Qarorlar:**
- `Camera.read()`: `grab()` har chaqiruvda, `retrieve()` faqat FPS intervali o'tgach — ortiqcha kadr dekodlanmaydi.
- Kamera ochilmasa `CameraError` (macOS ruxsat eslatmasi bilan) ko'tariladi.
- `PoseEstimator`: landmark 11/12/7/8 (yelka L/R, quloq L/R); visibility_min dan past bo'lsa None.
- `overlay.draw`: tahlil flip qilinmagan kadrda, faqat ko'rsatishda flip; landmark piksellar flipdan keyin x=w-x bilan moslashtiriladi.

**Ishga tushirish/test:**
```
pip install -r requirements.txt
python -m pytest -q
python -m tgf.demo_debug
```

**Test natijasi:** cv2/mediapipe sandboxda mavjud edi — `py_compile` barcha fayllar uchun OK, `pytest -q` **12/12 muvaffaqiyatli**. camera.py/pose.py haqiqiy kamerasiz sinovdan o'tkazilmadi (import va statik tekshiruv qilindi).

**Ma'lum kamchiliklar:**
- Haqiqiy kamera bilan macOS'da vizual tekshiruv qilinmadi (sandboxda kamera yo'q).
- calibration/monitor/alerts/cli hali yozilmagan.

**Keyingi stage uchun eslatma:** `tgf/calibration.py`, `tgf/monitor.py` — `compute_metrics`, `MovingAverage`, `Camera`, `PoseEstimator` tayyor va import qilinishi mumkin.
