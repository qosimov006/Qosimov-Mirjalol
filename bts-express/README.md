# BTS Express Pochta Tizimi

Texnologiyalar: HTML, CSS, JavaScript (frontend) · Python (backend, standart kutubxona) · ma'lumotlar bazasi: JSON fayl (lokal) yoki PostgreSQL / Amazon RDS (bulut) · fayllar: Amazon S3.

**Bulutga joylash (Bulutli texnologiyalar fani):** [deploy/README-deploy.md](deploy/README-deploy.md) · sxema: [docs/architecture.svg](docs/architecture.svg)

## Ishga tushirish

**Windows:** `start.bat` ni ikki marta bosing (Python o'rnatilgan bo'lishi kerak: python.org). **Linux/Mac:** `./start.sh`.
`index.html` ni to'g'ridan-to'g'ri ochmang — tizim `server.py` orqali, `http://localhost:8000` manzilida ishlaydi.
Terminal oynasi ochiq turishi kerak: yopsangiz, server to'xtaydi ("Failed to fetch" xatosi shundan chiqadi).

    python server.py           # Windows (Linux/Mac: python3 server.py) -> http://localhost:8000
    PORT=9000 python3 server.py  # boshqa port

Birinchi ishga tushishda `data/db.json` avtomatik yaratiladi. Har ishga tushishda `data/backup/` ga kunlik nusxa olinadi (oxirgi 14 ta).

Demo: `admin/admin123` · `operator/operator123` · `kuryer1/kuryer123` — **ishga tushirgach parollarni o'zgartiring** (tepadagi ism ustiga bosing).

## Imkoniyatlar

- **Bosh sahifa**: buyurtma raqami bo'yicha ochiq kuzatuv (bosqichlar + tarix; shaxsiy ma'lumot ko'rsatilmaydi).
- **Dizayn**: barcha rollar uchun BTS uslubidagi qobiq (to'q yuqori panel, chap menyu, kartochkali bosh sahifa).
- **Tarif**: admin "Tariflar" sahifasida boshlang'ich narx, bepul og'irlik, har kg narxi va yaxlitlashni belgilaydi; operator formasida narx og'irlikka qarab avtomatik chiqadi (qo'lda o'zgartirsa bo'ladi). Boshlang'ich qiymatlar namuna — o'zingizniki bilan almashtiring.
- **Pochta qabul qilish (operator)**: BTS oynasiga o'xshash ikki panelli forma — chapda yuboruvchi (viloyat/tuman/filial, jo'natma turi, paket, vazn, o'lchamlar va hajm, kuryer), o'ngda qabul qiluvchi (Tel1/Tel2, hudud, eshikkacha yetkazib berish) va elektron chek (summa, QQS, to'lov turi). Summa tarif bo'yicha avtomatik hisoblanadi. Saqlash / Nusxalash / Yopiq tugmalari bor.
- **Shaxsiy hisob**: mijoz balansi (to'ldirish, operatsiyalar tarixi). To'lov turi "Balans" bo'lsa summa hisobdan yechiladi, buyurtma bekor qilinsa qaytariladi.
- **Kuryerga berish (operator)**: kuryersiz buyurtmalarni tanlab, bir martada kuryerga biriktirish.
- **Hududlar**: barcha 14 viloyat, ularning shaharlari va tumanlari (205 ta) tayyor; admin "Ma'lumotnomalar"da o'zgartira oladi.
- **Ma'lumotnomalar (admin)**: hududlar, filiallar, jo'natma turlari, paketlar, to'lov va transport turlari, tashkilot rekvizitlari. Ro'yxatlar namuna — o'zingiznikiga moslang.
- **Operator**: buyurtmalar, mijozlar bazasi (avtomatik to'ldirish), buyurtmalar ro'yxati, mijozlar bazasi, yo'lxat chop etish.
- **Kuryer** (telefonga mos): faqat o'z buyurtmalari, qo'ng'iroq va xarita havolalari, holat yangilash, bekor qilish sababi, kunlik statistika.
- **Admin**: umumiy statistika va 7 kunlik grafik, barcha buyurtmalar (qidiruv, holat/sana/kuryer filtri, sahifalash, CSV eksport), tahrirlash/o'chirish/kuryer biriktirish, foydalanuvchilarni boshqarish.
- **Xavfsizlik**: PBKDF2 parol xeshi, 12 soatlik sessiya, login urinishlarini cheklash, rollar bo'yicha ruxsat, kiritishni tekshirish.

## Bulut rejimi

Lokal ishga tushirishda hech narsa o'zgarmaydi. Bulutda muhit o'zgaruvchilari bilan yoqiladi (qarang: `cloud.py` boshidagi izoh):
`BTS_STORAGE=postgres` (RDS), `S3_BUCKET` (fayllar), `CW_NAMESPACE` (CloudWatch metrikalari), `DB_SECRET_ID`/`ADMIN_SECRET_ID` (parollar Secrets Manager'da).
Parol va kalitlar kodda yo'q; AWS ruxsatlari EC2'ga biriktirilgan IAM rol orqali beriladi.
Qo'shimcha endpointlar: `/api/health` (salomatlik), admin uchun "Bulut holati" sahifasi (DB/S3/CloudWatch tekshiruvi), buyurtmaga fayl yuklash (S3), CSV eksport (S3).

## Testlar

    python3 tests/test_api.py   # API (vaqtinchalik baza bilan)
    python3 tests/ui_check.py   # brauzer testi (Playwright kerak)
    python3 tests/test_cloud.py # bulut qatlami: SQLite, PostgreSQL (psql kerak), S3/CloudWatch (soxta boto3, tests/fakes)
