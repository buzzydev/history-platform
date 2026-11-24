import { t } from "./i18n.js";
import { api } from "./api.js";
import { toast } from "./toast.js";
import { confirmDialog } from "./modal.js";

const root = document.getElementById("quiz-root");
const attemptId = root.dataset.attemptId;
let state = null;
let idx = 0;
let timerId = null;
let remaining = null;
let finishing = false;

const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

function skeleton() {
  root.replaceChildren();
  for (let i = 0; i < 3; i++) { const s = el("div", "skeleton"); s.style.height = i ? "56px" : "90px"; s.style.marginBottom = "10px"; root.appendChild(s); }
}

async function load() {
  skeleton();
  const r = await api(`/api/attempts/${attemptId}/state`);
  if (!r.ok) { root.replaceChildren(el("div", "notice danger", r.data.error || t("Could not load the quiz."))); return; }
  state = r.data;
  if (state.status !== "in_progress") { window.location.href = `/attempts/${attemptId}`; return; }
  const first = state.questions.findIndex((q) => !q.feedback);
  idx = first === -1 ? 0 : first;
  remaining = state.remaining_seconds;
  render();
  startTimer();
}

function startTimer() {
  if (remaining === null) return;
  clearInterval(timerId);
  timerId = setInterval(() => {
    remaining -= 1;
    const t = document.getElementById("timer");
    if (t) { t.textContent = fmt(Math.max(0, remaining)); t.classList.toggle("low", remaining <= 60); }
    if (remaining <= 0) { clearInterval(timerId); finish(true); }
  }, 1000);
}

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

function render() {
  const q = state.questions[idx];
  const answered = state.questions.filter((x) => x.feedback).length;
  root.replaceChildren();

  const top = el("div", "quiz-top");
  top.append(el("div", "muted", t("Question {n} of {total} \u2022 {a} answered", { n: idx + 1, total: state.total, a: answered })));
  if (remaining !== null) top.append(el("div", "timer" + (remaining <= 60 ? " low" : ""), fmt(Math.max(0, remaining))));
  top.lastChild.id = remaining !== null ? "timer" : "";
  root.appendChild(top);

  const bar = el("div", "progress"); const fill = el("i"); fill.style.width = (answered / state.total * 100) + "%"; bar.appendChild(fill);
  root.appendChild(bar);

  const nav = el("div", "qnav");
  state.questions.forEach((x, i) => {
    const b = el("button", "", String(i + 1));
    b.type = "button";
    b.setAttribute("aria-label", t("Go to question {n}", { n: i + 1 }));
    if (i === idx) b.classList.add("current");
    if (x.feedback) b.classList.add(x.feedback.is_correct === true ? "right" : x.feedback.is_correct === false ? "wrong" : "done");
    b.addEventListener("click", () => { idx = i; render(); });
    nav.appendChild(b);
  });
  root.appendChild(nav);

  const card = el("div", "card");
  card.appendChild(el("div", "q-text", q.text));
  const opts = el("div", "options");
  q.options.forEach((o, i) => {
    const b = el("button", "option");
    b.type = "button";
    b.append(el("span", "key", String.fromCharCode(65 + i)), el("span", "", o.text));
    const fb = q.feedback;
    if (fb) {
      b.disabled = true;
      if (fb.selected_option_id === o.id) b.classList.add(fb.is_correct === undefined ? "picked" : (fb.is_correct ? "correct" : "wrong"));
      if (fb.correct_option_id === o.id) b.classList.add("correct");
    } else {
      b.addEventListener("click", () => choose(q, o.id, opts));
    }
    opts.appendChild(b);
  });
  card.appendChild(opts);
  if (q.feedback) {
    const fb = q.feedback;
    if (fb.is_correct !== undefined) card.appendChild(el("p", "small", fb.is_correct ? t("\u2705 Correct!") : t("\u274C Incorrect.")));
    else card.appendChild(el("p", "small muted", t("Answer saved.")));
    if (fb.explanation) card.appendChild(el("div", "explain", fb.explanation));
  }
  root.appendChild(card);

  const nav2 = el("div", "row between");
  nav2.style.marginTop = "14px";
  const prev = el("button", "btn", t("\u2190 Previous")); prev.type = "button"; prev.disabled = idx === 0;
  prev.addEventListener("click", () => { idx -= 1; render(); });
  const next = el("button", "btn primary", idx === state.total - 1 ? t("Finish") : t("Next \u2192")); next.type = "button";
  next.addEventListener("click", () => { if (idx === state.total - 1) finish(false); else { idx += 1; render(); } });
  nav2.append(prev, next);
  root.appendChild(nav2);
  if (answered === state.total) {
    const f = el("button", "btn primary block", t("Submit and see results")); f.type = "button"; f.style.marginTop = "12px";
    f.addEventListener("click", () => finish(false));
    root.appendChild(f);
  }
}

async function choose(q, optionId, optsBox) {
  optsBox.querySelectorAll("button").forEach((b) => { b.disabled = true; });
  const r = await api(`/api/attempts/${attemptId}/answer`, { method: "POST", body: { question_id: q.id, option_id: optionId } });
  if (r.ok) {
    q.feedback = r.data.feedback;
    render();
  } else {
    toast(r.data.error || t("Could not save the answer."), "error");
    if (r.status === 410) { window.location.href = `/attempts/${attemptId}`; return; }
    if (r.status === 409) { await load(); return; }
    optsBox.querySelectorAll("button").forEach((b) => { b.disabled = false; });
  }
}

async function finish(auto) {
  if (finishing) return;
  const unanswered = state.questions.filter((x) => !x.feedback).length;
  if (!auto && unanswered) {
    const ok = await confirmDialog({ title: t("Submit the test?"), message: t("{n} question(s) are unanswered and will count as incorrect.", { n: unanswered }), confirmText: t("Submit"), danger: false });
    if (!ok) return;
  }
  finishing = true;
  const r = await api(`/api/attempts/${attemptId}/finish`, { method: "POST", body: {} });
  if (r.ok) { window.location.href = r.data.redirect; }
  else { finishing = false; toast(r.data.error || t("Could not submit."), "error"); }
}

load();
