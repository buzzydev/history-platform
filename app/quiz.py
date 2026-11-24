"""Server-side quiz engine: fair randomisation, anti-repeat exposure history, grading."""
import json
import random
from datetime import datetime, timedelta, timezone

from .db import IntegrityError, fmt, get_db, parse, utcnow, get_setting
from .audit import notify

_rng = random.SystemRandom()


class QuizError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def test_is_available(t, now=None):
    now = now or utcnow()
    return bool(t and t["status"] == "published" and t["is_enabled"]
                and (not t["publish_at"] or t["publish_at"] <= now)
                and (not t["expires_at"] or t["expires_at"] > now))


def pick_questions(db, user_id, test_id, pool_ids, n):
    """Return (ordered chosen ids, [(question_id, cycle)]) honouring the exposure history."""
    cycle = db.val("SELECT MAX(cycle) FROM question_exposure WHERE user_id = ? AND test_id = ?", (user_id, test_id), 1) or 1
    seen = {r["question_id"] for r in db.all(
        "SELECT question_id FROM question_exposure WHERE user_id = ? AND test_id = ? AND cycle = ?",
        (user_id, test_id, cycle))}
    unseen = [q for q in pool_ids if q not in seen]
    if len(unseen) >= n:
        chosen = _rng.sample(unseen, n)
        records = [(q, cycle) for q in chosen]
    else:
        chosen = list(unseen)
        records = [(q, cycle) for q in chosen]
        rest = [q for q in pool_ids if q not in set(unseen)]
        extra = _rng.sample(rest, n - len(unseen))
        chosen += extra
        records += [(q, cycle + 1) for q in extra]
    return chosen, records


def start_or_resume(db, user, test_id):
    db.lock_user(user["id"])
    t = db.one("SELECT * FROM test_collections WHERE id = ?", (test_id,))
    if not test_is_available(t):
        raise QuizError("This test is not available.", 404)
    existing = db.one("SELECT * FROM quiz_attempts WHERE user_id = ? AND test_id = ? AND status = 'in_progress'",
                      (user["id"], test_id))
    if existing:
        if existing["deadline_at"] and existing["deadline_at"] < utcnow():
            finish_attempt(db, existing["id"], forced=True)
        else:
            return existing["id"], False
    used = db.val("SELECT COUNT(*) FROM quiz_attempts WHERE user_id = ? AND test_id = ?", (user["id"], test_id), 0)
    if t["max_attempts"] and used >= t["max_attempts"]:
        raise QuizError("You have used all attempts for this test.", 403)
    pool = [r["id"] for r in db.all(
        "SELECT id FROM questions WHERE test_id = ? AND status = 'approved' ORDER BY position, id", (test_id,))]
    if not pool:
        raise QuizError("This test has no approved questions yet.", 409)
    n = min(t["questions_per_attempt"] or len(pool), len(pool))
    chosen, records = pick_questions(db, user["id"], test_id, pool, n)
    if t["randomize_questions"]:
        _rng.shuffle(chosen)
    else:
        order = {q: i for i, q in enumerate(pool)}
        chosen.sort(key=lambda q: order[q])
    attempt_no = (db.val("SELECT MAX(attempt_no) FROM quiz_attempts WHERE user_id = ? AND test_id = ?",
                         (user["id"], test_id), 0) or 0) + 1
    now = datetime.now(timezone.utc)
    deadline = fmt(now + timedelta(minutes=t["time_limit_minutes"])) if t["time_limit_minutes"] else None
    aid = db.insert(
        "INSERT INTO quiz_attempts(user_id,test_id,attempt_no,status,question_ids,total_questions,started_at,deadline_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (user["id"], test_id, attempt_no, "in_progress", json.dumps(chosen), len(chosen), fmt(now), deadline))
    for pos, qid in enumerate(chosen, start=1):
        opts = [r["id"] for r in db.all("SELECT id FROM answer_options WHERE question_id = ? ORDER BY position, id", (qid,))]
        if t["randomize_options"]:
            _rng.shuffle(opts)
        db.execute("INSERT INTO attempt_questions(attempt_id,question_id,position,option_order) VALUES (?,?,?,?)",
                   (aid, qid, pos, json.dumps(opts)))
    for qid, cyc in records:
        db.execute("INSERT INTO question_exposure(user_id,test_id,question_id,cycle,attempt_id,served_at) VALUES (?,?,?,?,?,?)",
                   (user["id"], test_id, qid, cyc, aid, fmt(now)))
    return aid, True


def get_attempt_for(db, attempt_id, user_id):
    a = db.one("SELECT * FROM quiz_attempts WHERE id = ? AND user_id = ?", (attempt_id, user_id))
    if not a:
        raise QuizError("Attempt not found.", 404)
    return a


def _expired(a, grace=5):
    if a["status"] != "in_progress" or not a["deadline_at"]:
        return False
    return parse(a["deadline_at"]) + timedelta(seconds=grace) < datetime.now(timezone.utc)


def feedback_for(t, correct_option_id, explanation, chosen_id, is_correct):
    fb = {"selected_option_id": chosen_id, "is_correct": bool(is_correct)}
    if t["show_correct"]:
        fb["correct_option_id"] = correct_option_id
    if t["show_explanation"] and explanation:
        fb["explanation"] = explanation
    return fb


def attempt_state(db, a):
    t = db.one("SELECT * FROM test_collections WHERE id = ?", (a["test_id"],))
    if a["status"] == "in_progress" and _expired(a, grace=0):
        finish_attempt(db, a["id"], forced=True)
        a = db.one("SELECT * FROM quiz_attempts WHERE id = ?", (a["id"],))
    rows = db.all(
        "SELECT aq.position, aq.option_order, q.id AS qid, q.text, q.explanation FROM attempt_questions aq "
        "JOIN questions q ON q.id = aq.question_id WHERE aq.attempt_id = ? ORDER BY aq.position", (a["id"],))
    answers = {r["question_id"]: r for r in db.all("SELECT * FROM student_answers WHERE attempt_id = ?", (a["id"],))}
    questions = []
    for r in rows:
        order = json.loads(r["option_order"])
        opt_rows = {o["id"]: o for o in db.all("SELECT id, text, is_correct FROM answer_options WHERE question_id = ?", (r["qid"],))}
        item = {"id": r["qid"], "position": r["position"], "text": r["text"],
                "options": [{"id": oid, "text": opt_rows[oid]["text"]} for oid in order if oid in opt_rows]}
        ans = answers.get(r["qid"])
        if ans:
            correct = next((o["id"] for o in opt_rows.values() if o["is_correct"]), None)
            item["feedback"] = feedback_for(t, correct, r["explanation"], ans["option_id"], ans["is_correct"])
            if not t["show_correct"]:
                item["feedback"].pop("is_correct", None)
                item["feedback"]["recorded"] = True
        questions.append(item)
    remaining = None
    if a["deadline_at"] and a["status"] == "in_progress":
        remaining = max(0, int((parse(a["deadline_at"]) - datetime.now(timezone.utc)).total_seconds()))
    return {"attempt_id": a["id"], "status": a["status"], "title": t["title"], "show_correct": bool(t["show_correct"]),
            "total": len(questions), "answered": len(answers), "remaining_seconds": remaining, "questions": questions}


def submit_answer(db, a, question_id, option_id):
    if a["status"] != "in_progress":
        raise QuizError("This attempt is already finished.", 409)
    if _expired(a):
        finish_attempt(db, a["id"], forced=True)
        db.commit()  # keep the auto-submission even though the request ends with an error
        raise QuizError("Time is up. The attempt was submitted.", 410)
    t = db.one("SELECT * FROM test_collections WHERE id = ?", (a["test_id"],))
    aq = db.one("SELECT * FROM attempt_questions WHERE attempt_id = ? AND question_id = ?", (a["id"], question_id))
    if not aq:
        raise QuizError("Question is not part of this attempt.", 400)
    if option_id not in json.loads(aq["option_order"]):
        raise QuizError("Invalid answer option.", 400)
    opt = db.one("SELECT * FROM answer_options WHERE id = ? AND question_id = ?", (option_id, question_id))
    if not opt:
        raise QuizError("Invalid answer option.", 400)
    try:
        db.execute("INSERT INTO student_answers(attempt_id,question_id,option_id,is_correct,answered_at) VALUES (?,?,?,?,?)",
                   (a["id"], question_id, option_id, 1 if opt["is_correct"] else 0, utcnow()))
    except IntegrityError:
        db.rollback()
        raise QuizError("This question was already answered.", 409)
    q = db.one("SELECT explanation FROM questions WHERE id = ?", (question_id,))
    correct = db.val("SELECT id FROM answer_options WHERE question_id = ? AND is_correct = 1", (question_id,))
    fb = feedback_for(t, correct, q["explanation"], option_id, opt["is_correct"])
    if not t["show_correct"]:
        fb = {"selected_option_id": option_id, "recorded": True}
    return fb


def finish_attempt(db, attempt_id, forced=False):
    a = db.one("SELECT * FROM quiz_attempts WHERE id = ?", (attempt_id,))
    if a["status"] != "in_progress":
        return a
    total = db.val("SELECT COUNT(*) FROM attempt_questions WHERE attempt_id = ?", (attempt_id,), 0)
    correct = db.val("SELECT COUNT(*) FROM student_answers WHERE attempt_id = ? AND is_correct = 1", (attempt_id,), 0)
    started = parse(a["started_at"])
    end = datetime.now(timezone.utc)
    if a["deadline_at"] and parse(a["deadline_at"]) < end:
        end = parse(a["deadline_at"])
    spent = max(0, int((end - started).total_seconds()))
    pct = round(100.0 * correct / total, 2) if total else 0.0
    status = "expired" if forced else "completed"
    db.execute(
        "UPDATE quiz_attempts SET status=?, correct_count=?, incorrect_count=?, percentage=?, completed_at=?, time_spent_seconds=? "
        "WHERE id = ? AND status = 'in_progress'",
        (status, correct, total - correct, pct, fmt(end if forced else datetime.now(timezone.utc)), spent, attempt_id))
    t = db.one("SELECT title FROM test_collections WHERE id = ?", (a["test_id"],))
    notify(a["user_id"], "Test completed", f"{t['title']}: {correct}/{total} ({pct:.0f}%)", "success", db=db)
    return db.one("SELECT * FROM quiz_attempts WHERE id = ?", (attempt_id,))


def leaderboard(db, limit=100, min_attempts=None):
    """Bayesian-weighted ranking: (C*m + sum(pct)) / (C + n)."""
    min_attempts = int(get_setting("leaderboard_min_attempts", db)) if min_attempts is None else min_attempts
    C = float(get_setting("leaderboard_prior_strength", db))
    m = db.val("SELECT AVG(percentage) FROM quiz_attempts WHERE status IN ('completed','expired')", (), 0.0) or 0.0
    rows = db.all(
        "SELECT u.id, u.username, COUNT(a.id) AS attempts, AVG(a.percentage) AS avg_pct, SUM(a.percentage) AS sum_pct, "
        "SUM(a.correct_count) AS correct, MAX(a.percentage) AS best "
        "FROM quiz_attempts a JOIN users u ON u.id = a.user_id "
        "WHERE a.status IN ('completed','expired') AND u.is_blocked = 0 AND u.role = 'student' "
        "GROUP BY u.id, u.username")
    out = []
    for r in rows:
        if r["attempts"] < min_attempts:
            continue
        r["score"] = round((C * m + (r["sum_pct"] or 0)) / (C + r["attempts"]), 2)
        r["avg_pct"] = round(r["avg_pct"] or 0, 1)
        out.append(r)
    out.sort(key=lambda r: (-r["score"], -r["attempts"], r["username"].lower()))
    for i, r in enumerate(out[:limit], 1):
        r["rank"] = i
    return out[:limit]


def user_stats(db, user_id):
    r = db.one("SELECT COUNT(*) AS n, AVG(percentage) AS avg, MAX(percentage) AS best, SUM(correct_count) AS correct "
               "FROM quiz_attempts WHERE user_id = ? AND status IN ('completed','expired')", (user_id,))
    return {"completed": r["n"] or 0, "average": round(r["avg"] or 0, 1), "best": round(r["best"] or 0, 1),
            "correct": r["correct"] or 0}
