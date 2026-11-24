# Railway'ga joylash (oddiy o'zbekcha)

1. **GitHub**: ZIP ichidagi hamma narsani yangi GitHub repozitoriyga yuklang (fayllar repozitoriyning eng yuqori papkasida bo'lsin).
2. **Railway** → *New Project* → *Deploy from GitHub repo* → shu repozitoriyni tanlang. Railway `Dockerfile` ni o'zi topadi.
3. Loyihaga **PostgreSQL** qo'shing (*New* → *Database* → *PostgreSQL*).
4. Sayt xizmatining **Variables** bo'limiga quyidagilarni yozing:
   * `APP_ENV` = `production`
   * `SECRET_KEY` = uzun tasodifiy matn (kamida 48 belgi)
   * `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   * `ADMIN_USERNAME` = admin nomi (masalan `admin`)
   * `ADMIN_PASSWORD` = kuchli parol (8+ belgi, harf va raqam)
   * `ADMIN_PHONE` = `+998901234567`
   * ixtiyoriy, lekin tavsiya etiladi: `BACKUP_DATABASE_URL` = **boshqa** PostgreSQL bazasi (zaxira uchun)
5. *Deploy* tugagach, *Settings → Networking → Generate Domain* bosing va saytni oching.
6. `ADMIN_USERNAME` bilan kiring. **Profile** orqali parolni darhol almashtiring.
7. **Admin → PDF import** orqali PDF yuklang → savollarni tekshiring → *Approve all questions* → *Publish test*.
8. **Admin → Backups → Run backup now** bosib, "verified" chiqishini tekshiring.

Muhim:
* Hamma ma'lumot (foydalanuvchilar, natijalar, PDF fayllar, zaxira) bazada saqlanadi.
* Saytni 1 tadan ortiq nusxada ishlatmang (zaxira rejalovchisi bitta bo'lishi kerak).
* Parolni unutgan foydalanuvchi uchun: **Admin → Users → kalit belgisi** (1 soatlik bir martalik havola).
