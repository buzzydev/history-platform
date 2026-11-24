import { t } from "./i18n.js";
let active = null;

export function confirmDialog({ title = t("Are you sure?"), message = "", confirmText = t("Confirm"), cancelText = t("Cancel"), danger = false } = {}) {
  return new Promise((resolve) => {
    const bg = document.createElement("div");
    bg.className = "modal-bg open";
    const box = document.createElement("div");
    box.className = "modal";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    const h = document.createElement("h3");
    h.textContent = title;
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = message;
    const row = document.createElement("div");
    row.className = "row";
    const no = document.createElement("button");
    no.type = "button"; no.className = "btn"; no.textContent = cancelText;
    const yes = document.createElement("button");
    yes.type = "button"; yes.className = "btn " + (danger ? "danger" : "primary"); yes.textContent = confirmText;
    row.append(no, yes);
    box.append(h, p, row);
    bg.appendChild(box);
    document.body.appendChild(bg);
    const prev = document.activeElement;
    const done = (v) => {
      document.removeEventListener("keydown", onKey);
      bg.remove();
      active = null;
      if (prev && prev.focus) prev.focus();
      resolve(v);
    };
    const onKey = (e) => {
      if (e.key === "Escape") done(false);
      if (e.key === "Tab") {
        const f = [no, yes];
        const i = f.indexOf(document.activeElement);
        e.preventDefault();
        f[(i + (e.shiftKey ? -1 : 1) + 2) % 2].focus();
      }
    };
    document.addEventListener("keydown", onKey);
    bg.addEventListener("click", (e) => { if (e.target === bg) done(false); });
    no.addEventListener("click", () => done(false));
    yes.addEventListener("click", () => done(true));
    active = bg;
    (danger ? no : yes).focus();
  });
}

export function openModal(contentNode, { title = "" } = {}) {
  const bg = document.createElement("div");
  bg.className = "modal-bg open";
  const box = document.createElement("div");
  box.className = "modal";
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");
  if (title) { const h = document.createElement("h3"); h.textContent = title; box.appendChild(h); }
  box.appendChild(contentNode);
  const row = document.createElement("div");
  row.className = "row";
  const close = document.createElement("button");
  close.type = "button"; close.className = "btn"; close.textContent = t("Close");
  row.appendChild(close);
  box.appendChild(row);
  bg.appendChild(box);
  document.body.appendChild(bg);
  const done = () => { document.removeEventListener("keydown", onKey); bg.remove(); };
  const onKey = (e) => { if (e.key === "Escape") done(); };
  document.addEventListener("keydown", onKey);
  bg.addEventListener("click", (e) => { if (e.target === bg) done(); });
  close.addEventListener("click", done);
  close.focus();
}

/* Destructive actions: any <form data-confirm="..."> or submit button with data-confirm shows a custom dialog. */
export function initConfirmForms() {
  document.addEventListener("submit", async (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.confirmed === "1") return;
    const src = (e.submitter && e.submitter.dataset.confirm) ? e.submitter : form;
    const msg = src.dataset.confirm;
    if (!msg) return;
    e.preventDefault();
    const ok = await confirmDialog({
      title: src.dataset.confirmTitle || t("Please confirm"), message: msg,
      confirmText: src.dataset.confirmButton || t("Yes, continue"), danger: src.dataset.danger !== "0",
    });
    if (ok) {
      form.dataset.confirmed = "1";
      if (e.submitter && e.submitter.name) {
        const h = document.createElement("input");
        h.type = "hidden"; h.name = e.submitter.name; h.value = e.submitter.value;
        form.appendChild(h);
      }
      form.submit();
    }
  });
}
