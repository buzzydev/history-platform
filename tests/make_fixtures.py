"""Generate sample PDFs (text-based Latin/Cyrillic, scanned image) for parser tests."""
import io, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def make_pdf(lines, font=True, per_page=40):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    name = "Helvetica"
    if font and os.path.exists(FONT):
        if "DejaVu" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("DejaVu", FONT))
        name = "DejaVu"
    y, n = 800, 0
    c.setFont(name, 11)
    for ln in lines:
        if n and n % per_page == 0:
            c.showPage(); c.setFont(name, 11); y = 800
        c.drawString(40, y, ln); y -= 18; n += 1
    c.save()
    return buf.getvalue()


LATIN = [
    "1. Amir Temur qachon tug'ilgan?", "A) 1336", "B) 1370", "C) 1405", "D) 1500", "Javob: A",
    "2. Buyuk Ipak yo'li qaysi qit'alarni bog'lagan?", "A) Osiyo va Yevropa", "B) Amerika va Afrika",
    "C) Avstraliya va Antarktida", "D) Faqat Afrika", "Javob: A",
    "3. Samarqand qaysi daryo vodiysida joylashgan?", "A) Zarafshon", "*B) Sirdaryo", "C) Amudaryo", "D) Volga",
]
CYRILLIC = [
    "1. Амир Темур қайси йили тугилган?", "А) 1336", "Б) 1370", "В) 1405", "Г) 1500", "Тўғри жавоб: А",
    "2. Бобурнинг асари қайси?", "А) Бобурнома", "Б) Шоҳнома", "В) Хамса", "Г) Девон", "Тўғри жавоб: А",
]
NUMERIC = [
    "1. Who built the Great Wall?", "1. The Romans", "2. The Chinese", "3. The Greeks", "4. The Persians",
    "2. In which year did World War II end?", "1. 1918", "2. 1939", "3. 1945", "4. 1950",
    "Answers", "1-2 2-3",
]
KEYED = [
    "1) Which ocean is the largest?", "a) Atlantic", "b) Pacific", "c) Indian", "d) Arctic",
    "2) Capital of France?", "a) Berlin", "b) Madrid", "c) Paris", "d) Rome",
    "3) Largest planet?", "a) Mars", "b) Jupiter", "c) Venus", "d) Earth",
    "Javoblar", "1-b 2-c 3-b",
]
