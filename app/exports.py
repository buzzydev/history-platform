import io
import os

from .helpers import dur, local_dt

HEAD = ["Student", "Name", "Test", "Attempt", "Correct", "Incorrect", "Total", "Percent", "Time spent", "Completed"]


def rows_for(results):
    return [[r["username"], f"{r['first_name']} {r['last_name']}", r["title"], r["attempt_no"], r["correct_count"],
             r["incorrect_count"], r["total_questions"], round(r["percentage"], 1), dur(r["time_spent_seconds"]),
             local_dt(r["completed_at"])] for r in results]


def results_xlsx(results):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append(HEAD)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows_for(results):
        ws.append(r)
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(40, max(len(str(c.value or "")) for c in col) + 2)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def results_pdf(results, title="Quiz results"):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    font = "Helvetica"
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            if "DejaVuQ" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("DejaVuQ", p))
            font = "DejaVuQ"
            break
    st = getSampleStyleSheet()["Title"]
    st.fontName = font
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    data = [HEAD] + [[str(c) for c in r] for r in rows_for(results)]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), font), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#bdb08e")),
                           ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f2e8")])]))
    doc.build([Paragraph(title, st), Spacer(1, 8), t])
    return buf.getvalue()
