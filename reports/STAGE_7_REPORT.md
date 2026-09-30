# Stage 7 Report — Ogohlantirish ovozini tanlash

## Maqsad
Ovoz, balandlik, takror va chap/o'ng uchun alohida ovozni config/CLI orqali sozlash imkonini berish.

## Yangi fayllar
- `tgf/sounds.py` — `list_system_sounds()`, `resolve_sound(spec)` (tizim nomi yoki fayl yo'li).
- `tests/test_sounds.py` — resolve/list uchun testlar (tmp_path + monkeypatch bilan).

## O'zgargan fayllar
- `tgf/config.py` — `sound`, `sound_left`, `sound_right`, `volume`, `repeat`, `repeat_gap_sec` qo'shildi, `sanitize()`ga clamp qo'shildi. Eski config fayllar `Config.load` orqali default bilan to'ldiriladi — buzilmaydi.
- `tgf/alerts.py` — to'liq qayta yozildi: `fire(side)` chap/o'ng/umumiy ovozni tanlaydi; `tick(now)` thread'siz takror ketma-ketligini yuradi; `preview(spec)` cooldown'siz sinov; ovoz topilmasa `Tink`ga, u ham bo'lmasa `osascript`ga tushadi; `clock` konstruktorga inject qilindi.
- `tgf/cli.py` — `--sound/--volume/--list-sounds/--test-sound` flaglari; `fire()`ga `state.status`dan `side` uzatiladi; asosiy siklga `alerter.tick(now)`; `s` tugmasi — tizim ovozlari bo'ylab aylanadi, sinaydi, `cfg.save(cfg_path)` qiladi; `_Runner`ga `cfg_path` qo'shildi.
- `tgf/overlay.py` — `draw()`ga ixtiyoriy `extra: str = ""`, joriy ovoz nomini oyna pastida ko'rsatadi.
- `tests/test_alerts.py` — `resolve_sound` endi mock qilinadi (sandbox'da `/System/Library/Sounds` yo'q); repeat/volume/side/preview uchun yangi testlar.

## Qarorlar
- Takrorlar thread emas, `tick()` orqali asosiy siklda — talab qilingandek.
- `sound_right=""` bo'lsa `cfg.sound`ga tushadi (side-spetsifik emas, umumiy fallback), talabga mos.
- Ovoz topilmasa avval `Tink`ga urinadi, so'ng `osascript`ga — hech qachon crash yo'q.

## Test natijasi
- `python -m py_compile tgf/*.py tests/*.py` — xatosiz.
- `pytest -q` — 45 test, barchasi o'tdi.
- `python -m tgf --list-sounds` va `--test-sound --sound Glass --volume 0.5` — kamerasiz, xatosiz (`exit=0`), noma'lum ovoz nomi bilan ham crash yo'q.

## Ma'lum kamchiliklar
- Sandbox'da `afplay`/`osascript` yo'q — real chalinish/`-v` argumenti Mac'da tasdiqlanishi kerak.
- `s` tugmasi faqat oynali (non-headless) rejimda ishlaydi.

## Real qurilmada sinash
```bash
python -m tgf --list-sounds
python -m tgf --test-sound --sound Glass --volume 0.5
python -m tgf   # oynada 's' bosib ovozlarni almashtiring, pastda nom ko'rinishi kerak
```

## Keyingi stage uchun eslatma
Stage 8 (silliq ishlash) uchun `monitor.py`ga tegilmadi — yelka/bosh mantig'i o'zgarishsiz qoldi.
