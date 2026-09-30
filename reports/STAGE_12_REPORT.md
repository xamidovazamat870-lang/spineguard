# STAGE 12 REPORT — Yakuniy

**Maqsad:** Kamerasiz sozlash asbobi (replay), hujjatni yakunlash, avtostartni moslash, kod tozalash, real qurilma tekshiruv ro'yxati.

**Yangi fayllar:**
- `tools/replay.py`, `tools/__init__.py` — CSV log → Metrics → PostureMonitor replay (alert vaqt chizig'i, yolg'on-alert taxmini, kanal statistikasi).
- `tests/test_replay.py` — 8 test, sintetik CSV bilan (yuklash, metrics parsing, avto-baseline, override, alert aniqlash, yolg'on-alert, CLI `main()`).
- `reports/DEVICE_CHECKLIST.md` — a-f bandlar bo'yicha qisqa foydalanuvchi ro'yxati.

**O'zgargan fayllar:**
- `tgf/config.py` — `Config.load()` endi eskirgan kalitlarni (`enter_deg` va h.k.) topsa stderr'ga bir marta ogohlantiradi (`DEPRECATED_KEYS`).
- `tgf/capture.py`, `tgf/cli.py`, `tgf/pipeline.py` — ishlatilmagan importlar (`sys`, `Tuple`, `json`, `math`, `os`, `tempfile`, `field`, `Landmarks3D`, dublikat `_NOPOSE_FPS`) olib tashlandi; `pyflakes` bilan tekshirildi (faqat qasddan qoldirilgan, `# noqa` bilan belgilangan lazy `cv2` importi qoldi).
- `README.md` — sozlamalar jadvali to'g'rilandi (eskirgan kalitlar belgilandi; Stage 9-11 maydonlari qo'shildi, ilgari yo'q edi); yangi "Sozlashni moslashtirish (replay bilan)" bo'limi.
- `Makefile` — `make sounds`, `make profiles` qo'shildi (`.PHONY` yangilandi).
- `CHANGELOG.md` — `## v12` yozuvi; `tgf/__init__.py` — `__version__ = "12.0.0"`.

**Qarorlar:**
- Replay `neck` kanalini CSV'dan tiklamaydi (log formatida yo'q) — `Metrics.neck=None` sifatida o'tkaziladi; bu `sh_ok and ear_ok` mavjud bo'lgan holatlarda ozgina farq qilishi mumkin, lekin shoulder/head/lean asosiy tuning uchun yetarli.
- Baseline avtomatik logdagi dastlabki `Normal` qatorlardan kalibratsiya qilinadi (`--calib-rows`, standart 30); `--baseline PATH` bilan haqiqiy `calibration.json`ni ham berish mumkin.
- Versiya sxemasi mavjud repo konventsiyasiga mos qoldirildi (`12.0.0`), reja matnidagi "0.3.0" o'rniga — v7-v11 allaqachon shu uslubda.
- `scripts/*`/plist Stage 11'dan beri profil papkasiga mos edi (baseline bilan bir joyda `profiles.json`) — o'zgarish talab qilinmadi, faqat Makefile'ga `sounds`/`profiles` qo'shildi.

**Test natijasi:** `python -m py_compile tgf/*.py tests/*.py tools/*.py` — OK. `pytest -q` — **107 passed** (97 avvalgi + 2 yangi config testi + 8 yangi replay testi).

**Ma'lum kamchiliklar:**
- Replay `neck` kanalini hisoblamaydi (yuqorida izohlangan).
- Real qurilma sinovi (checklist a-f) hali bajarilmagan — foydalanuvchida.

**Real qurilmada sinash qo'llanmasi:** `reports/DEVICE_CHECKLIST.md`ga qarang.

**Keyingi stage uchun eslatma:** Agar kelajakda log formatiga `neck` ustuni qo'shilsa, `tools/replay.row_to_metrics()`ni yangilash kerak bo'ladi.
