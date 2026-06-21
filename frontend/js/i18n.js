// Minimal, dependency-free i18n for OPLedger.
//
// Loads /locales/<lang>.json and replaces the text of any element carrying a
// data-i18n="<dotted.key>" attribute. English is the source locale; add more
// locale files alongside en.json and they resolve automatically.

const DEFAULT_LANG = "en";

function resolve(dict, dottedKey) {
  return dottedKey.split(".").reduce((node, part) => (node ? node[part] : undefined), dict);
}

export async function loadLocale(lang = DEFAULT_LANG) {
  let dict;
  try {
    const res = await fetch(`/locales/${lang}.json`);
    dict = res.ok ? await res.json() : {};
  } catch {
    dict = {};
  }
  return dict;
}

export function applyTranslations(dict, root = document) {
  for (const el of root.querySelectorAll("[data-i18n]")) {
    const value = resolve(dict, el.getAttribute("data-i18n"));
    if (typeof value === "string") el.textContent = value;
  }
}

export async function initI18n() {
  const lang = (navigator.language || DEFAULT_LANG).split("-")[0];
  const dict = await loadLocale(lang).then((d) =>
    Object.keys(d).length ? d : loadLocale(DEFAULT_LANG)
  );
  applyTranslations(dict);
  return dict;
}
