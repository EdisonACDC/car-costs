/* Car Costs web app: logs in to Home Assistant and shows the Car Costs card. */

const ICONS = {
  "mdi:car-electric": "🚙", "mdi:gas-station": "⛽", "mdi:ev-station": "🔌", "mdi:camera": "📷",
  "mdi:cash": "💶", "mdi:car-side": "🚗", "mdi:piggy-bank-outline": "🐷", "mdi:file-document-outline": "📄",
  "mdi:speedometer": "⏱️", "mdi:counter": "🛣️", "mdi:flag-checkered": "🏁", "mdi:home-lightning-bolt": "🏠",
  "mdi:delete-outline": "🗑️", "mdi:receipt-text-check": "🧾",
};
if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
if (!customElements.get("ha-icon")) {
  customElements.define("ha-icon", class extends HTMLElement {
    static get observedAttributes() { return ["icon"]; }
    attributeChangedCallback() { this.textContent = ICONS[this.getAttribute("icon")] || "•"; }
    connectedCallback() { this.attributeChangedCallback(); }
  });
}

const BASE = location.origin;
const CLIENT_ID = `${BASE}/`;
const REDIRECT = `${BASE}${location.pathname}`;
const KEY = "car_costs_tokens";
const params = new URLSearchParams(location.search);
const ENTRY = params.get("entry") || localStorage.getItem("car_costs_entry") || "";
if (params.get("entry")) localStorage.setItem("car_costs_entry", params.get("entry"));

const main = document.getElementById("main");
const lang = (navigator.language || "it").slice(0, 2);
const T = {
  it: { login: "Accedi a Home Assistant", offline: "Home Assistant non raggiungibile", retry: "Riprova", logout: "Esci", noint: "Car Costs non è configurato in Home Assistant" },
  de: { login: "Bei Home Assistant anmelden", offline: "Home Assistant nicht erreichbar", retry: "Erneut versuchen", logout: "Abmelden", noint: "Car Costs ist in Home Assistant nicht eingerichtet" },
  en: { login: "Log in to Home Assistant", offline: "Home Assistant not reachable", retry: "Retry", logout: "Log out", noint: "Car Costs is not set up in Home Assistant" },
}[lang] || null;
const t = T || { login: "Log in", offline: "Not reachable", retry: "Retry", logout: "Log out", noint: "Car Costs not set up" };

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg; el.style.display = "block";
  clearTimeout(toast._t); toast._t = setTimeout(() => (el.style.display = "none"), 4000);
}

function status(text, button, action) {
  main.innerHTML = `<div class="status"><div>${text}</div>${button ? `<button>${button}</button>` : ""}</div>`;
  if (button) main.querySelector("button").onclick = action;
}

// ---------------------------------------------------------------- auth
function login() {
  const state = Math.random().toString(36).slice(2);
  sessionStorage.setItem("car_costs_state", state);
  location.href = `${BASE}/auth/authorize?response_type=code&client_id=${encodeURIComponent(CLIENT_ID)}` +
    `&redirect_uri=${encodeURIComponent(REDIRECT)}&state=${state}`;
}

function saveTokens(json) {
  const tokens = { access: json.access_token, refresh: json.refresh_token, expires: Date.now() + json.expires_in * 1000 };
  localStorage.setItem(KEY, JSON.stringify(tokens));
  return tokens;
}

async function tokenRequest(body) {
  const res = await fetch(`${BASE}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: CLIENT_ID, ...body }),
  });
  if (!res.ok) { const e = new Error(`auth ${res.status}`); e.status = res.status; throw e; }
  return res.json();
}

let tokens = JSON.parse(localStorage.getItem(KEY) || "null");

async function accessToken() {
  if (!tokens) throw Object.assign(new Error("login"), { login: true });
  if (Date.now() > tokens.expires - 60000) {
    try {
      const json = await tokenRequest({ grant_type: "refresh_token", refresh_token: tokens.refresh });
      tokens = saveTokens({ ...json, refresh_token: tokens.refresh });
    } catch (e) {
      if (e.status === 400 || e.status === 403) { localStorage.removeItem(KEY); tokens = null; throw Object.assign(e, { login: true }); }
      throw e;
    }
  }
  return tokens.access;
}

async function api(path, options = {}) {
  const token = await accessToken();
  const res = await fetch(`${BASE}${path}`, { ...options, headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` } });
  if (res.status === 401) { localStorage.removeItem(KEY); tokens = null; throw Object.assign(new Error("login"), { login: true }); }
  return res;
}

async function json(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.message || body.error || `HTTP ${res.status}`);
  return body;
}

// ----------------------------------------------------------- hass shim
const listeners = new Set();
const fire = () => listeners.forEach((cb) => cb({ data: {} }));

const hass = {
  language: lang, locale: { language: navigator.language || "it" },
  async callWS(msg) {
    const q = new URLSearchParams({ limit: msg.limit || 15 });
    if (msg.config_entry_id || ENTRY) q.set("config_entry_id", msg.config_entry_id || ENTRY);
    return json(await api(`/api/car_costs/overview?${q}`));
  },
  async callService(domain, service, data) {
    const r = await json(await api(`/api/services/${domain}/${service}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    }));
    fire();
    return r;
  },
  fetchWithAuth: (path, options) => api(path, options),
  connection: {
    async subscribeEvents(cb) { listeners.add(cb); return () => listeners.delete(cb); },
  },
};

// Refresh when the app comes back to the foreground and every minute while open.
document.addEventListener("visibilitychange", () => { if (!document.hidden) fire(); });
setInterval(() => { if (!document.hidden) fire(); }, 60000);
window.addEventListener("hass-notification", (e) => toast(e.detail.message));

// ---------------------------------------------------------------- start
async function start() {
  const code = params.get("code");
  if (code) {
    const expected = sessionStorage.getItem("car_costs_state");
    history.replaceState(null, "", location.pathname);
    if (!expected || expected === params.get("state")) {
      try { tokens = saveTokens(await tokenRequest({ grant_type: "authorization_code", code })); }
      catch (e) { tokens = null; }
    }
  }
  if (!tokens) { status("🚙", t.login, login); return; }

  try {
    await hass.callWS({ limit: 1 });
  } catch (e) {
    if (e.login) { status("🚙", t.login, login); return; }
    if (/not found/i.test(e.message)) { status(t.noint); return; }
    status(`${t.offline}<br><small>${e.message}</small>`, t.retry, start);
    return;
  }

  await import("../car-costs-card.js?v=0.2.0");
  main.innerHTML = "";
  const card = document.createElement("car-costs-card");
  card.setConfig({ config_entry_id: ENTRY || undefined, limit: 30 });
  card.hass = hass;
  card.addEventListener("hass-notification", (e) => toast(e.detail.message));
  main.appendChild(card);
  const foot = document.createElement("div");
  foot.className = "foot";
  foot.innerHTML = `<a href="#" id="logout">${t.logout}</a>`;
  main.appendChild(foot);
  foot.querySelector("#logout").onclick = async (ev) => {
    ev.preventDefault();
    try { await fetch(`${BASE}/auth/token`, { method: "POST", body: new URLSearchParams({ action: "revoke", token: tokens.refresh }) }); } catch (e) {}
    localStorage.removeItem(KEY); tokens = null; status("🚙", t.login, login);
  };
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
start();
