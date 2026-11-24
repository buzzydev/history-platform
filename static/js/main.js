import { t as tr0 } from "./i18n.js";
import { api } from "./api.js";
import { toast } from "./toast.js";
import { initConfirmForms } from "./modal.js";

/* ---- theme switch ---- */
function applyTheme(t) {
  const tr = tr0;
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem("theme", t); } catch (e) {}
  document.querySelectorAll("[data-theme-toggle]").forEach((b) => {
    b.setAttribute("aria-pressed", String(t === "dark"));
    b.setAttribute("aria-label", t === "dark" ? tr("Switch to light mode") : tr("Switch to dark mode"));
  });
}
document.querySelectorAll("[data-theme-toggle]").forEach((b) => {
  b.addEventListener("click", () => applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"));
});
applyTheme(document.documentElement.getAttribute("data-theme") || "light");
if (window.matchMedia) {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
    let stored = null;
    try { stored = localStorage.getItem("theme"); } catch (err) {}
    if (!stored) applyTheme(e.matches ? "dark" : "light");
  });
}

/* ---- dropdowns: click toggles, outside click / Esc closes ---- */
function closeAll(except) {
  document.querySelectorAll(".dropdown.open").forEach((d) => {
    if (d !== except) { d.classList.remove("open"); const t = d.querySelector("[data-dropdown-toggle]"); if (t) t.setAttribute("aria-expanded", "false"); }
  });
}
document.addEventListener("click", (e) => {
  const toggle = e.target.closest("[data-dropdown-toggle]");
  if (toggle) {
    const dd = toggle.closest(".dropdown");
    const open = !dd.classList.contains("open");
    closeAll(dd);
    dd.classList.toggle("open", open);
    toggle.setAttribute("aria-expanded", String(open));
    if (open && dd.dataset.onOpen === "notifications") markNotificationsRead(dd);
    return;
  }
  if (!e.target.closest(".dropdown-menu")) closeAll();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeAll(); });

async function markNotificationsRead(dd) {
  const badge = dd.querySelector(".badge-dot");
  if (!badge) return;
  const r = await api("/api/notifications/read", { method: "POST", body: {} });
  if (r.ok) { badge.remove(); dd.querySelectorAll(".unread").forEach((n) => n.classList.remove("unread")); }
}

/* ---- mobile menu ---- */
const mt = document.querySelector("[data-menu-toggle]");
const mm = document.getElementById("mobile-menu");
if (mt && mm) {
  mt.addEventListener("click", () => {
    const open = mm.classList.toggle("open");
    mt.setAttribute("aria-expanded", String(open));
  });
}

/* ---- password visibility ---- */
document.querySelectorAll("[data-pw-toggle]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const input = btn.parentElement.querySelector("input");
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.setAttribute("aria-label", show ? tr0("Hide password") : tr0("Show password"));
    btn.setAttribute("aria-pressed", String(show));
  });
});

/* ---- progress bars (no inline styles: CSP) ---- */
document.querySelectorAll("[data-width]").forEach((el) => { el.style.width = Math.max(0, Math.min(100, Number(el.dataset.width) || 0)) + "%"; });

/* ---- flash messages -> toasts ---- */
const fd = document.getElementById("flash-data");
if (fd) {
  try { JSON.parse(fd.dataset.messages || "[]").forEach(([lvl, msg]) => toast(msg, lvl === "message" ? "info" : lvl)); } catch (e) {}
}

/* ---- disable double submit ---- */
document.addEventListener("submit", (e) => {
  const f = e.target;
  if (e.defaultPrevented || !(f instanceof HTMLFormElement)) return;
  f.querySelectorAll('button[type="submit"]:not([data-keep])').forEach((b) => { setTimeout(() => { b.disabled = true; }, 0); });
});
window.addEventListener("pageshow", (e) => {
  if (e.persisted) document.querySelectorAll('button[type="submit"]').forEach((b) => { b.disabled = false; });
});

initConfirmForms();
