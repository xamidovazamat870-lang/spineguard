# Stage 10 Report — Yaw-invariant angle + turn/edge gating

**Maqsad:** Foydalanuvchi burilgan/kadr chetida bo'lganda yolg'on alert bermaslik; 3D `pose_world_landmarks` orqali yaw'ga bog'liq bo'lmagan burchak hisoblash imkonini qo'shish.

**Yangi fayllar:** `tests/test_stage10.py`, `reports/STAGE_10_REPORT.md`.

**O'zgargan fayllar:**
- `tgf/geometry.py` — `Point3D`, `Landmarks3D`, `PoseContext`, `roll3d_deg`, `neck3d_deg`, `compute_pose_context`; `Landmarks.nose` (optional, 2D).
- `tgf/pose.py` — `process_full()` (2D + ixtiyoriy 3D), `process()` — wrapper.
- `tgf/monitor.py` — `"Turned"` status, `update(ctx=...)` gating (head yaw, body yaw, edge).
- `tgf/config.py` — `use_world`, `head_yaw_max`, `body_yaw_max`, `body_yaw_invalid`, `edge_margin`.
- `tgf/pipeline.py` — `Result.ctx`, har kadr `compute_pose_context()` chaqiriladi.
- `tgf/overlay.py` — `"Turned"` rangi, `ctx` matni, `label` parametri (lokalizatsiya uchun).
- `tgf/cli.py` — "Burilgan/Chetda" label; CSV log'ga yaw/edge ustunlari.
- `README.md`, `CHANGELOG.md`, `tgf/__init__.py` (v10.0.0).

**Qarorlar:**
- `head_yaw_proxy` 2D `nose.x` va o'rta-quloq x'idan hisoblanadi (3D talab qilinmaydi) — shuning uchun `use_world=False` bo'lsa ham burilishni aniqlash mumkin.
- `body_yaw_deg` faqat 3D mavjud bo'lsa hisoblanadi (`None` bo'lsa gating o'tkazilmaydi — Stage 9 xatti-harakati saqlanadi).
- Gating fusion bosqichida amalga oshiriladi (kanal vaznini 0/0.5/1 ga ko'paytirish), xom `Metrics`ni o'zgartirmaydi — shu bilan log/overlay'dagi xom qiymatlar buzilmaydi.
- `"Turned"`: barcha kanal vazni 0 bo'lsa. Hold-taymer (`_since`) o'zgarmaydi — `_tilted`/`_side` saqlanadi, faqat status va alert bostiriladi.
- `use_world=False` (default): `pose.py` 3D landmark qidirmaydi → `ctx.body_yaw_deg=None` → shoulder/neck gating hech qachon ishlamaydi, faqat head-yaw/edge gating faol (bu ataylab — 2D-only rejimda ham asosiy himoya bo'lsin).

**Test natijasi:** `PYTHONPATH=. pytest -q` → **83 passed** (12 ta yangi Stage 10 testi, shu jumladan yaw-aylanishda `roll3d_deg` o'zgarmasligi, `head_yaw_proxy` gating, `Turned` holatida hold-taymer muzlashi/davom etishi, edge vazn pasayishi, `ctx=None` bilan Stage 9 regressiyasi).

**Ma'lum kamchiliklar:**
- `head_yaw_proxy` faqat 2D proksi; haqiqiy 3D bosh yaw hisoblanmagan (vazifada shunday belgilangan).
- `edge_margin` faqat vazn kamaytiradi, kanalni butunlay o'chirmaydi — chegara holatlarda hali ham kichik ta'sir qolishi mumkin.
- `Config.sanitize()`dagi eski xato (bool maydonlar har doim default'ga tushadi) `use_world`ga ham tegishli — bu Stage 9'dan meros muammo, ushbu stage doirasida tuzatilmadi.

**Real qurilmada sinash qo'llanmasi:**
1. `pip install -e .`, `python -m tgf --calibrate` bilan boshlang.
2. `config.json`da `"use_world": true` qo'ying, monitorni ikkinchi ekranga yoki yon tomonga burilib sinang — overlay'da `yaw=` va `hyaw=` qiymatlarini kuzating.
3. Boshni kadr chetiga yaqinlashtirib (`EDGE` matni chiqishi kerak) yolg'on alert chiqmasligini tekshiring.
4. To'liq yon tomonga burilganda status "Burilgan/Chetda" bo'lishi, keyin normal holatga qaytganda hold-taymer avvalgi joyidan davom etishi kerak (darhol alert bermasligi mumkin, lekin noldan boshlanmaydi).

**Keyingi stage uchun eslatma:** Haqiqiy 3D bosh yaw (nose+ears 3D dan) va `body_yaw_deg` uchun tekshirilgan noise/threshold kalibratsiyasi keyingi bosqichda ko'rib chiqilishi mumkin.
