// OPLedger frontend entry point.
//
// Talks to the backend exclusively through the REST API under /api — the same
// surface a hosted deployment exposes. No localhost assumptions baked in here.
import { initI18n } from "./i18n.js";

const API = "/api";

async function getJSON(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function main() {
  const dict = await initI18n();

  // Route between first-run setup and the app shell based on backend state.
  const { initialized } = await getJSON("/setup/status").catch(() => ({ initialized: false }));

  const app = document.getElementById("app");
  const key = initialized ? "app.ready" : "app.setupNeeded";
  app.innerHTML = `<p data-i18n="${key}">${initialized ? "Ready." : "Setup required."}</p>`;
  // Re-translate the freshly injected node.
  const { applyTranslations } = await import("./i18n.js");
  applyTranslations(dict, app);
}

main();
