# Real qurilmada tekshiruv ro'yxati

Sandbox'da kamera yo'q — bu ro'yxatni real Mac'da, `make install` va `make run` (yoki `--headless`) dan keyin bajaring.

## a) Yelka bilan / yelkasiz egilish
1. To'g'ri o'tiring, kalibratsiyadan o'ting (`c` yoki birinchi ishga tushirish).
2. ~30 s davomida faqat boshni chapga, keyin o'ngga eging (yelka qimirlamasin) — `head` kanali alert berishi kerak.
3. Endi butun yuqori tana bilan (yelka bilan birga) chapga/o'ngga eging — `shoulder`/`neck` kanallari ham qo'shilishi kerak.
4. Kutilgan: ikkala holatda ham `hold_sec` dan keyin tegishli tomon (`Tilt Left`/`Tilt Right`) alert chiqadi; tik o'tirganda qaytadan `Normal`.

## b) Noutbukni surish / burish
1. Normal o'tirgan holatda noutbukni chapga yoki o'ngga ~20-30 sm suring.
2. Keyin noutbukni stol atrofida ~30-45° buring (kamera boshqa burchakdan qaraydi).
3. Kutilgan: `ctx_settle_sec` (standart 4 s) dan keyin tizim yangi joylashuvni tanib oladi yoki yangi profil sifatida jimgina o'rganadi (`auto_reanchor=true`); yolg'on alert chiqmasligi kerak.

## c) Ikkinchi monitorga qarash (bosh burilishi)
1. Asosiy monitor oldida o'tiring, keyin boshni yon tomondagi ikkinchi monitorga burang (tana yaw kam, bosh yaw katta).
2. Kutilgan: `head_yaw_max` dan oshsa `head` kanali vaqtincha o'chadi (`Turned` yoki boshqa kanallar bilan `Normal`), yolg'on tilt-alert chiqmasligi kerak.

## d) Ovozlarni almashtirish
1. `make sounds` (yoki `python -m tgf --list-sounds`) bilan mavjud tizim ovozlarini ko'ring.
2. Debug oynada `s` tugmasi bilan keyingi ovozga o'ting (sinaydi + saqlaydi) yoki `--sound NAME --test-sound` bilan oldindan sinang.
3. Kutilgan: tanlangan ovoz keyingi alertlarda eshitiladi; noto'g'ri nom `Tink`ga tushadi, keyin bildirishnomaga.

## e) `--stats` p95 va CPU%
1. `python -m tgf --stats` bilan ishga tushiring; har 5 s stderr'ga p50/p95 inference/capture kechikishi chiqadi.
2. Alohida terminalda `top -pid $(pgrep -f "python -m tgf")` (yoki Activity Monitor) bilan CPU% ni kuzating.
3. Kutilgan: `model_complexity=0` da CPU past (bir nechta % darajasida past-quvvat Mac'larda), p95 sezilarli sakrashsiz.

## f) 10 daqiqa jim o'tirish — yolg'on alert soni
1. Kalibratsiyadan so'ng, mumkin qadar tik va harakatsiz ~10 daqiqa o'tiring (`--log jim.csv` bilan yozib oling).
2. Kutilgan: 0 ta alert (yoki juda kam). Agar ko'p bo'lsa: `python -m tools.replay jim.csv` bilan qaysi kanal/sabab trigger qilayotganini ko'ring, so'ng `sensitivity`ni pasaytiring yoki tegishli `*_deg`/`*_factor`ni oshiring.
