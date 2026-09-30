# TGF — Ultra-yengil postura monitor (macOS)

Webcam orqali yelka/bosh qiyaligini kuzatuvchi, minimal resurs sarflaydigan Python vositasi.
OpenCV + MediaPipe Pose (`model_complexity=0`) asosida ishlaydi.

## Talablar

- macOS (Apple Silicon yoki Intel), Python 3.9–3.12 (3.13 da mediapipe yo'q; tavsiya: `brew install python@3.12`)
- Webcam

## O'rnatish

```bash
make install     # venv + pip install -e ".[dev]" + pip check
make test
```

## macOS kamera ruxsati

Birinchi ishga tushirishda macOS kamera ruxsatini so'raydi. Agar so'ramasa yoki rad etilgan bo'lsa:
**Tizim sozlamalari → Maxfiylik va xavfsizlik → Kamera** bo'limida terminal/ilovangizga ruxsat bering, so'ng qayta ishga tushiring.

## Ishga tushirish

```bash
python -m tgf                  # oyna bilan, debug overlay
python -m tgf --headless       # oynasiz, faqat ovozli/bildirishnoma alert
python -m tgf --calibrate      # saqlangan baseline'ni mensimay qayta kalibratsiya
python -m tgf --fps 10         # FPS'ni bekor qilish
python -m tgf --camera 1       # boshqa kamera indeksi
python -m tgf --config PATH    # boshqa config fayl
python -m tgf --sound Glass --volume 0.5   # ovoz va balandlikni bekor qilish
python -m tgf --list-sounds    # tizim ovozlari ro'yxati (kamerasiz)
python -m tgf --test-sound --sound Glass   # ovozni sinab ko'rish (kamerasiz)
python -m tgf --no-auto        # avto re-anchor'ni o'chirish (Stage 10 xatti-harakati)
python -m tgf --profiles       # saqlangan joylashuv profillarini chiqarish (kamerasiz)
python -m tgf --reset-profiles # barcha profillarni o'chirish (kamerasiz)
```

Oynali rejimda: `q` — chiqish, `c` — qayta kalibratsiya, `s` — keyingi tizim ovoziga o'tish (sinab ko'radi va saqlaydi), `p` — joriy profillar ro'yxatini terminalga chiqarish.
Headless rejimda qayta kalibratsiya uchun: `kill -SIGUSR1 <pid>`.

Birinchi ishga tushirishda (yoki `--calibrate` bilan) `calib_sec` davomida to'g'ri o'tiring — dastur baseline holatni saqlaydi.

## Sozlamalar (`~/.tgf/config.json`)

| Maydon | Standart | Ma'nosi |
|---|---|---|
| `fps` | 8 | Normal holatdagi kadr chastotasi |
| `width`, `height` | 640, 480 | Kadr o'lchami |
| `window` | 12 | Moving-average oynasi (kadrlarda, faqat `filter="ma"` bo'lsa) |
| `hold_sec` | 3.0 | Alert chiqishidan oldin tilt qancha ushlanishi kerak (sek) |
| `cooldown_sec` | 30.0 | Ketma-ket alertlar orasidagi minimal vaqt (sek) |
| `calib_sec` | 3.0 | Kalibratsiya davomiyligi (sek) |
| `visibility_min` | 0.5 | Ear/nose landmark ishonchlilik chegarasi |
| `camera_index` | 0 | Kamera indeksi |
| `nopose_grace_sec` | 1.5 | Qisqa landmark uzilishlarini o'tkazib yuborish (hold-taymer nolga tushmaydi) |
| `sound` | "Tink" | Ogohlantirish ovozi: tizim nomi (`/System/Library/Sounds`) yoki fayl yo'li |
| `sound_left` | "" | Chap tomon uchun alohida ovoz (bo'sh = `sound`) |
| `sound_right` | "" | O'ng tomon uchun alohida ovoz (bo'sh = `sound`) |
| `volume` | 1.0 | `afplay` balandligi (0.0-2.0) |
| `repeat` | 1 | Har bir alertda ovoz necha marta chalinishi (1-5) |
| `repeat_gap_sec` | 0.4 | Takrorlar orasidagi tanaffus (sek) |
| `filter` | `"oneeuro"` | Filter turi: `"oneeuro"` (1€ filter, kam kechikish) yoki `"ma"` (moving average) |
| `oe_min_cutoff` | `1.0` | 1€ filter min cutoff chastotasi (Hz) |
| `oe_beta` | `0.08` | 1€ filter tezlik koeffitsienti |
| `capture_fps` | `15` | Kamera capture thread FPS |
| `mp_smooth` | `false` | MediaPipe `smooth_landmarks` (kechikishni oshiradi) |
| `model_complexity` | `0` | MediaPipe model murakkabligi (0=tez, 1=aniqroq) |
| `shoulder_deg` | 4.0 | Yelka kanali uchun bazaviy chegara (daraja) — pastroq = sezgirroq |
| `head_deg` | 6.0 | Bosh (quloq chizig'i) kanali uchun bazaviy chegara (daraja) |
| `neck_deg` | 5.0 | Bo'yin (yelka→quloq vektori) kanali uchun bazaviy chegara (daraja) |
| `left_factor` | 0.85 | Chap tomon chegarasiga ko'paytiruvchi (<1 = chapga sezgirroq) |
| `right_factor` | 1.0 | O'ng tomon chegarasiga ko'paytiruvchi |
| `exit_ratio` | 0.7 | Tilt holatidan chiqish uchun kirish chegarasiga nisbat (gisterezis) |
| `sensitivity` | `"medium"` | Umumiy sezgirlik: `"low"` (1.3×), `"medium"` (1.0×), `"high"` (0.75×) — barcha chegaralarga ko'paytiriladi |
| `visibility_min_shoulder` | 0.35 | Yelka landmark ishonchlilik chegarasi (ko'zdan pastroq, chunki yelka ko'proq bekiladi) |
| `use_world` | `false` | Yaw'ga bog'liq bo'lmagan 3D burchak (`pose_world_landmarks`) ishlatilsinmi |
| `head_yaw_max` | 0.6 | Bosh burilish proksi chegarasi — undan yuqorida `head` kanali yaroqsiz |
| `body_yaw_max` | 35.0 | Tana yaw chegarasi (daraja) — undan yuqorida yelka/bo'yin vazni 0.5× |
| `body_yaw_invalid` | 55.0 | Tana yaw chegarasi — undan yuqorida yelka/bo'yin yaroqsiz |
| `edge_margin` | 0.08 | Kadr chetiga yaqinlik chegarasi (0..1) — yaqin bo'lsa kanal vazni pasayadi |
| `auto_reanchor` | `true` | Joylashuv o'zgarganda avtomatik profil almashtirish/o'rganish |
| `ctx_dx` | 0.15 | Kontekst mos kelishi uchun `cx` farqi chegarasi (nisbiy, 0..1) |
| `ctx_scale` | 0.20 | Kontekst mos kelishi uchun `scale` farqi chegarasi (nisbiy) |
| `ctx_yaw` | 20.0 | Kontekst mos kelishi uchun tana yaw farqi chegarasi (daraja) |
| `ctx_settle_sec` | 4.0 | Yangi kontekst qancha barqaror turishi kerak (sek), avto-almashtirish/o'rganishdan oldin |
| `max_profiles` | 6 | Saqlanadigan profillar soni chegarasi (LRU chiqarish) |
| `away_sec` | 20.0 | `NoPose` qancha davom etsa "ketgan" deb hisoblanadi (hozircha faqat izlash uchun) |
| `reanchor_roll_guard` | 15.0 | Yangi baseline eng yaqin profildan shuncha darajadan ko'p farq qilsa — rad etiladi |

Baseline `~/.tgf/calibration.json` faylida, profillar `~/.tgf/profiles.json` faylida saqlanadi.

**Eskirgan kalitlar** (`enter_deg`, `exit_deg`, `left_threshold`, `right_threshold`): Stage 9'dan beri o'qiladi, lekin mantiqda ishlatilmaydi (`shoulder_deg`/`head_deg`/`neck_deg`/`left_factor`/`right_factor` o'rnini bosgan). Agar `config.json`da hali ham mavjud bo'lsa, dastur ishga tushganda stderr'ga bir marta ogohlantirish chiqaradi.

## Sozlashni moslashtirish (replay bilan)

Kamerasiz, yozilgan CSV log asosida sozlamalarni sinab ko'rish mumkin:

```bash
python -m tgf --log ~/tgf_session.csv --headless     # 1) bir necha daqiqa yozib oling (Normal + tilt holatlarini qamrab oling)
python -m tools.replay ~/tgf_session.csv             # 2) o'sha logni qayta o'tkazing
python -m tools.replay ~/tgf_session.csv --sensitivity high --set hold_sec=1.5   # sozlamalarni sinash
```

`tools.replay` logdagi xom `shoulder/head/lean` qiymatlarini o'qib, `PostureMonitor`ni (kamera/mediapipe'siz) qayta ishga tushiradi va chiqaradi:
- **alert vaqt chizig'i** — qachon, qaysi tomonga, qaysi sabab bilan (`reason`) alert chiqqani;
- **yolg'on-alert taxmini** — asl yozuvda `Normal` deb belgilangan kadrda yangi sozlamalar bilan alert chiqsa;
- **kanal statistikasi** — har bir kanal (`shoulder`/`head`/`lean`) necha kadrda yaroqli bo'lgani va qaysi kanal qancha alertga sabab bo'lgani.

Qaysi parametr nimaga ta'sir qiladi:

| Maqsad | Qaysi parametrni sozlash |
|---|---|
| Umumiy sezgirlikni oshirish/pasaytirish | `--sensitivity low/medium/high` yoki `sensitivity` |
| Faqat yelka (ko'proq/kamroq) | `shoulder_deg` |
| Faqat bosh burilishi | `head_deg` |
| Chap va o'ng orasidagi assimetriya | `left_factor`, `right_factor` |
| Yaw'ga bog'liq bo'lmagan aniqlik (noutbuk burilganda) | `use_world=true` |
| Ikkinchi monitorga qarashda yolg'on alert | `head_yaw_max` (oshiring) |
| Noutbukni suriganda yolg'on alert | `ctx_dx`/`ctx_scale` (oshiring, tezroq yangi profil sifatida tanisin) |

Yangi `~/.tgf/config.json` qiymatlarini saqlash uchun `--set key=val` bilan sinab ko'rgan qiymatlarni qo'lda faylga yozing (replay o'zi config faylini o'zgartirmaydi).

## Avtostart (launchd)

```bash
make agent / make unagent            # stable kanal (~/.tgf)
make agent-dev / make unagent-dev    # dev kanal (~/.tgf-dev, com.tgf.posture.dev)
make recalibrate                     # SIGUSR1 (stable) — qayta kalibratsiyaga majburlash
make sounds                          # = python -m tgf --list-sounds (kamerasiz)
make profiles                        # = python -m tgf --profiles (kamerasiz)
```

Tizim kirganda headless rejimda ishga tushadi. Loglar: `~/.tgf/stdout.log`, `~/.tgf/stderr.log`.

## Kanallar (stable / dev)

`TGF_CHANNEL=dev` — alohida config/baseline/log (`~/.tgf-dev`) va alohida launchd label. `TGF_HOME=/yo'l` bilan to'liq bekor qilish mumkin.
Stable va dev bir vaqtda ishlasa, ikkalasi bitta kamerani ochadi — dev sinovi paytida `make unagent` qiling.

## Muammolar

- **Kamera ochilmadi**: yuqoridagi ruxsat bo'limiga qarang; boshqa ilova kamerani band qilmaganini tekshiring.
- **Doim "NoPose"**: yorug'lik yetarli emas yoki yelka/bosh kamera ko'rish maydonidan tashqarida; `visibility_min`ni pasaytirib ko'ring.
- **Alert kelmayapti**: `hold_sec`/`cooldown_sec` qiymatlarini tekshiring; headless rejimda ovoz `afplay` orqali, muqobil holda `osascript` bildirishnomasi orqali chiqadi.
- **False positive tilt**: `enter_deg`/`left_threshold`/`right_threshold`ni oshiring yoki qayta kalibratsiya qiling (`c` yoki SIGUSR1).
- **Ovoz eshitilmayapti**: `--list-sounds` bilan mavjud nomlarni tekshiring; noto'g'ri/yo'q fayl avtomatik `Tink`ga, keyin bildirishnomaga tushadi — crash bo'lmaydi.
- **launchd ishga tushmayapti**: `launchctl list | grep tgf` bilan holatni tekshiring, `~/.tgf/stderr.log`ni ko'ring.

## Testlar

```bash
pytest -q
```
