"""Uzbek (Latin) interface translation.

Source strings stay in English in templates/Python; when the site language is "uz" the rendered HTML/JSON is
translated through exact-match dictionary + regex patterns. Unknown strings stay English (never an error).
"""
import json
import re

UZ = {
    # navigation / generic
    "Home": "Bosh sahifa", "Profile": "Profil", "Sign Out": "Chiqish", "Log in": "Kirish", "Register": "Ro'yxatdan o'tish",
    "Switch theme": "Mavzuni almashtirish", "Switch to light mode": "Yorug' rejimga o'tish", "Switch to dark mode": "Qorong'u rejimga o'tish",
    "Skip to content": "Mazmunga o'tish", "Notifications": "Bildirishnomalar", "Notification center": "Bildirishnomalar markazi",
    "Main": "Asosiy", "Student sections": "Talaba bo'limlari", "Teacher sections": "O'qituvchi bo'limlari", "Admin sections": "Admin bo'limlari",
    "Pagination": "Sahifalash", "Dashboard": "Boshqaruv paneli", "Tests": "Testlar", "My history": "Mening tarixim", "Leaderboard": "Reyting",
    "Overview": "Umumiy ko'rinish", "Students": "Talabalar", "Results": "Natijalar", "Analytics": "Tahlil", "Users": "Foydalanuvchilar",
    "Subjects": "Fanlar", "Grades": "Sinflar", "PDF import": "PDF import", "Attempts": "Urinishlar", "Audit log": "Audit jurnali",
    "Logins": "Kirishlar", "Announcements": "E'lonlar", "Settings": "Sozlamalar", "Backups": "Zaxira nusxalar", "Health": "Tizim holati",
    "Save": "Saqlash", "Save changes": "O'zgarishlarni saqlash", "Cancel": "Bekor qilish", "Edit": "Tahrirlash", "Delete": "O'chirish",
    "Add": "Qo'shish", "Filter": "Saralash", "Search": "Qidirish", "Open": "Ochish", "Close": "Yopish", "Download": "Yuklab olish",
    "Actions": "Amallar", "Action": "Amal", "Details": "Tafsilotlar", "Status": "Holat", "Status:": "Holat:", "Date": "Sana", "Time": "Vaqt",
    "Name": "Nom", "Title": "Sarlavha", "Description": "Tavsif", "Description (optional)": "Tavsif (ixtiyoriy)", "Type": "Turi", "Message": "Xabar",
    "All": "Hammasi", "None": "Yo'q", "None.": "Yo'q.", "Choose…": "Tanlang…", "Order": "Tartib", "Size": "Hajm", "Kind": "Turi", "File": "Fayl",
    "Page": "Sahifa", "Pages": "Betlar", "Method": "Usul", "Question": "Savol", "Questions": "Savollar", "Quizzes": "Testlar",
    "Student": "Talaba", "User": "Foydalanuvchi", "Role": "Rol", "Active": "Faol", "Blocked": "Bloklangan", "Block": "Bloklash", "Unblock": "Blokdan chiqarish",
    "Enable": "Yoqish", "Disable": "O'chirish (nofaol)", "Disabled": "O'chirilgan", "Draft": "Qoralama", "Published": "E'lon qilingan",
    "Success": "Muvaffaqiyatli", "Successful": "Muvaffaqiyatli", "Failed": "Muvaffaqiyatsiz", "Verified": "Tekshirilgan", "Original": "Asl nusxa",
    "Show password": "Parolni ko'rsatish", "Hide password": "Parolni yashirish", "Dismiss": "Yopish", "Back to home": "Bosh sahifaga qaytish",
    "Back to log in": "Kirishga qaytish", "Back to users": "Foydalanuvchilarga qaytish", "Request a new link": "Yangi havola so'rash",
    "yes": "ha", "no": "yo'q", "min": "daq", "total": "jami",
    # statuses / roles / levels
    "in progress": "jarayonda", "completed": "yakunlangan", "expired": "vaqti tugagan", "student": "talaba", "teacher": "o'qituvchi", "admin": "admin",
    "info": "ma'lumot", "success": "muvaffaqiyat", "warning": "ogohlantirish", "error": "xato", "approved": "tasdiqlangan", "pending": "kutilmoqda",
    "In progress": "Jarayonda", "Unanswered": "Javobsiz", "Correct": "To'g'ri", "Incorrect": "Noto'g'ri", "Wrong": "Xato",
    "Announcement": "E'lon", "running": "ishlayapti", "not running in this process": "bu jarayonda ishlamayapti",
    # auth
    "Create account": "Hisob yaratish", "First name": "Ism", "Last name": "Familiya", "Phone number": "Telefon raqami", "Phone": "Telefon",
    "Username": "Foydalanuvchi nomi", "Password": "Parol", "Confirm password": "Parolni tasdiqlang", "Current password": "Joriy parol",
    "New password": "Yangi parol", "Confirm new password": "Yangi parolni tasdiqlang", "Change password": "Parolni almashtirish",
    "Update password": "Parolni yangilash", "Keep me signed in": "Tizimda qolish", "Forgot password?": "Parolni unutdingizmi?",
    "Forgot your password?": "Parolingizni unutdingizmi?", "Already registered?": "Ro'yxatdan o'tganmisiz?", "· No account?": "· Hisobingiz yo'qmi?",
    "Example: +998 90 123 45 67": "Masalan: +998 90 123 45 67", "At least 8 characters, with letters and digits.": "Kamida 8 belgi, harf va raqamlar bilan.",
    "Registration is currently closed.": "Hozircha ro'yxatdan o'tish yopiq.", "Reset password": "Parolni tiklash", "Set new password": "Yangi parolni o'rnatish",
    "Ask your teacher or the site administrator for a one-time reset link. The link is valid for one hour and can be used once.":
        "O'qituvchingiz yoki sayt administratoridan bir martalik tiklash havolasini so'rang. Havola bir soat amal qiladi va faqat bir marta ishlatiladi.",
    "This reset link is invalid, expired or already used.": "Bu tiklash havolasi yaroqsiz, muddati o'tgan yoki ishlatilgan.",
    "Password reset link": "Parolni tiklash havolasi", "Give this one-time link to": "Bu bir martalik havolani bering:",
    ". It expires in 1 hour and is shown only once.": ". U 1 soatdan keyin eskiradi va faqat bir marta ko'rsatiladi.",
    "Create password reset link": "Parolni tiklash havolasini yaratish",
    # home
    "Learn history by testing yourself": "Tarixni o'zingizni sinab o'rganing",
    "Practice World History and Uzbekistan History with fresh, randomised questions and see your progress after every test.":
        "Jahon tarixi va O'zbekiston tarixidan yangi, tasodifiy savollar bilan mashq qiling va har bir testdan keyin natijangizni ko'ring.",
    "Create free account": "Bepul hisob yaratish", "Open my dashboard": "Boshqaruv panelimni ochish", "Published tests": "E'lon qilingan testlar",
    "Grades supported": "Qo'llab-quvvatlanadigan sinflar", "Any test, any grade": "Istalgan test, istalgan sinf",
    "Every student can open every published test. No class restrictions.": "Har bir talaba e'lon qilingan istalgan testni yecha oladi. Sinf cheklovi yo'q.",
    "Fair random questions": "Adolatli tasodifiy savollar",
    "Each attempt gets a new shuffle and avoids questions you already saw until the pool is used up.":
        "Har bir urinishda savollar yangidan aralashtiriladi va savollar bazasi tugamaguncha ko'rgan savollaringiz takrorlanmaydi.",
    "Instant feedback": "Zudlik bilan javob", "See the correct answer and explanation after every question, and a full result at the end.":
        "Har bir savoldan keyin to'g'ri javob va izohni, oxirida esa to'liq natijani ko'ring.",
    # student
    "Browse all tests": "Barcha testlarni ko'rish", "Completed tests": "Yakunlangan testlar", "Average score": "O'rtacha ball", "Best score": "Eng yaxshi ball",
    "Correct answers": "To'g'ri javoblar", "Recently added tests": "Yaqinda qo'shilgan testlar", "Recent activity": "So'nggi faollik",
    "No tests are published yet. Please check back soon.": "Hozircha e'lon qilingan testlar yo'q. Keyinroq qayta tekshiring.",
    "You have not taken any tests yet.": "Siz hali birorta ham test yechmagansiz.", "No notifications.": "Bildirishnomalar yo'q.",
    "You have no notifications.": "Sizda bildirishnomalar yo'q.", "All tests": "Barcha testlar", "Search tests": "Testlarni qidirish",
    "All subjects": "Barcha fanlar", "All grades": "Barcha sinflar", "Grade": "Sinf", "Subject": "Fan", "No grade": "Sinf yo'q",
    "No tests match your filters.": "Filtrlarga mos test topilmadi.", "no time limit": "vaqt chegarasi yo'q", "Questions per attempt": "Bir urinishdagi savollar",
    "Time limit": "Vaqt chegarasi", "Attempts used": "Ishlatilgan urinishlar", "Feedback": "Javob ko'rsatish",
    "Correct answer shown after each question": "Har bir savoldan keyin to'g'ri javob ko'rsatiladi", "Shown at the end": "Oxirida ko'rsatiladi",
    "Start test": "Testni boshlash", "Resume attempt": "Urinishni davom ettirish", "Resume": "Davom ettirish", "My attempts": "Mening urinishlarim",
    "No attempts yet.": "Hali urinishlar yo'q.", "Admins and teachers can preview tests but only students take them.":
        "Administratorlar va o'qituvchilar testlarni ko'rib chiqishi mumkin, lekin faqat talabalar yechadi.",
    "Only students can take tests. Admins and teachers can preview results.": "Testni faqat talabalar yecha oladi. Admin va o'qituvchilar natijalarni ko'radi.",
    "JavaScript is required to take a quiz.": "Test yechish uchun JavaScript kerak.", "Result": "Natija", "Total questions": "Jami savollar",
    "Time spent": "Sarflangan vaqt", "Test completed": "Test yakunlandi", "Results for this test are not shown to students.": "Bu testning natijalari talabalarga ko'rsatilmaydi.",
    "Try again": "Qayta urinish", "Answer review": "Javoblarni ko'rib chiqish", "Your answer:": "Sizning javobingiz:", "Correct answer:": "To'g'ri javob:",
    "My quiz history": "Mening test tarixim", "Attempt": "Urinish", "Score": "Ball", "Correct": "To'g'ri", "No quiz history yet.": "Test tarixi hali yo'q.",
    "Global leaderboard": "Umumiy reyting", "Rank": "O'rin", "Best": "Eng yaxshi", "Average": "O'rtacha", "Quizzes": "Testlar", "Completed": "Yakunlangan",
    "The leaderboard is empty. Complete tests to appear here!": "Reyting hozircha bo'sh. Testlarni yechib, bu yerda paydo bo'ling!",
    "Personal information": "Shaxsiy ma'lumotlar", "Member since": "A'zo bo'lgan sana", "Completed tests": "Yakunlangan testlar",
    "No activity yet.": "Faollik hali yo'q.", "Quiz history": "Test tarixi",
    # teacher
    "Teacher dashboard": "O'qituvchi paneli", "Completed quizzes": "Yakunlangan testlar", "Latest results": "So'nggi natijalar", "Nothing yet.": "Hozircha hech narsa yo'q.",
    "No completed quizzes yet.": "Yakunlangan testlar hali yo'q.", "Search by name or username": "Ism yoki foydalanuvchi nomi bo'yicha qidirish",
    "No students found.": "Talabalar topilmadi.", "Student results": "Talabalar natijalari", "Student name or username": "Talaba ismi yoki foydalanuvchi nomi",
    "All tests": "Barcha testlar", "No results found.": "Natijalar topilmadi.", "Excel": "Excel", "PDF": "PDF", "Completed": "Yakunlangan",
    "Most frequently missed questions": "Eng ko'p xato qilingan savollar", "Test statistics": "Test statistikasi", "Test": "Test", "Answers": "Javoblar",
    "No data.": "Ma'lumot yo'q.", "Not enough answers yet (a question needs at least 3 answers).": "Javoblar hali yetarli emas (savolga kamida 3 ta javob kerak).",
    "No attempts.": "Urinishlar yo'q.", "Quiz attempts": "Test urinishlari",
    # admin
    "Admin dashboard": "Admin paneli", "Approved questions": "Tasdiqlangan savollar", "Awaiting approval": "Tasdiq kutmoqda", "Completed attempts": "Yakunlangan urinishlar",
    "Quizzes in progress": "Jarayondagi testlar", "Last backup": "Oxirgi zaxira", "Recent failed logins": "So'nggi muvaffaqiyatsiz kirishlar", "Recent activity": "So'nggi faollik",
    "Name, username or phone": "Ism, foydalanuvchi nomi yoki telefon", "All roles": "Barcha rollar", "Any status": "Istalgan holat", "Joined": "Qo'shilgan",
    "No users match.": "Mos foydalanuvchi topilmadi.", "Edit user": "Foydalanuvchini tahrirlash", "Only administrators can appoint teachers or administrators.":
        "O'qituvchi yoki administrator tayinlashni faqat administratorlar qila oladi.", "Teacher permissions (used when role is teacher)": "O'qituvchi huquqlari (rol o'qituvchi bo'lganda)",
    "View students": "Talabalarni ko'rish", "View quiz results and history": "Test natijalari va tarixini ko'rish", "View analytics": "Tahlilni ko'rish", "Export reports": "Hisobotlarni eksport qilish",
    "Delete user": "Foydalanuvchini o'chirish", "Nothing here yet.": "Bu yerda hali hech narsa yo'q.", "Deleted.": "O'chirildi.", "Saved.": "Saqlandi.",
    "Test collections": "Test to'plamlari", "New test": "Yangi test", "Import PDF": "PDF import qilish", "New test collection": "Yangi test to'plami", "Test settings": "Test sozlamalari",
    "Edit test": "Testni tahrirlash", "Edit settings": "Sozlamalarni tahrirlash", "Delete test": "Testni o'chirish", "Review questions": "Savollarni ko'rib chiqish",
    "No tests yet. Import a PDF or create one manually.": "Testlar hali yo'q. PDF import qiling yoki qo'lda yarating.", "Publish test": "Testni e'lon qilish", "Unpublish": "E'londan olish",
    "Source PDF:": "Manba PDF:", "Download original": "Asl faylni yuklab olish", "Save draft": "Qoralamani saqlash", "Approve all questions": "Barcha savollarni tasdiqlash",
    ". Extracted questions are never published automatically: review, correct, approve all, then publish.":
        ". Ajratib olingan savollar hech qachon avtomatik e'lon qilinmaydi: tekshiring, to'g'rilang, hammasini tasdiqlang, so'ng e'lon qiling.",
    "Title": "Sarlavha", "Grade (organisational only)": "Sinf (faqat tashkiliy ma'lumot)", "Time limit (minutes, 0 = none)": "Vaqt chegarasi (daqiqa, 0 = yo'q)",
    "Max attempts per student (0 = unlimited)": "Talabaga maksimal urinishlar (0 = cheksiz)", "Publication date (optional)": "E'lon qilish sanasi (ixtiyoriy)",
    "Expiration date (optional)": "Tugash sanasi (ixtiyoriy)", "Randomise question order": "Savollar tartibini aralashtirish", "Randomise answer options": "Javob variantlarini aralashtirish",
    "Show correct answer after each question": "Har bir savoldan keyin to'g'ri javobni ko'rsatish", "Show explanation if available": "Izoh bo'lsa, uni ko'rsatish",
    "Show final results to students": "Yakuniy natijani talabalarga ko'rsatish", "Test enabled": "Test yoqilgan",
    "Dates use the site time zone. Questions are picked fairly: unseen ones first; when order randomisation is off they are shown in their saved order.":
        "Sanalar sayt vaqt mintaqasida. Savollar adolatli tanlanadi: avval ko'rilmaganlari; tartibni aralashtirish o'chirilganda saqlangan tartibda ko'rsatiladi.",
    "Import questions from PDF": "PDF'dan savollarni import qilish", "PDF file (text-based or scanned)": "PDF fayl (matnli yoki skaner qilingan)",
    "Test collection name": "Test to'plami nomi", "Grade (optional metadata)": "Sinf (ixtiyoriy ma'lumot)", "Or add to an existing test": "Yoki mavjud testga qo'shish",
    "Create a new test": "Yangi test yaratish", "Upload and extract": "Yuklash va ajratib olish", "Uploaded documents": "Yuklangan hujjatlar", "Uploaded": "Yuklangan",
    "Supported: A) B) C) D) and 1. 2. 3. 4. options, Latin/Cyrillic/Uzbek text, answer lines (Javob: A), marked answers (*A) or answer keys at the end. Scanned pages use OCR. You always review before anything is published.":
        "Qo'llab-quvvatlanadi: A) B) C) D) va 1. 2. 3. 4. variantlar, lotin/kirill/o'zbek matni, javob qatorlari (Javob: A), belgilangan javoblar (*A) yoki oxiridagi javoblar kaliti. Skaner qilingan sahifalar OCR orqali o'qiladi. E'lon qilishdan oldin har doim o'zingiz tekshirasiz.",
    "No PDFs uploaded yet.": "PDF'lar hali yuklanmagan.", "Student or test": "Talaba yoki test", "No audit events match.": "Mos audit yozuvlari yo'q.", "From": "Dan", "To": "Gacha",
    "Event type": "Hodisa turi", "Target": "Obyekt", "User": "Foydalanuvchi", "Login history": "Kirish tarixi", "Device / browser": "Qurilma / brauzer", "Session": "Sessiya",
    "Result": "Natija", "No login events.": "Kirish yozuvlari yo'q.", "Successful": "Muvaffaqiyatli", "Send to all users": "Barcha foydalanuvchilarga yuborish",
    "No announcements yet.": "E'lonlar hali yo'q.", "Website settings": "Sayt sozlamalari", "Save settings": "Sozlamalarni saqlash", "Site name": "Sayt nomi",
    "Open registration": "Ro'yxatdan o'tish ochiq", "Default questions per attempt": "Standart: bir urinishdagi savollar", "Default time limit (minutes, 0 = none)": "Standart vaqt chegarasi (daqiqa, 0 = yo'q)",
    "Default max attempts (0 = unlimited)": "Standart maksimal urinishlar (0 = cheksiz)", "Show correct answer after each question (default)": "Har bir savoldan keyin to'g'ri javobni ko'rsatish (standart)",
    "Leaderboard: minimum completed attempts": "Reyting: minimal yakunlangan urinishlar", "Leaderboard: reliability weight (higher = stricter)": "Reyting: ishonchlilik og'irligi (yuqori = qattiqroq)",
    "Automatic backups": "Avtomatik zaxira nusxalar", "Backup interval (hours)": "Zaxira oralig'i (soat)", "Keep last N backups": "Oxirgi N ta zaxirani saqlash",
    "Include uploaded PDFs in backups": "Yuklangan PDF'larni zaxiraga kiritish", "Database backups": "Ma'lumotlar bazasi zaxirasi", "Run backup now": "Zaxirani hozir yaratish",
    "Backups are stored in the": "Zaxira nusxalar", "primary": "asosiy", "database. For real disaster recovery set": "bazada saqlanadi. Haqiqiy avariyadan tiklanish uchun",
    "to a separate database and download copies regularly.": "ni alohida bazaga ulang va nusxalarni muntazam yuklab oling.", "No backups yet.": "Zaxira nusxalar hali yo'q.", "When": "Qachon",
    "System health": "Tizim holati", "Database engine": "Baza turi", "DB latency": "Baza kechikishi", "Separate backup DB": "Alohida zaxira bazasi", "Backup scheduler thread": "Zaxira rejalovchisi",
    "OCR languages": "OCR tillari", "Environment": "Muhit", "Active sessions": "Faol sessiyalar", "Stored PDFs": "Saqlangan PDF'lar", "SQLite (development only)": "SQLite (faqat ishlab chiqish uchun)",
    "Delete attempt": "Urinishni o'chirish", "Create": "Yaratish", "Announcement deleted.": "E'lon o'chirildi.", "Announcement sent to all users.": "E'lon barcha foydalanuvchilarga yuborildi.",
    "Web site": "Sayt", "World History": "Jahon tarixi", "Uzbekistan History": "O'zbekiston tarixi", "Message": "Xabar",
    "Welcome!": "Xush kelibsiz!", "Your account is ready. Pick a test and start learning.": "Hisobingiz tayyor. Testni tanlang va o'rganishni boshlang.",
    "Test completed": "Test yakunlandi", "Backup completed": "Zaxira yaratildi", "Backup failed": "Zaxira yaratilmadi", "PDF extraction failed": "PDF'dan ajratib olish muvaffaqiyatsiz",
    "You are now a teacher": "Siz endi o'qituvchisiz", "An administrator granted you teacher access.": "Administrator sizga o'qituvchi huquqini berdi.",
    "Prev": "Oldingi", "← Prev": "← Oldingi", "Next →": "Keyingi →", "← Previous": "← Oldingi", "Finish": "Yakunlash", "Submit": "Topshirish", "Submit and see results": "Topshirish va natijani ko'rish",
    # flash / errors
    "Login successful.": "Muvaffaqiyatli kirdingiz.", "Registration successful. Welcome!": "Ro'yxatdan o'tish muvaffaqiyatli. Xush kelibsiz!", "You have been signed out.": "Tizimdan chiqdingiz.",
    "Invalid username or password.": "Foydalanuvchi nomi yoki parol noto'g'ri.", "Your account is blocked. Contact the administrator.": "Hisobingiz bloklangan. Administrator bilan bog'laning.",
    "Too many failed attempts. Please wait a few minutes.": "Juda ko'p muvaffaqiyatsiz urinish. Bir necha daqiqa kuting.", "Too many registration attempts. Try again later.": "Ro'yxatdan o'tishga juda ko'p urinish. Keyinroq qayta urining.",
    "Too many attempts. Try again later.": "Juda ko'p urinish. Keyinroq qayta urining.", "Too many attempts.": "Juda ko'p urinish.", "Please log in to continue.": "Davom etish uchun tizimga kiring.",
    "Please fix the highlighted fields.": "Belgilangan maydonlarni to'g'rilang.", "First name is required (max 60 characters).": "Ism kiritilishi shart (ko'pi bilan 60 belgi).",
    "Last name is required (max 60 characters).": "Familiya kiritilishi shart (ko'pi bilan 60 belgi).", "Enter a valid phone number, e.g. +998 90 123 45 67.": "To'g'ri telefon raqam kiriting, masalan +998 90 123 45 67.",
    "Enter a valid phone number.": "To'g'ri telefon raqam kiriting.", "3-30 characters: letters, digits, underscore or dot.": "3-30 belgi: harflar, raqamlar, pastki chiziq yoki nuqta.",
    "Passwords do not match.": "Parollar mos kelmadi.", "This username is already taken.": "Bu foydalanuvchi nomi band.", "This phone number is already registered.": "Bu telefon raqam allaqachon ro'yxatdan o'tgan.",
    "This username or phone number is already registered.": "Bu foydalanuvchi nomi yoki telefon raqam allaqachon ro'yxatdan o'tgan.", "Password updated. You can log in now.": "Parol yangilandi. Endi kirishingiz mumkin.",
    "Password must be at least 8 characters.": "Parol kamida 8 belgidan iborat bo'lishi kerak.", "Password is too long (max 128).": "Parol juda uzun (ko'pi bilan 128).",
    "Password must contain letters and digits.": "Parolda harflar va raqamlar bo'lishi kerak.", "First and last name are required.": "Ism va familiya kiritilishi shart.",
    "This phone number is already used by another account.": "Bu telefon raqam boshqa hisobda ishlatilgan.", "This phone number belongs to another account.": "Bu telefon raqam boshqa hisobga tegishli.",
    "Profile updated.": "Profil yangilandi.", "Current password is incorrect.": "Joriy parol noto'g'ri.", "New passwords do not match.": "Yangi parollar mos kelmadi.",
    "Password changed. Other devices were signed out.": "Parol o'zgartirildi. Boshqa qurilmalardan chiqarildi.", "This test is not available.": "Bu test mavjud emas.",
    "You have used all attempts for this test.": "Bu test bo'yicha barcha urinishlaringiz tugadi.", "This test has no approved questions yet.": "Bu testda hali tasdiqlangan savollar yo'q.",
    "Could not start the test. Please try again.": "Testni boshlab bo'lmadi. Qayta urinib ko'ring.", "Attempt not found.": "Urinish topilmadi.", "This attempt is already finished.": "Bu urinish allaqachon yakunlangan.",
    "Time is up. The attempt was submitted.": "Vaqt tugadi. Urinish topshirildi.", "Question is not part of this attempt.": "Bu savol ushbu urinishga tegishli emas.", "Invalid answer option.": "Noto'g'ri javob varianti.",
    "This question was already answered.": "Bu savolga allaqachon javob berilgan.", "question_id and option_id are required.": "question_id va option_id kerak.",
    "Authentication required.": "Tizimga kirish talab qilinadi.", "Forbidden.": "Ruxsat yo'q.", "Access denied": "Ruxsat berilmagan", "Page not found": "Sahifa topilmadi", "File too large": "Fayl juda katta",
    "Too many requests": "Juda ko'p so'rov", "Bad request": "Noto'g'ri so'rov", "Server error": "Server xatosi", "Something went wrong. Please try again.": "Nimadir xato ketdi. Qayta urinib ko'ring.",
    "Internal server error.": "Serverning ichki xatosi.", "Invalid or missing CSRF token.": "CSRF belgisi noto'g'ri yoki yo'q.", "Invalid payload.": "Noto'g'ri so'rov ma'lumoti.",
    "We could not complete this request.": "So'rovni bajarib bo'lmadi.", "Network error. Check your connection and try again.": "Tarmoq xatosi. Ulanishni tekshirib, qayta urinib ko'ring.",
    "User updated.": "Foydalanuvchi yangilandi.", "Account blocked.": "Hisob bloklandi.", "Account unblocked.": "Hisob blokdan chiqarildi.", "You cannot block yourself.": "O'zingizni bloklay olmaysiz.",
    "You cannot delete your own account.": "O'z hisobingizni o'chira olmaysiz.", "You cannot remove your own administrator role.": "O'zingizning administrator rolingizni olib tashlay olmaysiz.",
    "At least one administrator is required.": "Kamida bitta administrator bo'lishi kerak.", "At least one administrator must stay active.": "Kamida bitta administrator faol qolishi kerak.",
    "Change this administrator to another role before deleting the account.": "Hisobni o'chirishdan oldin bu administratorning rolini o'zgartiring.",
    "Name is required.": "Nom kiritilishi shart.", "Name is required (max 80 characters).": "Nom kiritilishi shart (ko'pi bilan 80 belgi).", "This name already exists.": "Bu nom allaqachon mavjud.",
    "This subject still has tests. Move or delete them first.": "Bu fanda hali testlar bor. Avval ularni ko'chiring yoki o'chiring.", "Choose a subject.": "Fanni tanlang.",
    "Title is required (max 150 characters).": "Sarlavha kiritilishi shart (ko'pi bilan 150 belgi).", "Title is required (max 120 characters).": "Sarlavha kiritilishi shart (ko'pi bilan 120 belgi).",
    "Expiration must be after the publication date.": "Tugash sanasi e'lon qilish sanasidan keyin bo'lishi kerak.", "Test created. Now add questions.": "Test yaratildi. Endi savollar qo'shing.",
    "Test settings saved.": "Test sozlamalari saqlandi.", "Test deleted together with its attempts.": "Test urinishlari bilan birga o'chirildi.", "Test disabled.": "Test o'chirildi (nofaol).", "Test enabled.": "Test yoqildi.",
    "Test moved back to draft.": "Test qoralamaga qaytarildi.", "Test published. Students can now take it.": "Test e'lon qilindi. Talabalar endi uni yecha oladi.", "Approve at least one question before publishing.": "E'lon qilishdan oldin kamida bitta savolni tasdiqlang.",
    "Settings saved.": "Sozlamalar saqlandi.", "Backup completed and restore-verified.": "Zaxira yaratildi va tiklash orqali tekshirildi.", "Choose a PDF file (.pdf).": "PDF fayl (.pdf) tanlang.", "The file is empty.": "Fayl bo'sh.",
    "Enter a collection name and choose a subject.": "To'plam nomini kiriting va fanni tanlang.", "This exact file was uploaded before.": "Aynan shu fayl avval yuklangan.",
    "Attempt deleted (the student gets this attempt back).": "Urinish o'chirildi (talabaga bu urinish qaytariladi).",
    "Delete this announcement?": "Bu e'lonni o'chirasizmi?", "Delete this test, its questions and all student attempts?": "Bu testni, uning savollarini va barcha talaba urinishlarini o'chirasizmi?",
    "Delete this attempt? The student will get the attempt back.": "Bu urinishni o'chirasizmi? Talabaga urinish qaytariladi.",
    # pdf parser
    "No questions were recognised. Check the numbering and answer format of the PDF.": "Savollar topilmadi. PDF'dagi raqamlash va javob formatini tekshiring.",
    "Correct answer not detected - choose it manually.": "To'g'ri javob aniqlanmadi - uni qo'lda tanlang.", "Fewer than two answer options were found.": "Ikkitadan kam javob varianti topildi.",
    "An answer option is empty.": "Javob variantlaridan biri bo'sh.", "Question text is empty.": "Savol matni bo'sh.", "Several options are marked as correct.": "Bir nechta variant to'g'ri deb belgilangan.",
    "The answer key disagrees with the answer found beside the question.": "Javoblar kaliti savol yonidagi javob bilan mos kelmaydi.", "The answer line could not be matched to an option.": "Javob qatorini variantga moslab bo'lmadi.",
    "OCR was used; please review the text carefully.": "OCR ishlatildi; matnni diqqat bilan tekshiring.", "The PDF has no pages.": "PDF'da sahifalar yo'q.",
    "The file is not a valid PDF (missing %PDF header).": "Fayl yaroqli PDF emas (%PDF sarlavhasi yo'q).",
    # JS-only
    "Could not load the quiz.": "Testni yuklab bo'lmadi.", "Could not save the answer.": "Javobni saqlab bo'lmadi.", "Could not submit.": "Topshirib bo'lmadi.", "Answer saved.": "Javob saqlandi.",
    "✅ Correct!": "✅ To'g'ri!", "❌ Incorrect.": "❌ Noto'g'ri.", "Submit the test?": "Testni topshirasizmi?", "Are you sure?": "Ishonchingiz komilmi?", "Confirm": "Tasdiqlash", "Please confirm": "Iltimos, tasdiqlang",
    "Yes, continue": "Ha, davom etish", "Previous": "Oldingi", "Question {n} of {total} • {a} answered": "{n}/{total}-savol • {a} ta javob berilgan", "Go to question {n}": "{n}-savolga o'tish",
    "{n} question(s) are unanswered and will count as incorrect.": "{n} ta savolga javob berilmagan va noto'g'ri hisoblanadi.", "Could not load questions.": "Savollarni yuklab bo'lmadi.",
    "+ Add question": "+ Savol qo'shish", "+ Add option": "+ Variant qo'shish", "No questions yet. Upload a PDF or add a question manually.": "Savollar hali yo'q. PDF yuklang yoki qo'lda qo'shing.",
    "{n} question(s) • {p} awaiting approval": "{n} ta savol • {p} tasi tasdiq kutmoqda", "Question text": "Savol matni", "Answer options (select the correct one)": "Javob variantlari (to'g'risini tanlang)",
    "Explanation (optional)": "Izoh (ixtiyoriy)", "Explanation": "Izoh", "Preview": "Ko'rib chiqish", "Move up": "Yuqoriga", "Move down": "Pastga", "Delete question": "Savolni o'chirish", "Remove option": "Variantni olib tashlash",
    "Delete question?": "Savolni o'chirasizmi?", "This question will be removed from the test.": "Bu savol testdan olib tashlanadi.", "Student preview": "Talaba ko'rinishi", "(empty question)": "(bo'sh savol)", "(empty)": "(bo'sh)",
    "confidence {n}%": "ishonch {n}%", "Mark option {n} correct": "{n}-variantni to'g'ri deb belgilash", "Option {n}": "{n}-variant", "Question": "Savol",
    "All questions approved.": "Barcha savollar tasdiqlandi.", "Draft saved.": "Qoralama saqlandi.", "Save failed.": "Saqlab bo'lmadi.", "Question #{n}: {e}": "Savol #{n}: {e}",
    "Question text is empty": "Savol matni bo'sh", "At least two options needed": "Kamida ikkita variant kerak", "An option is empty": "Variantlardan biri bo'sh", "Choose exactly one correct answer": "Aynan bitta to'g'ri javobni tanlang",
    "Delete": "O'chirish",
}

PATTERNS = [
    (r"^Hello, (.+)!$", r"Salom, \1!"),
    (r"^Page (\d+) / (\d+) · (\d+) total$", r"\1 / \2-sahifa · jami \3"),
    (r"^(\d+) questions$", r"\1 ta savol"), (r"^(\d+) questions · (\d+) min$", r"\1 ta savol · \2 daqiqa"),
    (r"^(\d+) questions · no time limit$", r"\1 ta savol · vaqt chegarasi yo'q"), (r"^(\d+) min$", r"\1 daqiqa"),
    (r"^(\d+) minutes$", r"\1 daqiqa"), (r"^None$", "Yo'q"),
    (r"^(\d+) questions · (\d+) min$", r"\1 ta savol · \2 daqiqa"),
    (r"^Attempts: (\d+) / (\d+)$", r"Urinishlar: \1 / \2"), (r"^Attempts: (\d+) \(unlimited\)$", r"Urinishlar: \1 (cheksiz)"),
    (r"^(\d+) of (\d+)$", r"\1 / \2"), (r"^(\d+) approved$", r"\1 ta tasdiqlangan"), (r"^(\d+) pending$", r"\1 ta kutilmoqda"),
    (r"^(\d+) test\(s\)$", r"\1 ta test"), (r"^(\d+) pages, (\w+) extraction\)$", r"\1 bet, \2 usulida)"),
    (r"^\((\d+) pages,$", r"(\1 bet,"), (r"^Users \((\d+) teachers\)$", r"Foydalanuvchilar (\1 ta o'qituvchi)"),
    (r"^Edit (.+)$", r"\1 ni tahrirlash"), (r"^Block (.+)\?$", r"\1 bloklansinmi?"), (r"^Unblock (.+)\?$", r"\1 blokdan chiqarilsinmi?"),
    (r"^Delete (.+) and all their results\? This cannot be undone\.$", r"\1 va uning barcha natijalari o'chirilsinmi? Buni qaytarib bo'lmaydi."),
    (r"^Delete (.+)\?$", r"\1 o'chirilsinmi?"), (r"^(Enable|Disable) this test\?$", lambda m: "Bu test yoqilsinmi?" if m.group(1) == "Enable" else "Bu test o'chirilsinmi (nofaol)?"),
    (r"^New (grade|subject) name$", lambda m: "Yangi sinf nomi" if m.group(1) == "grade" else "Yangi fan nomi"),
    (r"^Completed (.+?)( \(time ran out\))?$", lambda m: f"Yakunlangan: {m.group(1)}" + (" (vaqt tugadi)" if m.group(2) else "")),
    (r"^Status: (\w+)\. Extracted questions are never published automatically: review, correct, approve all, then publish\.$",
     r"Holat: \1. Ajratib olingan savollar hech qachon avtomatik e'lon qilinmaydi: tekshiring, to'g'rilang, hammasini tasdiqlang, so'ng e'lon qiling."),
    (r"^Ranking uses .*? Students appear after (\d+) completed attempts\.$",
     r"Reyting ishonchlilik bo'yicha tortilgan o'rtacha ball asosida hisoblanadi, shuning uchun bitta omadli urinish birinchi o'rinni ololmaydi. Talabalar \1 ta yakunlangan urinishdan keyin ko'rinadi."),
    (r"^A backup is marked verified only after .*? matched\. Scheduler thread: (.*)\.$",
     lambda m: "Zaxira faqat arxiv vaqtinchalik bazaga tiklanib, barcha qatorlar soni mos kelgandagina «tekshirilgan» deb belgilanadi. Rejalovchi oqimi: " + UZ.get(m.group(1), m.group(1)) + "."),
    (r"^([\d.]+) KB$", r"\1 KB"), (r"^Your answer: (.+)$", r"Sizning javobingiz: \1"),
    (r"^Extracted (\d+) question\(s\)(, skipped (\d+) duplicate\(s\))?\. Review and approve them before publishing\.$",
     lambda m: f"{m.group(1)} ta savol ajratib olindi" + (f", {m.group(3)} ta takror o'tkazib yuborildi" if m.group(3) else "") + ". E'lon qilishdan oldin ularni tekshiring va tasdiqlang."),
    (r"^PDF extraction failed: (.+)$", r"PDF'dan ajratib olish muvaffaqiyatsiz: \1"), (r"^Backup failed: (.+)$", r"Zaxira yaratilmadi: \1"),
    (r"^User (.+) deleted\.$", r"\1 foydalanuvchisi o'chirildi."), (r"^(Grade|Subject) created\.$", lambda m: ("Sinf" if m.group(1) == "Grade" else "Fan") + " yaratildi."),
    (r"^(\d+) question\(s\) are still awaiting approval\. Review and approve them first\.$", r"\1 ta savol hali tasdiq kutmoqda. Avval ularni tekshirib tasdiqlang."),
    (r"^(\d+) question\(s\) are incomplete\.$", r"\1 ta savol to'liq emas."),
    (r"^The PDF has (\d+) pages; the limit is (\d+)\.$", r"PDF'da \1 bet bor; chegara \2."), (r"^The PDF could not be read: (.+)\.$", r"PDF'ni o'qib bo'lmadi: \1."),
    (r"^Only (\d+) answer options were found\.$", r"Faqat \1 ta javob varianti topildi."), (r"^Question (\d+) is a duplicate inside this file and was skipped\.$", r"\1-savol shu fayl ichida takrorlangan va o'tkazib yuborildi."),
    (r"^Question numbers jump from (\d+) to (\d+); a question may be missing\.$", r"Savol raqamlari \1 dan \2 ga sakraydi; savol tushib qolgan bo'lishi mumkin."),
    (r"^(\d+) page\(s\) have no text layer and OCR failed: (.+)$", r"\1 ta betda matn qatlami yo'q va OCR ishlamadi: \2"),
    (r"^Time limit: (.+)$", r"Vaqt chegarasi: \1"),
]
_PATS = [(re.compile(p), r) for p, r in PATTERNS]
_ATTR = re.compile(r'\b(placeholder|aria-label|title|alt|data-confirm|data-confirm-title|data-confirm-button)="([^"]*)"')
_TEXT = re.compile(r">([^<>]+)<")
_FLASH = re.compile(r"(id=\"flash-data\" data-messages=')([^']*)(')")


def tr(s):
    """Translate one string (exact, then pattern). Returns the same string if unknown."""
    if not s or not s.strip():
        return s
    lead = s[: len(s) - len(s.lstrip())]
    trail = s[len(s.rstrip()):]
    core = re.sub(r"\s+", " ", s.strip())
    import html as _h
    core = _h.unescape(core)
    hit = UZ.get(core)
    if hit is None:
        for rx, rep in _PATS:
            m = rx.match(core)
            if m:
                hit = rep(m) if callable(rep) else m.expand(rep)
                break
    if hit is None:
        return s
    return lead + _h.escape(hit, quote=False) + trail


def translate_html(html):
    import html as _h

    def attr(m):
        v = tr(_h.unescape(m.group(2)))
        return f'{m.group(1)}="{_h.escape(_h.unescape(v), quote=True)}"' if v != m.group(2) else m.group(0)

    def flash(m):
        try:
            data = json.loads(m.group(2))
        except ValueError:
            return m.group(0)
        data = [[c, _h.unescape(tr(msg))] for c, msg in data]
        out = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("'", "\\u0027")
        return m.group(1) + out + m.group(3)

    html = _FLASH.sub(flash, html)
    html = _ATTR.sub(attr, html)
    html = _TEXT.sub(lambda m: ">" + tr(m.group(1)) + "<", html)
    return html.replace('<html lang="en"', '<html lang="uz"', 1)


def translate_json_error(obj):
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "error" and isinstance(v, str):
                obj[k] = tr(v)
            elif k == "problems" and isinstance(v, list):
                for p in v:
                    if isinstance(p, dict) and isinstance(p.get("errors"), list):
                        p["errors"] = [tr(e[:1].upper() + e[1:]) for e in p["errors"]]
    return obj


JS_KEYS = [k for k in UZ if "{" in k] + [
    "Could not load the quiz.", "Could not save the answer.", "Could not submit.", "Answer saved.", "✅ Correct!", "❌ Incorrect.", "Submit the test?", "Are you sure?",
    "Confirm", "Please confirm", "Yes, continue", "Cancel", "Close", "Dismiss", "Previous", "← Previous", "Next →", "Finish", "Submit", "Submit and see results",
    "Could not load questions.", "+ Add question", "+ Add option", "No questions yet. Upload a PDF or add a question manually.", "Question text", "Answer options (select the correct one)",
    "Explanation (optional)", "Explanation", "Preview", "Move up", "Move down", "Delete question", "Remove option", "Delete question?", "This question will be removed from the test.",
    "Student preview", "(empty question)", "(empty)", "All questions approved.", "Draft saved.", "Save failed.", "Question text is empty", "At least two options needed",
    "An option is empty", "Choose exactly one correct answer", "Delete", "Save draft", "Approve all questions", "Question", "Switch to light mode", "Switch to dark mode",
    "Show password", "Hide password", "Network error. Check your connection and try again.", "Incorrect", "Correct",
]


def js_dict(lang):
    return {k: UZ[k] for k in set(JS_KEYS) if k in UZ} if lang == "uz" else {}
