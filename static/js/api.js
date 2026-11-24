import { t } from "./i18n.js";
export function csrfToken() {
  const m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.content : "";
}

export async function api(url, { method = "GET", body } = {}) {
  const opts = { method, credentials: "same-origin", headers: { "X-CSRF-Token": csrfToken(), Accept: "application/json" } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    return { ok: false, status: 0, data: { error: t("Network error. Check your connection and try again.") } };
  }
  let data = {};
  try { data = await res.json(); } catch (e) { /* non-JSON */ }
  if (res.status === 401) { window.location.href = "/login"; }
  return { ok: res.ok, status: res.status, data };
}
