# Stage 5 Report — Sayqal, README, avtostart, yakuniy tekshiruv

## Maqsad
Mavjud kodni sayqalash, README va launchd avtostart qo'shish, loyihani yakunlash.

## Yangi fayllar
- `README.md` (to'liq qayta yozildi) — o'rnatish, ishga tushirish, sozlamalar jadvali, kalibratsiya, avtostart, muammolar bo'limi.
- `scripts/com.tgf.posture.plist` — launchd shabloni (headless avtostart).
- `scripts/install_launchd.sh` — plistni to'ldirib `~/Library/LaunchAgents`ga o'rnatadi va yuklaydi.
- `scripts/uninstall_launchd.sh` — avtostartni o'chiradi.

## O'zgargan fayllar
- `tgf/geometry.py` — `roll_deg` da x-farq belgisi teskari edi (`b.x - a.x` o'rniga shartnomadagi `a.x - b.x` kerak), bu LEFT/RIGHT tilt yo'nalishini butunlay teskari qilib qo'ygan edi. Tuzatildi.
- `tests/test_geometry.py` — yuqoridagi tuzatishga mos ravishda ikkita testning kirish nuqtalari to'g'irlandi (shartnoma: musbat = chap past = LEFT).
- `tgf/cli.py` — debug overlay chaqiruvida `metrics` doim `None` uzatilayotgan edi (`draw(frame, lm, None, status)`), shuning uchun oynada shoulder/head/lean qiymatlari hech qachon ko'rinmasdi. Endi hisoblangan `metrics` uzatiladi.

## Qarorlar
- Boshqa fayllarda (`config.py`, `filters.py`, `camera.py`, `pose.py`, `monitor.py`, `alerts.py`, `calibration.py`, `overlay.py`) resurs yopish (`close()`/`finally`), FPS throttle va exception handling to'g'ri topildi — o'zgartirilmadi.
- launchd plist shablon sifatida saqlanadi, `install_launchd.sh` `sed` bilan `python3` yo'li, loyiha papkasi va `$HOME`ni joylashtiradi — turli foydalanuvchi muhitlarida ishlashi uchun.
- `KeepAlive=true` tanlandi, chunki dastur uzoq muddat fonda ishlashi kerak; agar chiqib ketsa, launchd qayta ishga tushiradi.

## Ishga tushirish/test
```bash
python -m tgf
python -m tgf --headless
scripts/install_launchd.sh
pytest -q
```

## Test natijasi
- `python -m py_compile tgf/*.py tests/*.py` — xatosiz.
- `pytest -q` — 24 test, barchasi o'tdi (geometry sign-fix bilan birga).
- `bash -n scripts/*.sh` — sintaksis xatosiz.
- Sandbox'da cv2/mediapipe yo'qligi sababli `camera.py`, `pose.py`, `overlay.py`, `cli.py` faqat `py_compile` bilan tekshirildi (import-vaqtida ishlaydigan kod yo'q, xato chiqmadi).

## Ma'lum kamchiliklar
- `roll_deg` tuzatilgandan so'ng, agar foydalanuvchi Stage 4 baseline (`~/.tgf/calibration.json`) allaqachon saqlangan bo'lsa, eski (teskari belgili) baseline yangi hisob-kitob bilan mos kelmasligi mumkin — birinchi ishga tushirishda `--calibrate` bilan qayta kalibratsiya tavsiya etiladi.
- Kamera va MediaPipe haqiqiy qurilmada sinovdan o'tkazilmadi (sandbox cheklovi).

## Keyingi stage uchun eslatma
Loyiha Stage 5 bilan yakunlanadi. Kelajakda kengaytirish uchun: ko'p monitor/kamera qo'llab-quvvatlash, statistika/tarix logi, menu-bar (rumps) integratsiyasi ko'rib chiqilishi mumkin.
