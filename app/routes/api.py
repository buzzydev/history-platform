from flask import Blueprint, g, jsonify, request

from .. import quiz
from ..audit import audit
from ..db import get_db
from ..security import login_required

bp = Blueprint("api", __name__, url_prefix="/api")


def _attempt(aid):
    return quiz.get_attempt_for(get_db(), aid, g.user["id"])


@bp.errorhandler(quiz.QuizError)
def _qe(e):
    get_db().rollback()
    return jsonify(error=str(e)), e.status


@bp.get("/attempts/<int:aid>/state")
@login_required
def state(aid):
    db = get_db()
    return jsonify(quiz.attempt_state(db, _attempt(aid)))


@bp.post("/attempts/<int:aid>/answer")
@login_required
def answer(aid):
    data = request.get_json(silent=True) or {}
    try:
        qid, oid = int(data.get("question_id")), int(data.get("option_id"))
    except (TypeError, ValueError):
        return jsonify(error="question_id and option_id are required."), 400
    db = get_db()
    fb = quiz.submit_answer(db, _attempt(aid), qid, oid)
    return jsonify(feedback=fb)


@bp.post("/attempts/<int:aid>/finish")
@login_required
def finish(aid):
    db = get_db()
    a = _attempt(aid)
    done = quiz.finish_attempt(db, a["id"])
    audit("quiz_completed", "attempt", aid, score=done["percentage"])
    return jsonify(ok=True, redirect=f"/attempts/{aid}")
