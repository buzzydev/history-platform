import { t } from "./i18n.js";
const ICON = { success: "\u2713", error: "!", warning: "!", info: "i" };

export function toast(message, level = "info", ms = 5200) {
  const box = document.getElementById("toasts");
  if (!box) return;
  const el = document.createElement("div");
  el.className = "toast " + level;
  el.setAttribute("role", level === "error" ? "alert" : "status");
  const msg = document.createElement("div");
  msg.className = "t-msg";
  msg.textContent = message;
  const close = document.createElement("button");
  close.className = "t-close";
  close.type = "button";
  close.setAttribute("aria-label", t("Dismiss"));
  close.textContent = "\u00d7";
  el.append(msg, close);
  const remove = () => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 260);
  };
  close.addEventListener("click", remove);
  box.appendChild(el);
  if (ms > 0) setTimeout(remove, ms);
  return el;
}
