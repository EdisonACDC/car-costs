/* How the app proves who it is.
 *
 * - Inside Home Assistant's panel (embed=1) it uses the panel's own session: `hass.fetchWithAuth`.
 * - On a phone it uses a device token, got by trading the one-time link made in the panel. There
 *   is no Home Assistant login on the phone, ever. The token only works for the cars and the
 *   actions the phone was given (/api/car_costs/app/...). */

export const BASE = location.origin;
const KEY = "car_costs_device";
const APP = "/api/car_costs/app";

/** Inside Home Assistant's panel the page is an iframe of the panel's window: no own login. */
export const EMBEDDED = new URLSearchParams(location.search).get("embed") === "1";
const hassOf = () => { try { return window.parent.__carCostsHass || null; } catch { return null; } };

export class LoginRequired extends Error {}   // not linked, or the phone was unlinked
export class Unreachable extends Error {}
export class ApiError extends Error {
  constructor(message, status, body) { super(message); this.status = status; this.body = body; }
}

let token = null;
try { token = localStorage.getItem(KEY) || null; } catch { /* storage blocked */ }

export const hasTokens = () => (EMBEDDED ? !!hassOf() : !!token);
export function forget() {
  token = null;
  try { localStorage.removeItem(KEY); } catch { /* nothing to remove */ }
}
function keep(value) {
  token = value;
  try { localStorage.setItem(KEY, value); } catch { /* storage blocked */ }
}

// ---------------------------------------------------------------- the link
const LINK = /[#?&]c=([A-Za-z0-9_-]{20,128})(?![A-Za-z0-9_-])/;

/** The one-time code in the address: #c=... (any browser) or ?c=... (the iPhone's Home Screen icon). */
export function readLink() {
  const m = LINK.exec(location.hash || "") || LINK.exec(location.search || "");
  return m ? m[1] : null;
}
/** The code from a pasted link (or the bare code). */
export function linkFrom(text) {
  const s = String(text || "").trim();
  const m = LINK.exec(s);
  if (m) return m[1];
  return /^[A-Za-z0-9_-]{20,128}$/.test(s) ? s : null;
}
/** Take the code out of the address bar. */
export function forgetLinkInUrl() {
  try { history.replaceState(null, "", location.pathname); } catch { /* not allowed */ }
}
/** iPhone, in the browser: the code moves to ?c= so the Home Screen icon opens the app with it. */
export function keepLinkForHomeScreen(code) {
  try { history.replaceState(null, "", `${location.pathname}?c=${encodeURIComponent(code)}`); } catch { /* not allowed */ }
}

/** Trade the link's code for this phone's own token. */
export async function activate(code) {
  let res;
  try {
    res = await fetch(`${BASE}${APP}/activate`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: code }),
    });
  } catch { throw new Unreachable(); }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(body.error || `HTTP ${res.status}`, res.status, body);
  keep(body.token);
}

// ------------------------------------------------------------------- calls
/** The app talks to /api/car_costs/... and /api/services/car_costs/...; the phone's versions are
 *  the same under /api/car_costs/app/. */
function phonePath(path) {
  if (path.startsWith("/api/services/car_costs/")) return `${APP}/service/${path.slice("/api/services/car_costs/".length)}`;
  if (path.startsWith("/api/car_costs/")) return `${APP}/${path.slice("/api/car_costs/".length)}`;
  return path;
}

export async function api(path, options = {}) {
  if (EMBEDDED) {
    const hass = hassOf();
    if (!hass) throw new LoginRequired();
    let res;
    try { res = await hass.fetchWithAuth(path, options); } catch { throw new Unreachable(); }
    if (res.status === 401) throw new LoginRequired();
    return res;
  }
  if (!token) throw new LoginRequired();
  let res;
  try {
    res = await fetch(`${BASE}${phonePath(path)}`, { ...options, headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` } });
  } catch { throw new Unreachable(); }
  if (res.status === 401) { forget(); throw new LoginRequired(); }
  return res;
}

export async function apiJson(path, options = {}) {
  const res = await api(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(body.message || body.error || `HTTP ${res.status}`, res.status, body);
  return body;
}

/** Who this phone is and what it may do; also brings the renewed token when it is time. */
export async function me() {
  if (EMBEDDED) return { permission: "edit" };
  const body = await apiJson("/api/car_costs/me");
  if (body.token) { keep(body.token); delete body.token; }
  return body;
}

/** Home Assistant's websocket, for the panel's admin screens (only inside the panel). */
export function callWS(message) {
  const hass = hassOf();
  if (!EMBEDDED || !hass) return Promise.reject(new LoginRequired());
  return hass.callWS(message);
}
export const isAdmin = () => !!hassOf()?.user?.is_admin;
