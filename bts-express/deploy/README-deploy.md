# BTS Express - AWS'ga joylash qo'llanmasi

Loyiha turi: **TPS** (tranzaksiyalarni qayta ishlash tizimi - pochta buyurtmalari). Provayder: **AWS**.
Resurslarni **o'z AWS akkauntingizda** yaratasiz (boshqa talabaning akkauntidan foydalanish qabul qilinmaydi).

## 0. Tayyorgarlik
1. AWS akkaunt, **root bilan ishlamang**: IAM Identity Center yoki IAM foydalanuvchi yarating (MFA yoqing) va unga CLI uchun yetarli huquq bering.
2. Kompyuteringizda [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) o'rnating va `aws configure` (yoki `aws sso login`) qiling. **Access key'ni hech qayerga (GitHub, hisobot, chat) yozmang.**
3. `cp deploy/config.env.example deploy/config.env` va tahrirlang (S3 nomi noyob bo'lishi kerak, email, region). `config.env` .gitignore'da.

## 1. Bir buyruq bilan yaratish
    bash deploy/01-create-aws.sh
Skript quyidagilarni yaratadi (10-15 daqiqa, asosan RDS kutiladi):

| # | Resurs | Tafsilot |
|---|--------|----------|
| 1 | Security Groups | `web` (80, 443 hamma; 22 faqat `SSH_CIDR` berilsa) va `db` (5432 faqat `web` SG dan) |
| 2 | S3 bucket | Public access to'liq bloklangan, SSE-AES256, `exports/` 30 kunda o'chadi |
| 3 | Secrets Manager | `bts-express/admin` (tasodifiy admin paroli); RDS master paroli ham avtomatik shu yerda |
| 4 | RDS PostgreSQL | `db.t4g.micro`, 20 GB, shifrlangan, **ochiq emas**, 7 kunlik zaxira, Single-AZ (arzon) |
| 5 | IAM rol | `ec2-app-policy.json.tpl`: S3 faqat `bts/*`, 2 ta sirni o'qish, faqat `BTSExpress`/`CWAgent` metrikalari, o'z log guruhi |
| 6 | EC2 | Amazon Linux 2023, `t3.micro`, IMDSv2 majburiy, shifrlangan disk, Elastic IP; user-data ilovani o'rnatadi (nginx + systemd + CloudWatch agent) |
| 7 | CloudWatch alarmlar | EC2 CPU, status check, ilova 5xx xatolari, RDS CPU, RDS bo'sh joy -> SNS email |
| 8 | Budget | oyiga `BUDGET_USD` dan 80% oshsa email |

Skript oxirida ilova manzili chiqadi: `http://<Elastic IP>/`. Admin parolini olish:

    aws secretsmanager get-secret-value --secret-id bts-express/admin --query SecretString --output text

SNS xabarnomasi uchun emailingizga kelgan **tasdiqlash xatini** bosing.

## 2. Tekshirish va hisobot uchun dalillar
Admin sifatida kiring -> **Bulut holati** sahifasi:
- "Tekshirishni boshlash" - DB yozish/o'qish, S3 put/get/delete, CloudWatch metrika (skrinshot: **DB ulanishi** va **S3 ishlatilishi** dalili).
- Buyurtma yarating, unga rasm yuklang, "eksport" tugmasini bosing, so'ng AWS konsolida S3 bucket ichidagi `bts/orders/...` va `bts/exports/...` ni ko'rsating (skrinshot).
- EC2 konfiguratsiyasi: konsolda Instance details yoki `aws ec2 describe-instances`; serverda `cat /etc/os-release`, `systemctl status bts-express nginx` (Session Manager orqali).
- Security Group va IAM: konsolda `bts-express-web`, `bts-express-db` inbound rules, `bts-express-ec2-role` -> Permissions (skrinshot).
- Monitoring: CloudWatch -> All metrics -> `BTSExpress` (Requests, OrdersCreated...) yoki EC2 CPU grafigi; Logs -> `/bts-express/app` (skrinshot).
- Himoyadan oldin kichik "yuk" bering (bir necha buyurtma) - grafiklar bo'sh bo'lmasin; metrikalar har 60 soniyada yuboriladi.

## 3. Serverga kirish (SSH ochmasdan)
EC2 roli `AmazonSSMManagedInstanceCore` bilan ta'minlangan: Konsol -> EC2 -> instance -> **Connect -> Session Manager**.
Loglar: `sudo tail -f /var/log/bts-express/app.log` (JSON qatorlar), o'rnatish logi: `/var/log/bts-userdata.log`.

## 4. Ilovani yangilash
Kodni o'zgartirgach: zipni qayta yuklash (`aws s3 cp` -> `s3://BUCKET/deploy/app.zip`), serverda
`aws s3 cp s3://BUCKET/deploy/app.zip /tmp/app.zip && sudo unzip -oq /tmp/app.zip -d /opt/bts-express && sudo systemctl restart bts-express`.

## 5. HTTPS (ixtiyoriy, tavsiya)
Domeningiz bo'lsa: DNS'da A yozuvini Elastic IP'ga qarating, `config.env`'da `DOMAIN=` ni to'ldiring (yaratishdan oldin) - user-data Let's Encrypt sertifikatini oladi.
Domen bo'lmasa HTTP bilan ishlaydi (login/parol ochiq uzatiladi - hisobotda bu cheklov sifatida yozing).

## 6. Mavjud JSON ma'lumotni RDS'ga ko'chirish (kerak bo'lsa)
Serverda (Session Manager): `cd /opt/bts-express && sudo -u bts env $(cat /etc/bts-express.env | xargs) venv/bin/python migrate.py /path/db.json`

## 7. Xarajat va tozalash
- Taxminiy xarajat (eu-central-1): EC2 t3.micro + RDS db.t4g.micro + Elastic IP (public IPv4 pullik) ~ oyiga $25-35, Free Tier bo'lsa kamroq. **Faqat himoya davrida ishlating.**
- **Himoyadan keyin o'qituvchi ko'rsatmasiga binoan hammasini o'chiring:** `bash deploy/teardown.sh` (so'ng konsolda EC2, RDS, S3, Elastic IP qolmaganini tekshiring).

## Ochiq portlar va sabablari (hisobot/himoya uchun)
| Port | Kimga | Nima uchun |
|------|-------|------------|
| 80 | 0.0.0.0/0 | HTTP: foydalanuvchilar brauzerdan kiradi; sertifikat olish; HTTPS'ga yo'naltirish |
| 443 | 0.0.0.0/0 | HTTPS (domen bo'lsa) |
| 22 | yopiq (yoki faqat sizning IP/32) | Administrator kirishi. Standart: yopiq, Session Manager ishlatiladi |
| 5432 | faqat `web` SG | Ilova serveri -> PostgreSQL. Internetdan kirib bo'lmaydi |
| 8000 | hech kimga | Ilova faqat 127.0.0.1'da; tashqariga nginx orqali chiqadi |

## Xavfsizlik choralari (qisqacha)
Parollar Secrets Manager'da (kodda/GitHub'da yo'q) · EC2 -> AWS ruxsatlari IAM rol orqali (access key yo'q) · minimal IAM huquqlari · DB ochiq emas va SG bilan cheklangan, TLS (`sslmode=require`) · S3 yopiq, shifrlangan, 5 daqiqalik presigned havolalar · IMDSv2 · nginx rate-limit (login 10/daq) · ilova login urinishlarini cheklaydi · yuklanadigan fayl turi/hajmi/mazmuni tekshiriladi · diskning shifrlanishi · CloudWatch alarmlar va budget.

## Cheklovlar (halol eslatma)
Bu skriptlar va kod haqiqiy AWS'da **men tomondan sinab ko'rilmagan** (AWS akkaunt yo'q). PostgreSQL SQL'i haqiqiy PostgreSQL 16'da, boto3 chaqiruvlari soxta boto3 bilan, skript oqimi soxta `aws` bilan sinalgan. Birinchi ishga tushirishda xato chiqsa: `/var/log/bts-userdata.log` va `/var/log/bts-express/app.log` ni ko'ring.
