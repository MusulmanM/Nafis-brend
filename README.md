# Nafis — suv zavodi boshqaruv tizimi

Filtrlangan ichimlik suvi ishlab chiqaradigan va yetkazib beradigan zavod uchun ichki veb-sayt.
Interfeys o'zbek tilida (lotin), telefon uchun qulay (mobile-first).

**Imkoniyatlar**

- **Boshliq paneli:** bosh sahifa (bugungi ko'rsatkichlar va 7 kunlik tushum grafigi), buyurtmalar, mijozlar, qarzdorlar, butil (tara) hisobi, ombor, mahsulotlar va narxlar, yetkazuvchilar, doimiy buyurtmalar.
- **Hisobotlar:** kunlik, haftalik, oylik yoki istalgan sana oralig'i uchun. Grafiklar bor va natijani Excel'ga yuklab olish mumkin.
- **Yetkazuvchi paneli (telefon uchun):** bugungi buyurtmalar, qo'ng'iroq qilish, xaritada ochish, "Yo'lga chiqdim", "Yetkazib berdim", "Yetkazib bo'lmadi" tugmalari va "Mening kunim" sahifasi.
- Buyurtma yetkazilganda mijozning qarzi va butil balansi **avtomatik** yangilanadi. Tugma ikki marta bosilsa ham bir marta hisoblanadi.

Texnologiyalar: Python 3.11+, Django 5, SQLite (PostgreSQL'ga o'tish mumkin), Bootstrap 5, Chart.js, openpyxl.

---

## 1. O'rnatish va ishga tushirish

Kerak bo'ladi: **Python 3.11 yoki yangiroq** ([python.org](https://www.python.org/downloads/)).
Windows'da o'rnatayotganda **"Add python.exe to PATH"** belgisini qo'yishni unutmang.

### Linux / macOS

```bash
cd Nafis-brend                      # loyiha papkasiga o'ting

python3 -m venv .venv               # virtual muhit yaratish (bir marta)
source .venv/bin/activate           # virtual muhitni yoqish (har safar yangi terminalda)

pip install -r requirements.txt     # kutubxonalarni o'rnatish

cp .env.example .env                # sozlamalar faylini yaratish
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
# ↑ chiqqan matnni .env faylidagi SECRET_KEY= qatoriga qo'ying

python manage.py migrate            # ma'lumotlar bazasini yaratish
python manage.py createsuperuser    # boshliq akkaunti (login va parol so'raladi)
python manage.py runserver          # serverni ishga tushirish
```

### Windows (PowerShell)

```powershell
cd Nafis-brend

python -m venv .venv
.venv\Scripts\Activate.ps1
# Agar "running scripts is disabled" xatosi chiqsa, bir marta bajaring:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# (cmd.exe ishlatsangiz:  .venv\Scripts\activate.bat)

pip install -r requirements.txt

copy .env.example .env
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
# ↑ chiqqan matnni .env faylidagi SECRET_KEY= qatoriga qo'ying (Bloknot bilan oching)

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Brauzerda oching: **http://127.0.0.1:8000**. Serverni to'xtatish uchun `Ctrl+C` ni bosing.

### Demo ma'lumotlar (ixtiyoriy)

Hisobot va grafiklarni darhol ko'rish uchun quyidagi buyruqni bajaring:

```bash
python manage.py seed_demo
```

Bu buyruq 2 ta yetkazuvchi, 20 ta mijoz, 3 ta mahsulot, 30 kunlik buyurtmalar, qarz to'lovlari, ombor yozuvlari va 3 ta doimiy buyurtma yaratadi.

- Yetkazuvchilar: `jasur` va `bekzod`, ikkalasining paroli `parol123`.
- Agar bazada boshliq bo'lmasa, `admin` / `admin12345` yaratiladi.
- Bazada ma'lumot bo'lsa, buyruq ishlamaydi. Hammasini **o'chirib**, qaytadan yaratish uchun: `python manage.py seed_demo --reset`.

> ⚠️ `--reset` barcha buyurtma, mijoz, to'lov, ombor va mahsulot yozuvlarini o'chiradi. Haqiqiy ma'lumotlar bilan ishlatmang!

### Telefondan ochish (bir Wi-Fi tarmog'ida)

1. Kompyuterning IP manzilini bilib oling: Linux'da `ip a`, Windows'da `ipconfig` (masalan, `192.168.1.10`).
2. `.env` faylida shu IP'ni qo'shing: `ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.10`.
3. Serverni barcha manzillar uchun ishga tushiring: `python manage.py runserver 0.0.0.0:8000`.
4. Telefonda oching: `http://192.168.1.10:8000`.

---

## 2. Foydalanish

Hamma bitta login sahifasidan kiradi, tizim esa rolga qarab yo'naltiradi:

| Rol | Kirgandan keyin | Nima qila oladi |
|---|---|---|
| **Boshliq** | `/panel/` | Hamma narsa |
| **Yetkazuvchi** | `/driver/` | Faqat o'ziga biriktirilgan buyurtmalar |

Yetkazuvchi boshliq sahifalariga kira olmaydi (server 403 qaytaradi). Bloklangan foydalanuvchi esa umuman tizimga kira olmaydi.

**Boshliq uchun ish tartibi**

1. **Mahsulotlar** bo'limida 19L, 5L, 1.5L ni narxi bilan qo'shing. 19L uchun "Qaytariladigan butil" belgisini qo'ying.
2. **Yetkazuvchilar** bo'limida yetkazuvchilarni qo'shing va ularga login/parol bering.
3. **Buyurtmalar → Yangi buyurtma** sahifasida mijoz telefonini yozing. Mijoz topilsa, kartasi chiqadi. Topilmasa, shu joyning o'zida ism va manzil kiritib yangi mijoz qo'shiladi.
4. **Ombor** bo'limida har kuni ishlab chiqarilgan miqdorni kiriting.
5. **Qarzdorlar** bo'limida qarz to'lovini qabul qiling.
6. **Butillar** bo'limida qaysi mijozda nechta butil turganini ko'ring. Mijozdagi butillar u yerda qolib ketmasligi uchun:
   - **"2 haftadan beri buyurtmasiz"** filtri buyurtma bermay qo'ygan, ya'ni butili qolib ketgan mijozlarni ko'rsatadi;
   - **Olib kelish** — yetkazuvchiga "shu mijozdan bo'sh butillarni olib kel" topshirig'i beriladi (yetkazuvchi va sana tanlanadi);
   - **Qabul qilish** — mijoz butillarni o'zi zavodga olib kelganda darhol yoziladi.
   Ikkala tugma mijoz sahifasida ham bor. Ochiq topshiriqni "Bekor qilish" bilan bekor qilsa bo'ladi.
7. **Hisobotlar** bo'limida davrni tanlang va kerak bo'lsa "Excel'ga yuklab olish" tugmasini bosing.

**Yetkazuvchi uchun ish tartibi** (telefonda)

1. **Buyurtmalar** — bugungi va kechikkan buyurtmalar kartochkalari. Telefon raqami bosilsa, qo'ng'iroq boshlanadi. Xarita tugmalari Yandex yoki Google xaritani ochadi.
2. **Yo'lga chiqdim** bosilganda holat "Yo'lda" ga o'zgaradi.
3. **Yetkazib berdim** bosilganda oyna ochiladi: to'lov turi, olingan summa va qaytarilgan bo'sh butillar kiritiladi. Tasdiqlangach, qarz va butillar avtomatik yangilanadi.
4. **Yetkazib bo'lmadi** bosilganda sabab tanlanadi: uyda yo'q, telefon ko'tarmadi, manzil noto'g'ri yoki boshqa (izoh bilan).
5. **Butillarni olib kelish** — boshliq bergan topshiriqlar buyurtmalar ostida alohida kartochkada chiqadi. **Olib keldim** bosilib, nechta bo'sh butil olingani kiritiladi (mijozdagi butillar avtomatik kamayadi) yoki **Bo'lmadi** bilan sabab ko'rsatiladi.
6. **Mening kunim** sahifasida nechta yetkazilgani, nechtasi qolgani, qancha butil qaytgani va kassaga topshiriladigan naqd pul ko'rinadi.

Yetkazishda mijozda ortiqcha eski butil bo'lsa, "Yetkazib berdim" oynasida **"Hammasi: N ta"** tugmasi chiqadi: u bilan hamma eski butillarni bir bosishda qaytarib olingan deb belgilash mumkin.

**Django admin panel** (`/admin/`) zaxira boshqaruv uchun. Qarz, butil va buyurtma holatini o'zgartiradigan maydonlar u yerda faqat o'qish uchun ochiq, shunda balans buzilmaydi.

---

## 3. Doimiy buyurtmalar (avtomatik)

Boshliq **Doimiy buyurtmalar** bo'limida mijoz, hafta kunlari va mahsulotlarni belgilaydi. Shu kunlar uchun buyurtmalarni quyidagi buyruq yaratadi:

```bash
python manage.py create_recurring_orders                  # bugun uchun
python manage.py create_recurring_orders --date 2026-11-10
python manage.py create_recurring_orders --days 3         # bugun, ertaga, indinga
```

Buyruqni ikki marta ishga tushirish xavfsiz: bir kunga ikkinchi buyurtma yaratilmaydi.
Panelda **"Bugungi buyurtmalarni yaratish"** tugmasi ham bor.

**Har kuni ertalab avtomatik ishga tushirish**

*Linux (cron):* `crontab -e` buyrug'ini bajarib, quyidagi qatorni qo'shing (har kuni soat 06:00 da):

```
0 6 * * * cd /yo'l/Nafis-brend && .venv/bin/python manage.py create_recurring_orders >> recurring.log 2>&1
```

*Windows (Task Scheduler — "Vazifalar rejalashtiruvchisi"):*

1. "Create Basic Task" → nom bering → **Daily**, soat 06:00.
2. Action: **Start a program**.
   - Program: `C:\yo'l\Nafis-brend\.venv\Scripts\python.exe`
   - Arguments: `manage.py create_recurring_orders`
   - Start in: `C:\yo'l\Nafis-brend`

---

## 4. Hisob-kitob qoidalari

- **Qarz:** yetkazilganda `qarz += buyurtma summasi − olingan summa`. Olingan summa katta bo'lsa (mijoz eski qarzini ham bersa), qarz kamayadi. Qarz hech qachon manfiy bo'lmaydi.
- **Butillar:** yetkazilganda `mijozdagi butillar += berilgan to'la butillar − qaytarilgan bo'shlar`. Faqat "qaytariladigan" mahsulotlar (19L) hisobga olinadi.
- **Buyurtmasiz butil qaytarish** (olib kelish topshirig'i yoki mijoz o'zi olib kelgani): `mijozdagi butillar −= olib kelingan soni`. Topshiriq berilganda balans o'zgarmaydi, faqat "Olib keldim" bosilganda o'zgaradi. Mijozda bor sondan ko'p qaytarib bo'lmaydi. Bitta mijozga bir vaqtda faqat bitta ochiq topshiriq beriladi. Hisobotlarda bu butillar "qaytarilgan" butillarga qo'shiladi va olib kelingan kun bo'yicha hisoblanadi.
- **Ombor qoldig'i** = jami ishlab chiqarilgan − jami yetkazilgan.
- **Narx** buyurtma paytida saqlanadi: mahsulot narxi keyin o'zgarsa ham, eski buyurtmalar summasi o'zgarmaydi.
- **Hisobotlarda sanalar:**
  - buyurtmalar **soni** yetkazish sanasi bo'yicha hisoblanadi;
  - **pul** esa haqiqatda olingan kuni bo'yicha: yetkazilgan vaqt va qarz to'lovi sanasi.
- **Ikki marta bosishdan himoya:**
  - qarz va butil hisob-kitoblari `transaction.atomic()` ichida bajariladi;
  - holat shartli UPDATE bilan o'zgaradi ("faqat hali yakunlanmagan bo'lsa");
  - to'lov, butil qabul qilish, olib kelish topshirig'i va yangi buyurtma formalarida bir martalik kalit bor.

---

## 5. Loyiha tuzilmasi

```
Nafis-brend/
├── config/            Sozlamalar (settings.py), asosiy URL'lar
├── core/              Umumiy yordamchilar
│   ├── phone.py         Telefon: +998 XX XXX XX XX formati va tekshiruvi
│   ├── forms.py         Bootstrap formalari, sana va summa maydonlari
│   ├── templatetags/    {{ summa|som }} → "125 000 so'm" kabi filtrlar
│   └── management/commands/seed_demo.py
├── accounts/          Foydalanuvchi (rol: boshliq/yetkazuvchi), login, yetkazuvchilar
│   └── decorators.py    @boss_required, @driver_required — ruxsat tekshiruvi
├── customers/         Mijozlar, qarz to'lovlari, qarzdorlar, butil hisobi va butil qaytarish
│   └── services.py      accept_payment() — qarz to'lovi
├── inventory/         Mahsulotlar, ombor (ishlab chiqarish va qoldiq)
├── orders/            Buyurtmalar, doimiy buyurtmalar, yetkazuvchi paneli
│   ├── services.py      create_order(), mark_delivered(), ... — balans shu yerda o'zgaradi
│   ├── driver_views.py  Yetkazuvchi paneli sahifalari
│   ├── recurring.py     Doimiy buyurtmalardan buyurtma yaratish
│   └── management/commands/create_recurring_orders.py
├── reports/           Bosh sahifa, hisobotlar, Excel eksport
│   ├── stats.py         Barcha hisob-kitoblar
│   └── excel.py         .xlsx fayl yaratish
├── templates/         HTML shablonlar (layouts/ — boshliq va yetkazuvchi karkasi)
├── static/            CSS va JavaScript
├── deploy/            AWS/Ubuntu serverga joylash skriptlari (deploy.sh, setup_server.sh)
├── .env.example       Sozlamalar namunasi (.env ga nusxa oling)
└── requirements.txt   Kerakli kutubxonalar
```

Har bir app ichida:

| Fayl | Vazifasi |
|---|---|
| `models.py` | Bazadagi jadvallar |
| `views.py` | Sahifalar |
| `forms.py` | Formalar va tekshiruv (validatsiya) |
| `urls.py` | Manzillar |
| `admin.py` | Django admin |
| `services.py` | Pul va holatni o'zgartiradigan amallar |
| `tests.py` | Avtomatik testlar |

---

## 6. Testlar

```bash
python manage.py test
```

Testlar quyidagilarni tekshiradi:
- ruxsatlar;
- qarz va butil hisob-kitobi (buyurtmasiz butil qaytarish ham);
- ikki marta bosilganda ikki marta hisoblanmasligi;
- validatsiya;
- hisobot va Excel;
- doimiy buyurtmalar;
- `seed_demo` dan keyin balanslarning to'g'riligi.

---

## 7. PostgreSQL'ga o'tish

1. PostgreSQL drayverini o'rnating: `pip install "psycopg[binary]"`.
2. PostgreSQL'da baza yarating, masalan `nafis`.
3. `.env` faylida quyidagilarni yozing:
   ```
   DB_ENGINE=postgres
   DB_NAME=nafis
   DB_USER=postgres
   DB_PASSWORD=parolingiz
   DB_HOST=localhost
   DB_PORT=5432
   ```
4. `python manage.py migrate` va `python manage.py createsuperuser` buyruqlarini bajaring.

SQLite'dagi ma'lumotlarni ko'chirish uchun: oldin `python manage.py dumpdata --natural-foreign --exclude contenttypes --exclude auth.permission > data.json`, keyin yangi bazada `python manage.py loaddata data.json`.

---

## 8. AWS serverga joylash (avtomatik)

`deploy/` papkasidagi skriptlar loyihani Ubuntu serverga (masalan, AWS EC2) bitta buyruq bilan joylaydi:
nginx + gunicorn, HTTPS sertifikat (Let's Encrypt), doimiy buyurtmalar uchun cron.

**Serverdan oldin (AWS konsolida):**
1. EC2 server — Ubuntu 22.04 yoki 24.04.
2. Security Group'da **22** (SSH), **80** (HTTP) va **443** (HTTPS) portlar ochiq bo'lsin.
3. Server qayta yonganda IP o'zgarmasligi uchun **Elastic IP** biriktiring (aks holda domen ishlamay qoladi).

**Joylash** (o'z kompyuteringizdan, loyiha papkasida):

```bash
bash deploy/deploy.sh ubuntu@SERVER_IP /yo'l/kalit.pem
```

- Domen berilmasa, bepul vaqtinchalik domen ishlatiladi: `13.50.1.2` -> `https://13-50-1-2.sslip.io`.
  O'z domeningiz bo'lsa (uning DNS A yozuvi server IP'siga qaragan bo'lsin), uchinchi parametr qilib yozing.
- Birinchi joylashda boshliq akkaunti tasodifiy parol bilan yaratiladi va ekranga chiqadi
  (serverda `~/nafis_admin_parol.txt` faylida ham saqlanadi). Kirgach, parolni o'zgartiring.
- Kodni yangilash uchun xuddi shu buyruqni qayta ishga tushiring: server bazasi va `.env` o'zgarmaydi.
- Windows'da bu skriptni WSL yoki Git Bash orqali ishga tushiring.

**Serverda foydali buyruqlar:**

```bash
sudo systemctl status nafis          # sayt ishlayaptimi
sudo journalctl -u nafis -n 50       # oxirgi xatolar
cp /opt/nafis/db.sqlite3 ~/zaxira-$(date +%F).sqlite3   # bazaning zaxira nusxasi
```

**Qo'lda joylashda esda tuting:**
- `.env` faylida `DEBUG=False` qiling, `ALLOWED_HOSTS` ga domeningizni yozing.
- HTTPS bo'lsa, `CSRF_TRUSTED_ORIGINS=https://domeningiz.uz`, `SECURE_COOKIES=True` va (nginx orqasida) `BEHIND_PROXY=True`.
- `python manage.py collectstatic` bajarib, `staticfiles/` ni nginx orqali tarqating.
- `runserver` o'rniga gunicorn ishlating.
- `SECRET_KEY` ni hech kimga bermang va `.env` faylini git'ga qo'shmang. U `.gitignore` da bor.
