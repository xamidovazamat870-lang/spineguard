# Stage 14 Report: 3D Yaw-Invariant Metrics Integration

## Nima o'zgardi:
- `tgf/geometry.py`: `compute_metrics()` ga `lm3` parametri qo'shildi; `shoulder_yaw_invariant` va `neck_yaw_invariant` hisob-kitobi ulandi.
- `tgf/pipeline.py`: `process()` oqimida `lm3` metrikani hisoblash funksiyasiga uzatildi.
- `tgf/config.py`: `use_world: bool = True` qilib belgilandi.
- `tests/test_geometry.py`: 3D landmarklar orqali yaw o'zgarganda ham yelka burchagi barqaror qolishini tekshiruvchi test qo'shildi.

## Natijalar:
- Barcha testlar muvaffaqiyatli o'tdi (109 passed).
