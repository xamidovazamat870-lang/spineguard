# Stage 13 — Ko'z chizig'i (Face Mesh)

- geometry.py: Landmarks'ga left_eye/right_eye; compute_metrics bosh og'ishi (hd), bo'yin (nk), lean ko'zdan hisoblanadi (ko'rinmasa quloqqa qaytadi)
- pose.py: Pose landmark 2/5 + Face Mesh (refine_landmarks) ko'z markazlari (263/362 va 33/133); Face Mesh topilmasa Pose ko'zlari
- overlay.py: yuzdagi chiziq ko'zlar ustida chiziladi
- Eslatma: kalibratsiyani qayta qiling (C). Tekshirildi: foydalanuvchi qo'lda ishlatib ko'rdi, ishlaydi.
- Ochiq: yelka chizig'i ko'krak ichida (sh sezgirligi past); Face Mesh yuki (kerak bo'lsa har 2-kadrda)
