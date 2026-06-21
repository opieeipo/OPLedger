// Minimal, dependency-free i18n for OPLedger.
//
// Loads /locales/<lang>.json and exposes:
//   - applyTranslations(): replaces text of [data-i18n] elements (static HTML)
//   - t(key): resolves a dotted key for dynamically rendered strings
// English is the source locale; add more locale files alongside en.json and
// they resolve automatically based on the browser language.

const DEFAULT_LANG = "en";
let dict = {};

function resolve(d, dottedKey) {
  return dottedKey.split(".").reduce((node, part) => (node ? node[part] : undefined), d);
}

export function t(key, fallback = "") {
  const value = resolve(dict, key);
  return typeof value === "string" ? value : fallback || key;
}

async function loadLocale(lang) {
  try {
    const res = await fetch(`/locales/${lang}.json`);
    return res.ok ? await res.json() : {};
  } catch {
    return {};
  }
}

export function applyTranslations(root = document) {
  for (const el of root.querySelectorAll("[data-i18n]")) {
    const value = resolve(dict, el.getAttribute("data-i18n"));
    if (typeof value === "string") el.textContent = value;
  }
}

export async function initI18n() {
  const lang = (navigator.language || DEFAULT_LANG).split("-")[0];
  dict = await loadLocale(lang);
  if (!Object.keys(dict).length) dict = await loadLocale(DEFAULT_LANG);
  document.documentElement.lang = lang;
  applyTranslations();
  return dict;
}
