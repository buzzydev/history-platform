let dict = {};
try {
  const el = document.getElementById("i18n-data");
  dict = JSON.parse((el && el.dataset.dict) || "{}");
} catch (e) { dict = {}; }

export function t(key, vars) {
  let s = Object.prototype.hasOwnProperty.call(dict, key) ? dict[key] : key;
  if (vars) for (const k of Object.keys(vars)) s = s.split("{" + k + "}").join(String(vars[k]));
  return s;
}
