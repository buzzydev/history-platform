# JSON API

All requests need the session cookie and header `X-CSRF-Token` (value of `<meta name="csrf-token">`). Authorization is verified on the server for every call.

## Student quiz API (`/api`, login required, only your own attempts)
| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/api/attempts/<id>/state` | – | Attempt, questions in saved random order, options (never `is_correct`), feedback for answered questions, `remaining_seconds` |
| POST | `/api/attempts/<id>/answer` | `{question_id, option_id}` | `{feedback}`; `correct_option_id` and `explanation` only if the test allows it; 409 if already answered, 410 if time is up |
| POST | `/api/attempts/<id>/finish` | `{}` | `{redirect}`; computes and stores the score |
| POST | `/api/notifications/read` | `{}` | marks all notifications read |

## Admin question editor (`/admin/api`, admin only)
| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/admin/api/tests/<id>/questions` | – | `{questions:[{id,text,explanation,status,needs_review,confidence,warnings,options:[{id,text,is_correct}]}]}` |
| POST | `/admin/api/tests/<id>/questions` | `{questions:[...], approve:bool}` | saves the whole list (add/edit/delete/reorder). `approve:true` returns 422 with `problems` if any question has no single correct answer |

## Health
`GET /healthz` → `{"status":"ok"}` (used by Railway).
