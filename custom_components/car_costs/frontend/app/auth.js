/* Home Assistant login (OAuth) and authenticated requests. Works on http://IP:8123 and Nabu Casa. */

export const BASE = location.origin;
const CLIENT_ID = `${BASE}/`;
const REDIRECT = `${BASE}${location.pathname}`;
const KEY = "car_costs_tokens";

let tokens = JSON.parse(localStorage.getItem(KEY) || "null");

export class LoginRequired extends Error {}
export class Unreachable extends Error {}
export class ApiError extends Error {
  constructor(message, status, body) { super(message); this.status = status; this.body = body; }
}

export const hasTokens = () => !!tokens;

export function login() {
  const state = Math.random().toString(36).slice(2);
  sessionStorage.setItem("car_costs_state", state);
  location.href = `${BASE}/auth/authorize?response_type=code&client_id=${encodeURIComponent(CLIENT_ID)}` +
    `&redirect_uri=${encodeURIComponent(REDIRECT)}&state=${state}`;
}

function saveTokens(json) {
  tokens = { access: json.access_token, refresh: json.refresh_token, expires: Date.now() + json.expires_in * 1000 };
  localStorage.setItem(KEY, JSON.stringify(tokens));
}

async function tokenRequest(body) {
  let res;
  try {
    res = await fetch(`${BASE}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_id: CLIENT_ID, ...body }),
    });
  } catch { throw new Unreachable(); }
  if (!res.ok) throw Object.assign(new Error(`auth ${res.status}`), { status: res.status });
  return res.json();
}

/** Call once at start: finishes the login when HA redirected back with ?code=. */
export async function finishLogin() {
  const params = new URLSearchParams(location.search);
  const code = params.get("code");
  if (!code) return;
  const expected = sessionStorage.getItem("car_costs_state");
  const state = params.get("state");
  params.delete("code"); params.delete("state");
  const rest = params.toString();
  history.replaceState(null, "", location.pathname + (rest ? `?${rest}` : ""));
  if (expected && expected !== state) return;
  try { saveTokens(await tokenRequest({ grant_type: "authorization_code", code })); }
  catch (e) { if (e instanceof Unreachable) throw e; tokens = null; }
}

async function accessToken() {
  if (!tokens) throw new LoginRequired();
  if (Date.now() > tokens.expires - 60000) {
    try {
      const json = await tokenRequest({ grant_type: "refresh_token", refresh_token: tokens.refresh });
      saveTokens({ ...json, refresh_token: tokens.refresh });
    } catch (e) {
      if (e.status === 400 || e.status === 403) { forget(); throw new LoginRequired(); }
      throw e instanceof Unreachable ? e : new Unreachable();
    }
  }
  return tokens.access;
}

function forget() { localStorage.removeItem(KEY); tokens = null; }

export async function api(path, options = {}) {
  const token = await accessToken();
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { ...options, headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` } });
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

export async function logout() {
  if (tokens) {
    try { await fetch(`${BASE}/auth/token`, { method: "POST", body: new URLSearchParams({ action: "revoke", token: tokens.refresh }) }); }
    catch { /* offline: the token is forgotten locally anyway */ }
  }
  forget();
}
