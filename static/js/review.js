import { t } from "./i18n.js";
import { api } from "./api.js";
import { toast } from "./toast.js";
import { confirmDialog, openModal } from "./modal.js";

const root = document.getElementById("review-root");
const tid = root.dataset.testId;
let questions = [];
let dirty = false;

const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const ICON = {
  trash: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6"/></svg>',
  up: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>',
  down: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M19 12l-7 7-7-7"/></svg>',
  eye: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  x: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>',
};
const iconBtn = (cls, label, svg, fn) => {
  const b = el("button", "act " + cls); b.type = "button"; b.setAttribute("aria-label", label); b.title = label; b.innerHTML = svg;
  b.addEventListener("click", fn); return b;
};

function blank() { return { id: null, text: "", explanation: "", status: "pending", needs_review: true, confidence: 1, warnings: [], options: [0, 1, 2, 3].map(() => ({ id: null, text: "", is_correct: false })) }; }
const problems = (q) => {
  const p = [];
  if (!q.text.trim()) p.push(t("Question text is empty"));
  if (q.options.length < 2) p.push(t("At least two options needed"));
  if (q.options.some((o) => !o.text.trim())) p.push(t("An option is empty"));
  if (q.options.filter((o) => o.is_correct).length !== 1) p.push(t("Choose exactly one correct answer"));
  return p;
};

async function load() {
  root.replaceChildren(el("div", "skeleton"), el("div", "skeleton"), el("div", "skeleton"));
  root.querySelectorAll(".skeleton").forEach((s) => { s.style.height = "120px"; s.style.marginBottom = "12px"; });
  const r = await api(`/admin/api/tests/${tid}/questions`);
  if (!r.ok) { root.replaceChildren(el("div", "notice danger", r.data.error || t("Could not load questions."))); return; }
  questions = r.data.questions; dirty = false;
  render();
}

function render() {
  root.replaceChildren();
  const pending = questions.filter((q) => q.status !== "approved").length;
  const head = el("div", "row between");
  head.append(el("div", "muted", t("{n} question(s) \u2022 {p} awaiting approval", { n: questions.length, p: pending })));
  const add = el("button", "btn", t("+ Add question")); add.type = "button";
  add.addEventListener("click", () => { questions.push(blank()); dirty = true; render(); window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }); });
  head.appendChild(add);
  root.appendChild(head);
  if (!questions.length) {
    const e = el("div", "empty card"); e.append(el("p", "", t("No questions yet. Upload a PDF or add a question manually.")));
    root.appendChild(e);
  }
  questions.forEach((q, i) => root.appendChild(card(q, i)));

  const bar = el("div", "sticky-bar");
  const save = el("button", "btn", t("Save draft")); save.type = "button"; save.addEventListener("click", () => persist(false));
  const approve = el("button", "btn primary", t("Approve all questions")); approve.type = "button"; approve.addEventListener("click", () => persist(true));
  bar.append(save, approve);
  root.appendChild(bar);
}

function card(q, i) {
  const probs = problems(q);
  const c = el("div", "card rq" + (probs.length ? " invalid" : (q.needs_review ? " needs" : "")));
  const top = el("div", "row between");
  const left = el("div", "row");
  left.append(el("strong", "", `#${i + 1}`));
  left.append(el("span", "badge " + (q.status === "approved" ? "success" : "warning"), q.status));
  if (q.confidence < 1) left.append(el("span", "badge " + (q.confidence < 0.6 ? "danger" : "info"), t("confidence {n}%", { n: Math.round(q.confidence * 100) })));
  const acts = el("div", "actions");
  acts.append(
    iconBtn("", t("Preview"), ICON.eye, () => preview(q)),
    iconBtn("", t("Move up"), ICON.up, () => move(i, -1)),
    iconBtn("", t("Move down"), ICON.down, () => move(i, 1)),
    iconBtn("delete", t("Delete question"), ICON.trash, async () => {
      if (await confirmDialog({ title: t("Delete question?"), message: t("This question will be removed from the test."), confirmText: t("Delete"), danger: true })) {
        questions.splice(i, 1); dirty = true; render();
      }
    }));
  top.append(left, acts);
  c.appendChild(top);
  (q.warnings || []).forEach((w) => c.appendChild(el("div", "notice warning small", "\u26A0 " + w)));

  const ta = el("textarea"); ta.value = q.text; ta.setAttribute("aria-label", t("Question text"));
  ta.addEventListener("input", () => { q.text = ta.value; dirty = true; });
  const f1 = el("div", "field"); f1.append(el("label", "", t("Question")), ta); c.appendChild(f1);

  const opts = el("div", "field"); opts.appendChild(el("label", "", t("Answer options (select the correct one)")));
  q.options.forEach((o, oi) => {
    const row = el("div", "opt-row");
    const r = el("input"); r.type = "radio"; r.name = "correct-" + i; r.checked = o.is_correct; r.setAttribute("aria-label", t("Mark option {n} correct", { n: oi + 1 }));
    r.addEventListener("change", () => { q.options.forEach((x, k) => { x.is_correct = k === oi; }); dirty = true; render_keep(); });
    const inp = el("input"); inp.type = "text"; inp.value = o.text; inp.maxLength = 500; inp.setAttribute("aria-label", t("Option {n}", { n: oi + 1 }));
    inp.addEventListener("input", () => { o.text = inp.value; dirty = true; });
    row.append(r, inp, iconBtn("delete", t("Remove option"), ICON.x, () => { q.options.splice(oi, 1); dirty = true; render_keep(); }));
    opts.appendChild(row);
  });
  if (q.options.length < 8) {
    const a = el("button", "btn", t("+ Add option")); a.type = "button";
    a.addEventListener("click", () => { q.options.push({ id: null, text: "", is_correct: false }); dirty = true; render_keep(); });
    opts.appendChild(a);
  }
  c.appendChild(opts);

  const ex = el("textarea"); ex.value = q.explanation || ""; ex.setAttribute("aria-label", t("Explanation")); ex.rows = 2;
  ex.addEventListener("input", () => { q.explanation = ex.value; dirty = true; });
  const f2 = el("div", "field"); f2.append(el("label", "", t("Explanation (optional)")), ex); c.appendChild(f2);
  return c;
}

function render_keep() { const y = window.scrollY; render(); window.scrollTo(0, y); }
function move(i, d) { const j = i + d; if (j < 0 || j >= questions.length) return; [questions[i], questions[j]] = [questions[j], questions[i]]; dirty = true; render_keep(); }

function preview(q) {
  const box = el("div");
  box.appendChild(el("div", "q-text", q.text || t("(empty question)")));
  const o = el("div", "options");
  q.options.forEach((x, i) => {
    const b = el("div", "option" + (x.is_correct ? " correct" : ""));
    b.append(el("span", "key", String.fromCharCode(65 + i)), el("span", "", x.text || t("(empty)")));
    o.appendChild(b);
  });
  box.appendChild(o);
  if (q.explanation) box.appendChild(el("div", "explain", q.explanation));
  openModal(box, { title: t("Student preview") });
}

async function persist(approve) {
  const r = await api(`/admin/api/tests/${tid}/questions`, { method: "POST", body: { questions, approve } });
  if (r.ok) {
    questions = r.data.questions; dirty = false; render();
    toast(approve ? t("All questions approved.") : t("Draft saved."), "success");
    if (approve) {
      const pb = document.getElementById("publish-btn");
      if (pb) pb.disabled = false;
    }
  } else {
    toast(r.data.error || t("Save failed."), "error");
    if (r.data.problems) {
      document.querySelectorAll(".rq").forEach((c, i) => { if (r.data.problems.some((p) => p.index === i)) c.classList.add("invalid"); });
      const first = r.data.problems[0];
      toast(t("Question #{n}: {e}", { n: first.index + 1, e: first.errors.map((x) => t(x.charAt(0).toUpperCase() + x.slice(1))).join(", ") }), "warning", 8000);
    }
  }
}

window.addEventListener("beforeunload", (e) => { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
load();
