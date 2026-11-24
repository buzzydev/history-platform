import io
import json

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app import pdfimport
from tests.base import AppTestCase, token
from tests.make_fixtures import CYRILLIC, KEYED, LATIN, NUMERIC, make_pdf


def scanned_pdf(lines):
    """Image-only PDF (no text layer) to exercise OCR."""
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
    y = 100
    for ln in lines:
        d.text((80, y), ln, fill="black", font=f); y += 60
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    tmp = io.BytesIO(); img.save(tmp, "PNG"); tmp.seek(0)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(tmp), 0, 0, width=A4[0], height=A4[1]); c.save()
    return buf.getvalue()


class ParserTests(AppTestCase):
    def test_latin_letter_options_and_answer_line(self):
        r = pdfimport.process_pdf(make_pdf(LATIN))
        self.assertEqual(len(r["questions"]), 3)
        q = r["questions"][0]
        self.assertEqual([o["is_correct"] for o in q["options"]], [True, False, False, False])
        self.assertEqual(r["questions"][2]["options"][1]["is_correct"], True)   # *B) marker
        self.assertFalse(any(q["needs_review"] for q in r["questions"]))

    def test_cyrillic_uzbek(self):
        r = pdfimport.process_pdf(make_pdf(CYRILLIC))
        self.assertEqual(len(r["questions"]), 2)
        self.assertIn("Темур", r["questions"][0]["text"])
        self.assertTrue(r["questions"][1]["options"][0]["is_correct"])

    def test_numeric_options_with_key(self):
        r = pdfimport.process_pdf(make_pdf(NUMERIC))
        self.assertEqual([[o["is_correct"] for o in q["options"]].index(True) for q in r["questions"]], [1, 2])

    def test_answer_key_section(self):
        r = pdfimport.process_pdf(make_pdf(KEYED))
        self.assertEqual([[o["is_correct"] for o in q["options"]].index(True) for q in r["questions"]], [1, 2, 1])

    def test_missing_answer_flagged_for_review(self):
        lines = ["1. Question one?", "A) a", "B) b", "C) c", "D) d", "2. Question two?", "A) a", "B) b", "C) c", "D) d", "Javob: C"]
        r = pdfimport.process_pdf(make_pdf(lines))
        q1, q2 = r["questions"]
        self.assertTrue(q1["needs_review"])
        self.assertFalse(any(o["is_correct"] for o in q1["options"]))
        self.assertLess(q1["confidence"], 0.6)
        self.assertFalse(q2["needs_review"])

    def test_inline_options_multiline_and_multipage(self):
        lines = ["1. A very long question that continues", "   on a second line?", "A) one  B) two  C) three  D) four", "Answer: B"]
        r = pdfimport.process_pdf(make_pdf(lines))
        q = r["questions"][0]
        self.assertEqual(q["text"], "A very long question that continues on a second line?")
        self.assertEqual(len(q["options"]), 4)
        self.assertTrue(q["options"][1]["is_correct"])
        big = []
        for i in range(1, 121):
            big += [f"{i}. Savol {i}?", "A) bir", "B) ikki", "C) uch", "D) tort", "Javob: B"]
        r = pdfimport.process_pdf(make_pdf(big, per_page=50))
        self.assertEqual(len(r["questions"]), 120)
        self.assertGreaterEqual(r["page_count"], 3)

    def test_invalid_pdf_rejected(self):
        with self.assertRaises(pdfimport.PdfError):
            pdfimport.process_pdf(b"not a pdf at all")
        with self.assertRaises(pdfimport.PdfError):
            pdfimport.process_pdf(b"%PDF-1.4 garbage garbage")

    def test_scanned_pdf_uses_ocr(self):
        lines = ["1. Who built the pyramids", "A) Egyptians", "B) Romans", "C) Vikings", "D) Aztecs", "Answer: A"]
        r = pdfimport.process_pdf(scanned_pdf(lines), ocr_langs="eng")
        self.assertEqual(r["method"], "ocr")
        self.assertEqual(len(r["questions"]), 1)
        self.assertIn("pyramids", r["questions"][0]["text"])
        self.assertTrue(r["questions"][0]["options"][0]["is_correct"])
        self.assertTrue(any("OCR" in w for w in r["warnings"]))


class ImportFlowTests(AppTestCase):
    def upload(self, a, data, name="q.pdf", title="History Set 1", **extra):
        sid = self.db().val("SELECT id FROM subjects ORDER BY id LIMIT 1")
        form = {"title": title, "subject_id": str(sid), "csrf_token": token(a, "/admin/pdf"), "file": (io.BytesIO(data), name)}
        form.update(extra)
        return a.post("/admin/pdf", data=form, content_type="multipart/form-data")

    def test_upload_review_approve_publish(self):
        a = self.admin_client()
        r = self.upload(a, make_pdf(LATIN + ["4. Four?", "A) a", "B) b", "C) c", "D) d"]))
        self.assertEqual(r.status_code, 302)
        tid = self.db().val("SELECT id FROM test_collections")
        db = self.db()
        self.assertEqual(db.val("SELECT status FROM test_collections WHERE id=?", (tid,)), "draft")  # never auto-published
        self.assertEqual(db.val("SELECT COUNT(*) FROM questions WHERE status='pending'"), 4)
        self.assertEqual(db.val("SELECT COUNT(*) FROM uploaded_documents"), 1)
        stored = db.val("SELECT data FROM uploaded_documents")
        self.assertTrue(bytes(stored).startswith(b"%PDF"))
        # students cannot take it yet
        s = self.logged_in("learner")
        self.assertEqual(s.get(f"/tests/{tid}").status_code, 404)
        # publish is refused while questions are pending
        a.post(f"/admin/tests/{tid}/publish", data={"csrf_token": token(a, "/admin/pdf")})
        self.assertEqual(self.db().val("SELECT status FROM test_collections WHERE id=?", (tid,)), "draft")
        # approving fails while a question lacks a correct answer
        qs = a.get(f"/admin/api/tests/{tid}/questions").get_json()["questions"]
        self.assertEqual(sum(q["needs_review"] for q in qs), 1)
        r = self.api(a, f"/admin/api/tests/{tid}/questions", {"questions": qs, "approve": True})
        self.assertEqual(r.status_code, 422)
        # admin fixes it
        bad = [q for q in qs if q["needs_review"]][0]
        bad["options"][2]["is_correct"] = True
        r = self.api(a, f"/admin/api/tests/{tid}/questions", {"questions": qs, "approve": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM questions WHERE status='approved'"), 4)
        a.post(f"/admin/tests/{tid}/publish", data={"csrf_token": token(a, "/admin/pdf")})
        self.assertEqual(self.db().val("SELECT status FROM test_collections WHERE id=?", (tid,)), "published")
        self.assertEqual(s.get(f"/tests/{tid}").status_code, 200)

    def test_edit_delete_reorder_and_add_questions(self):
        a = self.admin_client()
        self.upload(a, make_pdf(LATIN))
        tid = self.db().val("SELECT id FROM test_collections")
        qs = a.get(f"/admin/api/tests/{tid}/questions").get_json()["questions"]
        qs[1]["text"] = "Edited text?"
        qs.reverse()
        qs.pop()
        qs.append({"id": None, "text": "Manual?", "explanation": "because", "options": [{"text": "x", "is_correct": True}, {"text": "y", "is_correct": False}]})
        r = self.api(a, f"/admin/api/tests/{tid}/questions", {"questions": qs, "approve": False})
        self.assertEqual(r.status_code, 200)
        out = r.get_json()["questions"]
        self.assertEqual(len(out), 3)
        self.assertEqual(out[-1]["text"], "Manual?")
        self.assertIn("Edited text?", [q["text"] for q in out])

    def test_rejects_non_pdf_and_invalid_pdf(self):
        a = self.admin_client()
        r = self.upload(a, b"hello", name="evil.exe")
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM uploaded_documents"), 0)
        r = self.upload(a, b"<html>fake</html>", name="fake.pdf")
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM uploaded_documents"), 0)
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM audit_logs WHERE action='pdf_extraction_failed'"), 1)
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM notifications WHERE title='PDF extraction failed'"), 1)

    def test_duplicate_questions_not_imported_twice_into_same_test(self):
        a = self.admin_client()
        self.upload(a, make_pdf(LATIN))
        tid = self.db().val("SELECT id FROM test_collections")
        self.upload(a, make_pdf(LATIN), test_id=str(tid), title="")
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM questions WHERE test_id=?", (tid,)), 3)

    def test_oversized_upload_rejected(self):
        self.app.config["MAX_CONTENT_LENGTH"] = 1000
        a = self.admin_client()
        r = self.upload(a, b"%PDF-" + b"0" * 5000)
        self.assertEqual(r.status_code, 413)
