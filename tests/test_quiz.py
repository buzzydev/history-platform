import json
import threading

from app import quiz
from tests.base import AppTestCase, token


class QuizTests(AppTestCase):
    def start(self, c, tid):
        r = c.post(f"/tests/{tid}/start", data={"csrf_token": token(c, "/tests")})
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:200])
        return int(r.headers["Location"].rsplit("/", 1)[1])

    def state(self, c, aid):
        return c.get(f"/api/attempts/{aid}/state").get_json()

    def test_state_never_leaks_correct_answers(self):
        tid = self.make_test(10, 5)
        c = self.logged_in("leak")
        aid = self.start(c, tid)
        raw = c.get(f"/api/attempts/{aid}/state").get_data(as_text=True)
        self.assertNotIn("is_correct", raw)
        self.assertNotIn("correct_option_id", raw)
        html = c.get(f"/quiz/{aid}").get_data(as_text=True)
        self.assertNotIn("option 0", html)

    def test_no_duplicates_and_stable_order_during_attempt(self):
        tid = self.make_test(30, 10)
        c = self.logged_in("order")
        aid = self.start(c, tid)
        s1, s2 = self.state(c, aid), self.state(c, aid)
        ids = [q["id"] for q in s1["questions"]]
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(set(ids)), 10)
        self.assertEqual(ids, [q["id"] for q in s2["questions"]])
        self.assertEqual([[o["id"] for o in q["options"]] for q in s1["questions"]], [[o["id"] for o in q["options"]] for q in s2["questions"]])
        # starting again resumes the same attempt
        self.assertEqual(self.start(c, tid), aid)

    def test_questions_and_options_are_randomised_between_students(self):
        tid = self.make_test(40, 15)
        seqs, opts = set(), set()
        for i in range(6):
            c = self.logged_in(f"rnd{i}")
            s = self.state(c, self.start(c, tid))
            seqs.add(tuple(q["id"] for q in s["questions"]))
            opts.add(tuple(tuple(o["id"] for o in q["options"]) for q in s["questions"]))
        self.assertGreater(len(seqs), 3)
        self.assertGreater(len(opts), 3)

    def test_correct_answer_stays_associated_with_option(self):
        tid = self.make_test(8, 8)
        c = self.logged_in("assoc")
        aid = self.start(c, tid)
        s = self.state(c, aid)
        db = self.db()
        right = 0
        for q in s["questions"]:
            correct_id = db.val("SELECT id FROM answer_options WHERE question_id=? AND is_correct=1", (q["id"],))
            self.assertIn(correct_id, [o["id"] for o in q["options"]])
            r = self.api(c, f"/api/attempts/{aid}/answer", {"question_id": q["id"], "option_id": correct_id})
            fb = r.get_json()["feedback"]
            self.assertTrue(fb["is_correct"])
            self.assertEqual(fb["correct_option_id"], correct_id)
            right += 1
        done = c.post(f"/api/attempts/{aid}/finish", json={}, headers={"X-CSRF-Token": token(c, "/profile")}).get_json()
        row = self.db().one("SELECT * FROM quiz_attempts WHERE id=?", (aid,))
        self.assertEqual((row["correct_count"], row["incorrect_count"], row["percentage"], row["status"]), (8, 0, 100.0, "completed"))

    def test_wrong_answer_feedback_and_scoring_and_no_changing_answers(self):
        tid = self.make_test(4, 4)
        c = self.logged_in("wrongs")
        aid = self.start(c, tid)
        s = self.state(c, aid)
        q = s["questions"][0]
        db = self.db()
        wrong = db.val("SELECT id FROM answer_options WHERE question_id=? AND is_correct=0 ORDER BY id LIMIT 1", (q["id"],))
        fb = self.api(c, f"/api/attempts/{aid}/answer", {"question_id": q["id"], "option_id": wrong}).get_json()["feedback"]
        self.assertFalse(fb["is_correct"])
        r = self.api(c, f"/api/attempts/{aid}/answer", {"question_id": q["id"], "option_id": wrong})
        self.assertEqual(r.status_code, 409)
        # option from another question is rejected
        other = db.val("SELECT id FROM answer_options WHERE question_id<>? LIMIT 1", (s["questions"][1]["id"],))
        r = self.api(c, f"/api/attempts/{aid}/answer", {"question_id": s["questions"][1]["id"], "option_id": other})
        self.assertEqual(r.status_code, 400)
        c.post(f"/api/attempts/{aid}/finish", json={}, headers={"X-CSRF-Token": token(c, "/profile")})
        row = self.db().one("SELECT * FROM quiz_attempts WHERE id=?", (aid,))
        self.assertEqual((row["correct_count"], row["incorrect_count"], row["percentage"]), (0, 4, 0.0))

    def test_hidden_correct_answers_when_show_correct_disabled(self):
        tid = self.make_test(3, 3, show_correct=0)
        c = self.logged_in("hidden")
        aid = self.start(c, tid)
        q = self.state(c, aid)["questions"][0]
        oid = q["options"][0]["id"]
        raw = self.api(c, f"/api/attempts/{aid}/answer", {"question_id": q["id"], "option_id": oid}).get_data(as_text=True)
        self.assertNotIn("is_correct", raw)
        self.assertNotIn("correct_option_id", raw)

    def test_exposure_history_no_repeat_until_pool_exhausted(self):
        tid = self.make_test(30, 10)
        c = self.logged_in("cycler")
        seen = []
        for _ in range(3):
            aid = self.start(c, tid)
            seen.append({q["id"] for q in self.state(c, aid)["questions"]})
            c.post(f"/api/attempts/{aid}/finish", json={}, headers={"X-CSRF-Token": token(c, "/profile")})
        self.assertEqual(len(seen[0] | seen[1] | seen[2]), 30)       # no repetition across the first 3 attempts
        self.assertFalse(seen[0] & seen[1])
        aid = self.start(c, tid)                                       # 4th attempt starts a new shuffled cycle
        self.assertEqual(len(self.state(c, aid)["questions"]), 10)
        self.assertEqual(self.db().val("SELECT MAX(cycle) FROM question_exposure"), 2)

    def test_partial_pool_then_new_cycle_fills_without_duplicates(self):
        tid = self.make_test(25, 10)
        c = self.logged_in("partial")
        for _ in range(2):
            aid = self.start(c, tid)
            c.post(f"/api/attempts/{aid}/finish", json={}, headers={"X-CSRF-Token": token(c, "/profile")})
        aid = self.start(c, tid)                                       # only 5 unseen left -> 5 + 5 from a new cycle
        ids = [q["id"] for q in self.state(c, aid)["questions"]]
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(set(ids)), 10)

    def test_new_questions_are_preferred(self):
        tid = self.make_test(10, 10)
        c = self.logged_in("newq")
        aid = self.start(c, tid); c.post(f"/api/attempts/{aid}/finish", json={}, headers={"X-CSRF-Token": token(c, "/profile")})
        db = self.db()
        db.execute("INSERT INTO questions(test_id,text,position,status,content_hash,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                   (tid, "Brand new?", 99, "approved", "newhash", "2026-01-01 00:00:00", "2026-01-01 00:00:00"))
        qid = db.val("SELECT id FROM questions WHERE content_hash='newhash'")
        db.execute("INSERT INTO answer_options(question_id,text,is_correct,position) VALUES (?,?,?,?)", (qid, "a", 1, 0))
        db.execute("INSERT INTO answer_options(question_id,text,is_correct,position) VALUES (?,?,?,?)", (qid, "b", 0, 1))
        db.execute("UPDATE test_collections SET questions_per_attempt=3 WHERE id=?", (tid,)); db.commit()
        aid = self.start(c, tid)
        self.assertIn(qid, [q["id"] for q in self.state(c, aid)["questions"]])

    def test_attempt_limit(self):
        tid = self.make_test(5, 5, max_attempts=2)
        c = self.logged_in("limited")
        for _ in range(2):
            aid = self.start(c, tid)
            c.post(f"/api/attempts/{aid}/finish", json={}, headers={"X-CSRF-Token": token(c, "/profile")})
        r = c.post(f"/tests/{tid}/start", data={"csrf_token": token(c, "/tests")})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/tests"))
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM quiz_attempts"), 2)

    def test_time_limit_expires_attempt(self):
        tid = self.make_test(5, 5, time_limit_minutes=10)
        c = self.logged_in("slow")
        aid = self.start(c, tid)
        q = self.state(c, aid)["questions"][0]
        self.api(c, f"/api/attempts/{aid}/answer", {"question_id": q["id"], "option_id": q["options"][0]["id"]})
        db = self.db(); db.execute("UPDATE quiz_attempts SET deadline_at='2000-01-01 00:00:00' WHERE id=?", (aid,)); db.commit()
        r = self.api(c, f"/api/attempts/{aid}/answer", {"question_id": self.state(c, aid)["questions"][1]["id"] if False else q["id"], "option_id": q["options"][1]["id"]})
        self.assertIn(r.status_code, (409, 410))
        row = self.db().one("SELECT * FROM quiz_attempts WHERE id=?", (aid,))
        self.assertEqual(row["status"], "expired")
        self.assertEqual(row["total_questions"], 5)
        self.assertEqual(row["correct_count"] + row["incorrect_count"], 5)

    def test_refresh_restores_unfinished_attempt_and_results_persist(self):
        tid = self.make_test(6, 6)
        c = self.logged_in("persist")
        aid = self.start(c, tid)
        s = self.state(c, aid)
        for q in s["questions"][:3]:
            self.api(c, f"/api/attempts/{aid}/answer", {"question_id": q["id"], "option_id": q["options"][0]["id"]})
        # "refresh" in a brand-new browser session after logging in again
        c2 = self.client_for()
        self.login(c2, "persist", "Passw0rd1")
        s2 = self.state(c2, aid)
        self.assertEqual(s2["answered"], 3)
        self.assertEqual([q["id"] for q in s2["questions"]], [q["id"] for q in s["questions"]])
        self.assertTrue(all("feedback" in q for q in s2["questions"][:3]))
        c2.post(f"/api/attempts/{aid}/finish", json={}, headers={"X-CSRF-Token": token(c2, "/profile")})
        c3 = self.client_for(); self.login(c3, "persist", "Passw0rd1")
        html = c3.get(f"/attempts/{aid}").get_data(as_text=True)
        self.assertIn("Total questions", html)
        row = self.db().one("SELECT * FROM quiz_attempts WHERE id=?", (aid,))
        self.assertEqual(row["status"], "completed")
        self.assertTrue(row["completed_at"])

    def test_unavailable_tests_cannot_be_started(self):
        draft = self.make_test(5, 5, publish=False)
        c = self.logged_in("nodraft")
        r = c.post(f"/tests/{draft}/start", data={"csrf_token": token(c, "/tests")})
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM quiz_attempts"), 0)
        live = self.make_test(5, 5, title="disabled one")
        db = self.db(); db.execute("UPDATE test_collections SET is_enabled=0 WHERE id=?", (live,)); db.commit()
        c.post(f"/tests/{live}/start", data={"csrf_token": token(c, "/tests")})
        db.execute("UPDATE test_collections SET is_enabled=1, expires_at='2000-01-01 00:00:00' WHERE id=?", (live,)); db.commit()
        c.post(f"/tests/{live}/start", data={"csrf_token": token(c, "/tests")})
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM quiz_attempts"), 0)

    def test_any_student_can_take_any_grade_test(self):
        db = self.db()
        g = db.val("SELECT id FROM grades ORDER BY sort_order DESC LIMIT 1")
        tid = self.make_test(5, 5)
        db.execute("UPDATE test_collections SET grade_id=? WHERE id=?", (g, tid)); db.commit()
        c = self.logged_in("anygrade")
        self.assertEqual(c.get(f"/tests/{tid}").status_code, 200)
        self.start(c, tid)

    def test_concurrent_starts_create_one_attempt(self):
        tid = self.make_test(20, 10)
        self.make_user("racer")
        results = []
        def go():
            c = self.client_for()
            self.login(c, "racer", "Passw0rd1")
            r = c.post(f"/tests/{tid}/start", data={"csrf_token": token(c, "/tests")})
            results.append(r.headers.get("Location"))
        ts = [threading.Thread(target=go) for _ in range(6)]
        [t.start() for t in ts]; [t.join() for t in ts]
        db = self.db()
        self.assertEqual(db.val("SELECT COUNT(*) FROM quiz_attempts WHERE status='in_progress'"), 1)
        aid = db.val("SELECT id FROM quiz_attempts")
        self.assertEqual(len(set(results)), 1, results)
        self.assertEqual(db.val("SELECT COUNT(*) FROM attempt_questions WHERE attempt_id=?", (aid,)), 10)
        self.assertEqual(db.val("SELECT COUNT(*) FROM question_exposure"), 10)

    def test_concurrent_answers_same_question_only_one_saved(self):
        tid = self.make_test(3, 3)
        c = self.logged_in("dbl")
        aid = self.start(c, tid)
        q = self.state(c, aid)["questions"][0]
        codes = []
        def go():
            cc = self.client_for(); self.login(cc, "dbl", "Passw0rd1")
            codes.append(self.api(cc, f"/api/attempts/{aid}/answer", {"question_id": q["id"], "option_id": q["options"][0]["id"]}).status_code)
        ts = [threading.Thread(target=go) for _ in range(4)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(codes.count(200), 1, codes)
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM student_answers"), 1)

    def test_leaderboard_is_reliability_weighted(self):
        tid = self.make_test(5, 5)
        db = self.db()
        lucky = self.make_user("lucky"); steady = self.make_user("steady"); weak = self.make_user("weak")
        def add(uid, n, pct):
            for i in range(n):
                db.execute("INSERT INTO quiz_attempts(user_id,test_id,attempt_no,status,total_questions,correct_count,percentage,started_at,completed_at) "
                           "VALUES (?,?,?,?,?,?,?,?,?)", (uid, tid, i + 1, "completed", 5, 0, pct, "2026-01-01 00:00:00", "2026-01-01 00:10:00"))
        add(lucky, 1, 100); add(steady, 6, 90); add(weak, 4, 40)
        db.commit()
        rows = quiz.leaderboard(db, 10)
        names = [r["username"] for r in rows]
        self.assertNotIn("lucky", names)                       # below minimum attempts
        self.assertEqual(names, ["steady", "weak"])
        rows = quiz.leaderboard(db, 10, min_attempts=1)
        self.assertEqual([r["username"] for r in rows][0], "steady")   # single lucky 100% does not beat 6x90%
