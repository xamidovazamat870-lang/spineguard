# STAGE 9 REPORT — Shoulder sensitivity: per-channel detection

## Maqsad
Yelka egilishini bosh kabi ishonchli aniqlash; kanal bo'yicha validlik; chapga sezgirroq; sezgirlik presetlari.

## Yangi fayllar
- `tests/test_stage9.py` — 13 ta yangi test (T1–T7 + qo'shimcha unit testlar)

## O'zgargan fayllar
| Fayl | Sabab |
|------|-------|
| `geometry.py` | `Metrics` Optional kanallar; `compute_metrics` per-channel validlik; `neck_deg()` qo'shildi |
| `calibration.py` | `Baseline` sigma maydonlari; `Calibrator` outlier filtri + harakat tekshiruvi; `load/save_baseline` helper |
| `monitor.py` | Fused score S; per-channel `thr_i = max(cfg_i, 3σ_i)·factor·sens`; `State.reason`; kanal uzilishda filter reset yo'q |
| `config.py` | 8 ta yangi maydon; deprecated maydonlar saqlanib, sanitize'da tekshiriladi |
| `pose.py` | Per-point visibility tekshiruvi olib tashlandi (geometriyaga ko'chirildi) |
| `cli.py` | `--sensitivity`, `--model` args; baseline I/O `calibration` moduliga yo'naltirildi |
| `pipeline.py` | `compute_metrics` ga `visibility_min_shoulder` uzatildi; `save_baseline` helper |
| `overlay.py` | Per-channel delta ko'rsatish (sh/hd/nk/ln) |

## Qarorlar
- `neck` = mid-shoulder→mid-ear vektori vertikal burchagi; 3-kanallik tizim uchun eng aniq signal
- `S = Σ w_i·d_i/thr_i` (renormalized) — kanallar yo'q bo'lsa avtomatik kompensatsiya
- `single_strong: |d_i|/thr_i ≥ 1.2` — bitta kanalning kuchli signali yetarli
- `sigma` yo'q JSON: default `sigma=1.0` bilan yuklanadi — orqaga moslik ta'minlandi
- Kanal `None` bo'lsa filter reset qilinmaydi — qisqa uzilishda holat saqlanadi

## Test natijasi
```
69 passed in 1.40s
```
T1–T7 hamda barcha avvalgi testlar o'tdi.

## Ma'lum kamchiliklar
- `neck` kanali aspect ratio parametrisiz hisoblanyapti (pipeline'dan aspect uzatilsa aniqroq)
- `sigma` hisob-kitobi MAD asosida — juda kam namunada noto'g'ri bo'lishi mumkin

## Real qurilmada sinash
```bash
python -m tgf --calibrate --sensitivity high
python -m tgf --model 1 --sensitivity low
```
Yelkalar kadrdan chiqib ketganda ham bosh kanalining ishlashini tekshiring.

## Keyingi stage uchun eslatma
Stage 10: pozitsiya kuzatuvi — foydalanuvchi ekranga yaqinlashganda signal.
