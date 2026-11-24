"""PDF text/OCR extraction and multiple-choice question parsing (Latin, Cyrillic, Uzbek)."""
import hashlib
import io
import re
import unicodedata

LET = "A-Ea-eАБВГДабвгд"
OPT_RE = re.compile(r"^\s*[*+✓✔√#]?\s*[\(\[]?([%s])(?:[\)\]]\s*|[.:]\s+)(.*)$" % LET)
INLINE_SPLIT_RE = re.compile(r"(?:(?<=\s)|^)([%s])[\)\]]\s+" % LET)
Q_RE = re.compile(
    r"^\s*(?:(?:№|#|N[oO]?\.?|Savol|SAVOL|Вопрос|ВОПРОС|Савол|САВОЛ|Question|QUESTION)\s*(\d{1,4})|(\d{1,3}))"
    r"\s*[.)\]:](?!\d)\s*(.*)$")
NUM_OPT_RE = re.compile(r"^\s*(\d{1,2})\s*[.)]\s*(.*)$")
ANS_RE = re.compile(
    r"^\s*(?:to['’ʻʼ`]?g['’ʻʼ`]?ri\s+javob|togri\s+javob|javob|жавоб|тўғри\s+жавоб|тугри\s+жавоб|"
    r"correct\s+answer|answer|correct|key|ответ|правильный\s+ответ|верный\s+ответ)"
    r"\s*[:\-–=]*\s*\(?\s*([A-Ea-eАБВГДабвгд1-5])\s*\)?(?!\w)", re.I)
KEY_HEADER_RE = re.compile(r"^\s*(javoblar|kalitlar|kalit|answers?|answer\s+key|keys?|ключ|ответы|жавоблар|калитлар)\b[\s:.\-]*", re.I)
PAIR_RE = re.compile(r"(\d{1,4})(?:\s*[-–.):=]+\s*([%s1-5])|\s*([%s]))(?!\w)" % (LET, LET))


def _pairs(s):
    return [(int(a), b or c) for a, b, c in PAIR_RE.findall(s)]
MARK_LEAD_RE = re.compile(r"^\s*([*+✓✔√#])\s*")
MARK_TRAIL_RE = re.compile(r"\s+(\*|\(\+\)|\+|✓|✔|√)\s*$")
LOOKALIKE = {"А": "A", "В": "B", "С": "C", "Е": "E", "а": "a", "е": "e"}
CYR_INDEX = {"А": 0, "Б": 1, "В": 2, "Г": 3, "Д": 4}


class PdfError(Exception):
    pass


def _norm_letter(ch):
    return ch.upper()


def _canon(ch):
    ch = ch.upper()
    return LOOKALIKE.get(ch, ch)


def clean_text(t):
    t = unicodedata.normalize("NFC", t or "")
    t = t.replace("\u00a0", " ").replace("\u00ad", "").replace("\r", "\n").replace("\f", "\n")
    return t


def extract_text(data, max_pages=300, ocr_langs="uzb+uzb_cyrl+rus+eng"):
    """Return (pages:list[str], method:str, warnings:list[str])."""
    if not data[:5] == b"%PDF-":
        raise PdfError("The file is not a valid PDF (missing %PDF header).")
    import pdfplumber
    warnings = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            n = len(pdf.pages)
            if n == 0:
                raise PdfError("The PDF has no pages.")
            if n > max_pages:
                raise PdfError(f"The PDF has {n} pages; the limit is {max_pages}.")
            pages = [clean_text(p.extract_text() or "") for p in pdf.pages]
    except PdfError:
        raise
    except Exception as e:
        raise PdfError(f"The PDF could not be read: {type(e).__name__}.") from e
    method = "text"
    weak = [i for i, t in enumerate(pages) if len(t.strip()) < 25]
    if weak:
        try:
            ocr = ocr_pages(data, weak, ocr_langs)
            for i, t in ocr.items():
                pages[i] = clean_text(t)
            method = "ocr" if len(weak) == len(pages) else "mixed"
        except Exception as e:  # OCR engine missing etc.
            warnings.append(f"{len(weak)} page(s) have no text layer and OCR failed: {e}")
    return pages, method, warnings


def ocr_pages(data, indexes, langs):
    import pypdfium2 as pdfium
    import pytesseract
    avail = set(pytesseract.get_languages(config=""))
    use = [l for l in langs.split("+") if l in avail]
    if not use:
        raise RuntimeError("no Tesseract language packs installed")
    doc = pdfium.PdfDocument(data)
    out = {}
    for i in indexes:
        img = doc[i].render(scale=200 / 72).to_pil()
        out[i] = pytesseract.image_to_string(img, lang="+".join(use))
    return out


def question_hash(text, options):
    key = re.sub(r"\W+", "", text.lower()) + "|" + "|".join(sorted(re.sub(r"\W+", "", o.lower()) for o in options))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _tidy(s):
    return re.sub(r"\s+", " ", s or "").strip()


def parse_questions(pages, method="text"):
    """Parse extracted page texts. Returns dict(questions=[...], warnings=[...])."""
    lines = []
    for t in pages:
        for ln in t.split("\n"):
            if re.fullmatch(r"\s*[-–—]?\s*\d{1,3}\s*[-–—]?\s*", ln):  # bare page numbers
                continue
            if ln.strip():
                lines.append(ln.rstrip())
    letter_lines = sum(max(1, len(INLINE_SPLIT_RE.findall(ln))) for ln in lines if OPT_RE.match(ln))
    letter_mode = letter_lines >= 2

    questions, cur, key, in_key = [], None, {}, False
    for ln in lines:
        if KEY_HEADER_RE.match(ln) and (cur is not None or questions):
            rest = KEY_HEADER_RE.sub("", ln)
            if not rest.strip() or PAIR_RE.search(rest):
                in_key = True
                for n, l in _pairs(rest):
                    key[n] = l
                continue
        if in_key:
            for n, l in _pairs(ln):
                key[n] = l
            continue
        pairs = _pairs(ln)
        if len(pairs) >= 3 and not PAIR_RE.sub("", ln).strip(" ,;.-–\t"):
            for n, l in pairs:
                key[n] = l
            continue
        am = ANS_RE.match(ln)
        if am and cur is not None:
            cur["answer_letter"] = am.group(1)
            continue
        if letter_mode:
            om = OPT_RE.match(ln) if cur is not None else None
            if om:
                _add_letter_options(cur, ln)
                continue
            qm = Q_RE.match(ln)
            if qm:
                cur = _new_q(questions, qm)
                continue
        else:
            qm = Q_RE.match(ln)
            nm = NUM_OPT_RE.match(ln)
            if cur is not None and nm and cur["text"] and int(nm.group(1)) == len(cur["options"]) + 1 \
                    and (cur["options"] or int(nm.group(1)) == 1):
                _add_option(cur, str(len(cur["options"]) + 1), nm.group(2))
                continue
            if qm:
                cur = _new_q(questions, qm)
                continue
        if cur is not None:  # continuation line
            if cur["options"]:
                cur["options"][-1]["text"] += " " + ln.strip()
            else:
                cur["text"] += " " + ln.strip()

    return _finalize(questions, key, method, letter_mode)


def _new_q(questions, m):
    num = int(m.group(1) or m.group(2))
    q = {"number": num, "text": m.group(3).strip(), "options": [], "answer_letter": None}
    questions.append(q)
    return q


def _add_option(q, label, text):
    text = text.strip()
    correct = False
    mm = MARK_LEAD_RE.match(text)
    if mm:
        correct, text = True, text[mm.end():]
    mt = MARK_TRAIL_RE.search(text)
    if mt:
        correct, text = True, text[:mt.start()]
    q["options"].append({"label": label, "text": text.strip(), "marked": correct})


def _add_letter_options(q, line):
    stripped = MARK_LEAD_RE.sub("", line, count=1) if MARK_LEAD_RE.match(line) else line
    lead_mark = bool(MARK_LEAD_RE.match(line))
    starts = [m for m in INLINE_SPLIT_RE.finditer(stripped)]
    first = OPT_RE.match(stripped)
    if len(starts) >= 2 and first:
        bounds = [m.start() for m in starts] + [len(stripped)]
        for i, m in enumerate(starts):
            seg = stripped[bounds[i]:bounds[i + 1]]
            om = OPT_RE.match(seg)
            if om:
                _add_option(q, om.group(1), om.group(2))
        if lead_mark and q["options"]:
            q["options"][-len(starts)]["marked"] = True
    else:
        om = OPT_RE.match(stripped)
        _add_option(q, om.group(1), om.group(2))
        if lead_mark:
            q["options"][-1]["marked"] = True


def _resolve_letter(q, letter):
    letter = letter.strip()
    if letter.isdigit():
        i = int(letter) - 1
        return i if 0 <= i < len(q["options"]) else None
    exact = [i for i, o in enumerate(q["options"]) if o["label"].upper() == letter.upper()]
    if len(exact) == 1:
        return exact[0]
    canon = [i for i, o in enumerate(q["options"]) if _canon(o["label"]) == _canon(letter)]
    if len(canon) == 1:
        return canon[0]
    idx = "ABCDE".find(_canon(letter))
    if idx < 0:
        idx = CYR_INDEX.get(letter.upper(), -1)
    return idx if 0 <= idx < len(q["options"]) else None


def _finalize(raw, key, method, letter_mode):
    out, warnings, seen_hash = [], [], set()
    for q in raw:
        text = _tidy(q["text"])
        opts = [{"text": _tidy(o["text"]), "marked": o["marked"]} for o in q["options"]]
        warns, conf, correct = [], 1.0, None
        marked = [i for i, o in enumerate(opts) if o["marked"]]
        by_line = _resolve_letter(q, q["answer_letter"]) if q["answer_letter"] else None
        by_key = _resolve_letter(q, key[q["number"]]) if q["number"] in key else None
        if len(marked) > 1:
            warns.append("Several options are marked as correct.")
        elif len(marked) == 1:
            correct = marked[0]
        if correct is None and by_line is not None:
            correct = by_line
        if correct is None and by_key is not None:
            correct = by_key
            conf = 0.9
        elif by_key is not None and by_key != correct:
            warns.append("The answer key disagrees with the answer found beside the question.")
            correct = None
        if q["answer_letter"] and by_line is None:
            warns.append("The answer line could not be matched to an option.")
        if correct is None:
            conf = min(conf, 0.3)
            warns.append("Correct answer not detected - choose it manually.")
        if len(opts) < 2:
            conf = min(conf, 0.2)
            warns.append("Fewer than two answer options were found.")
        elif len(opts) < 4:
            conf = min(conf, 0.7)
            warns.append(f"Only {len(opts)} answer options were found.")
        if any(not o["text"] for o in opts):
            warns.append("An answer option is empty.")
            conf = min(conf, 0.5)
        if not text:
            warns.append("Question text is empty.")
            conf = min(conf, 0.2)
        if method != "text":
            conf = round(conf * 0.85, 2)
        needs = correct is None or len(opts) < 2 or conf < 0.6 or any("empty" in w for w in warns)
        h = question_hash(text, [o["text"] for o in opts])
        if h in seen_hash:
            warnings.append(f"Question {q['number']} is a duplicate inside this file and was skipped.")
            continue
        seen_hash.add(h)
        out.append({"number": q["number"], "text": text,
                    "options": [{"text": o["text"], "is_correct": i == correct} for i, o in enumerate(opts)],
                    "confidence": round(conf, 2), "needs_review": needs, "warnings": warns, "hash": h})
    if not out:
        warnings.append("No questions were recognised. Check the numbering and answer format of the PDF.")
    nums = [q["number"] for q in out]
    for a, b in zip(nums, nums[1:]):
        if b != a + 1 and b > a:
            warnings.append(f"Question numbers jump from {a} to {b}; a question may be missing.")
    if method != "text":
        warnings.append("OCR was used; please review the text carefully.")
    return {"questions": out, "warnings": warnings, "mode": "letters" if letter_mode else "numbers"}


def process_pdf(data, max_pages=300, ocr_langs="uzb+uzb_cyrl+rus+eng"):
    pages, method, warns = extract_text(data, max_pages, ocr_langs)
    res = parse_questions(pages, method)
    res["warnings"] = warns + res["warnings"]
    res["method"] = method
    res["page_count"] = len(pages)
    return res
