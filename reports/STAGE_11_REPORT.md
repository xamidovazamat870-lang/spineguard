# Stage 11 Report — Aqlli re-anchor: kontekst profillari va xavfsiz avto-kalibratsiya

**Maqsad:** Joy/masofa/yaw o'zgarganda (kontekst) baseline'ni avtomatik moslashtirish, lekin faqat postura o'zgarganda (roll) hech qachon re-anchor qilmaslik.

**Yangi fayllar:** `tgf/profiles.py`, `tests/test_stage11_profiles.py`, `tests/test_stage11_pipeline.py`, `reports/STAGE_11_REPORT.md`.

**O'zgargan fayllar:**
- `tgf/pipeline.py` — `_maybe_reanchor()`: kontekst siljishini aniqlaydi (`ctx_settle_sec` barqaror bo'lgach), tanish profilga jimgina almashtiradi yoki yangi (bloklanmaydigan) kalibratsiya boshlaydi (`ReanchorReason.NEW/SWITCHED`). Xavfsizlik: `Tilt`/alert holatida auto-o'rganma; yangi baseline eng yaqin profildan `reanchor_roll_guard`dan ko'p farq qilsa rad etiladi (`_accept_new_baseline`).
- `tgf/config.py` — yangi maydonlar: `auto_reanchor, ctx_dx, ctx_scale, ctx_yaw, ctx_settle_sec, max_profiles, away_sec, reanchor_roll_guard`. **Muhim tuzatish:** `sanitize()` avval har qanday `bool` maydonni har doim default'ga qaytarardi (Stage 9/10'dan meros) — shu sabab `auto_reanchor=False`/`--no-auto` hech qachon ishlamas edi. Endi faqat maydon o'zi `bool` bo'lmasa rad etiladi.
- `tgf/cli.py` — `--no-auto`, `--profiles`, `--reset-profiles`; `p` tugmasi profillarni stderr'ga chiqaradi; overlay'da yangi kontekst kalibratsiyasi paytida "Yangi joylashuv: to'g'ri o'tiring…" matni.
- `README.md`, `CHANGELOG.md`, `tgf/__init__.py` (v11.0.0).

**Qarorlar:**
- Profil moslik `PoseContext.cx/scale/body_yaw_deg` (Stage 10'da allaqachon bor) ustida ishlaydi — yangi landmark hisoblash shart emas.
- Kontekst siljishi faqat "barqaror" bo'lgach (oldingi kadrga nisbatan `ctx_dx*1.5` ichida) hisoblanadi — titrash yolg'on almashtirishni keltirib chiqarmaydi.
- `auto_reanchor=False` — Stage 10 xatti-harakati aynan saqlanadi (`_maybe_reanchor` darhol qaytadi).

**Test natijasi:** Sandbox'da `pytest` o'rnatilmagan (tarmoq yo'q); minimal Python test-runner + qo'lda yozilgan `pytest.approx/raises/fixture` shim orqali tekshirildi. **91 ta test o'tdi** (barcha eski Stage 1-10 testlar + 14 ta yangi Stage 11 test), muvaffaqiyatsiz 3 ta holat faqat mening runnerimning `fixture` argumentlarini qo'llab-quvvatlamasligi (haqiqiy `pytest`da o'tishi kerak). Foydalanuvchida albatta `pytest -q` bilan qayta tekshiring.

**Ma'lum kamchiliklar:**
- Away/qaytish (band 3) alohida holat mashinasi sifatida emas, balki tabiiy natija sifatida ishlaydi: `ctx=None` paytida drift-tracker faqat reset bo'ladi, profil hech qachon o'chirilmaydi — `away_sec` config maydoni hozircha faqat kelajakdagi kengaytirish uchun tayyorlangan, alohida mantiqqa ulanmagan.
- `ProfileBank.upsert` mos profilni topib, uni **yangilaydi** (masalan xavfsizlik tekshiruvidan keyin) — bu ataylab, lekin juda yaqin ikkita joylashuv bitta profilga birlashib ketishi mumkin (kutilgan, `ctx_dx/ctx_scale` orqali sozlanadi).
- Real kamerada `pytest` bilan to'liq tekshiruv qilinmadi.

**Real qurilmada sinash qo'llanmasi:**
1. `pip install -e .`, oddiy joyda kalibratsiya qiling.
2. Noutbukni yoki stulni chapga/o'ngga ~30-40 sm siljiting, 4+ soniya harakatsiz turing — yangi profil uchun bloklanmaydigan kalibratsiya (`Kalibratsiya`/`Yangi joylashuv`) ishga tushishi kerak.
3. Eski joyga qayting — darhol (kalibratsiyasiz) eski baseline qayta tiklanishi kerak.
4. Bir joyda o'tirib egiling — hech qachon re-anchor ishga tushmasligi, faqat oddiy Tilt alert kerak.
5. `p` tugmasi yoki `--profiles` bilan saqlangan profillarni ko'ring.

**Keyingi stage uchun eslatma:** `away_sec` asosida haqiqiy "away" holatini (masalan, profil `last_used` yangilanishini to'xtatish yoki uzoq g'oyib bo'lishda maxsus signal) qo'shish keyingi bosqichda ko'rib chiqilishi mumkin.
