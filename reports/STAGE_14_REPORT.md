# Stage 14 — 3D yaw-invariant metrika

## Nima o'zgardi
1. **geometry.py**: `Metrics` ga ikkita yangi optional maydon qo'shildi:
   `shoulder_yaw_invariant`, `neck_yaw_invariant` (default `None`). `compute_metrics()`
   ga ixtiyoriy `lm3: Optional[Landmarks3D] = None` parametr qo'shildi — berilsa,
   mavjud `roll3d_deg`/`neck3d_deg` chaqirilib yangi maydonlar to'ldiriladi (eski
   visibility gating bilan mos: shoulder_yaw_invariant faqat sh_ok, neck_yaw_invariant
   faqat neck_ok bo'lsa hisoblanadi). Eski 2D maydonlar (shoulder/head/neck/lean)
   va ularning hisoblash mantig'i o'zgarmadi.
2. **pipeline.py**: `process()` da allaqachon olinayotgan `lm3` endi
   `compute_metrics()` ga ham uzatiladi (avval faqat `compute_pose_context()` ga
   borardi).
3. **config.py**: `use_world` default qiymati `False` → `True`. `sanitize()`
   clamp mantig'i tegilmadi (bool maydon, clamp yo'q edi).

## Nega
`roll3d_deg`/`neck3d_deg` funksiyalari mavjud edi, lekin hech qayerda
chaqirilmasdi — asosiy metrika hali ham to'liq 2D edi va yaw (tanani
burish) natijani buzardi. Endi `use_world=True` bilan MediaPipe
`pose_world_landmarks` ishlatiladi va yaw-invariant burchaklar har frame
`Metrics` ichida mavjud bo'ladi (monitor.py ularni Stage 15 da ishlatadi).

## Test natijalari
```
109 passed in 1.51s
```
Yangi testlar (`tests/test_geometry.py`):
- `test_shoulder_yaw_invariant_stable_across_body_yaw` — bir xil real yelka
  og'ish burchagi 0°/20°/40°/-30° yaw bilan proyeksiya qilinganda
  `shoulder_yaw_invariant` farqi < 2° ekanini tasdiqlaydi.
- `test_compute_metrics_without_lm3_leaves_yaw_invariant_none` — `lm3`
  berilmasa yangi maydonlar `None` qolishini (backward compat) tekshiradi.

Barcha eski testlar (test_stage9/10/11, test_monitor, va h.k.) o'zgarishsiz
o'tdi — signature backward compatible.
