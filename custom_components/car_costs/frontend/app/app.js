/* Car Costs web app: Overview, Log, Charts, Settings (+ the "＋" sheet in forms.js). */

import * as auth from "./auth.js";
import { LoginRequired, Unreachable, ApiError } from "./auth.js";
import {
  t, days, num, eur, signedEur, pct, dateLabel, relativeDay, monthLabel, parseDay,
  lang, LANGS, setLanguage, languagePreference,
} from "./i18n.js";
import { barsChart, lineChart, donut } from "./charts.js";
import { $, $$, esc, buzz, toast, loadThumbs } from "./ui.js";
import { initForms, openAdd, openDetail } from "./forms.js";

{ const th = new URLSearchParams(location.search).get("theme"); if (th) document.documentElement.dataset.theme = th; }
const CACHE_KEY = "car_costs_cache";
const ENTRY_KEY = "car_costs_entry";
const RING = 2 * Math.PI * 56;

const state = {
  entry: new URLSearchParams(location.search).get("entry") || localStorage.getItem(ENTRY_KEY) || "",
  cars: [], ov: null, hist: null,
  tab: "overview", filter: "all", q: "", range: 12,
  offline: false,
};
const root = $("#app");
let loading = false;

// ---------------------------------------------------------------- screens
function setScreen(html) { root.innerHTML = html; $("#tabs").hidden = true; }

function showLogin() {
  setScreen(`<div class="center"><div class="logo">🚙</div><h1>${esc(t("login_title"))}</h1><p>${esc(t("login_text"))}</p>
    <button class="btn" id="go">${esc(t("login_btn"))}</button></div>`);
  $("#go").onclick = auth.login;
  hideSplash();
}
function showWelcome() {
  setScreen(`<div class="center"><div class="logo">🚙</div><h1>${esc(t("welcome_title"))}</h1><p>${esc(t("welcome_text"))}</p>
    <a class="btn" href="${auth.BASE}/config/integrations/dashboard/add?domain=car_costs" target="_top">${esc(t("welcome_btn"))}</a></div>`);
  hideSplash();
}
function showMessage(text, retry) {
  setScreen(`<div class="center"><div class="logo">🚙</div><p>${text}</p>${retry ? `<button class="btn" id="retry">${esc(t("retry"))}</button>` : ""}</div>`);
  if (retry) $("#retry").onclick = start;
  hideSplash();
}
function skeleton() {
  root.innerHTML = `<div class="skeleton"><div class="sk" style="height:44px;width:60%;margin:8px 4px 18px"></div>
    <div class="sk" style="height:172px"></div><div class="sk" style="height:140px;margin-top:14px"></div>
    <div class="grid"><div class="sk" style="height:92px"></div><div class="sk" style="height:92px"></div><div class="sk" style="height:92px"></div><div class="sk" style="height:92px"></div></div></div>`;
}
function hideSplash() {
  const s = $("#splash");
  if (!s) return;
  s.classList.add("out");
  setTimeout(() => s.remove(), 500);
}

// ------------------------------------------------------------------- data
const q = () => new URLSearchParams({ config_entry_id: state.entry });

async function fetchAll() {
  if (!state.cars.length) state.cars = await auth.apiJson("/api/car_costs/cars");
  if (!state.cars.length) throw new ApiError("none", 404, {});
  if (!state.cars.some((c) => c.config_entry_id === state.entry)) state.entry = state.cars[0].config_entry_id;
  const [ov, hist] = await Promise.all([
    auth.apiJson(`/api/car_costs/overview?${q()}&limit=200`),
    auth.apiJson(`/api/car_costs/history?${q()}&months=0`),
  ]);
  state.ov = ov; state.hist = hist; state.offline = false;
  localStorage.setItem(ENTRY_KEY, state.entry);
  try { localStorage.setItem(CACHE_KEY, JSON.stringify({ cars: state.cars, entry: state.entry, ov, hist, at: Date.now() })); } catch { /* quota */ }
}

function loadCache() {
  try {
    const c = JSON.parse(localStorage.getItem(CACHE_KEY) || "null");
    if (!c || (state.entry && c.entry !== state.entry && state.cars.length)) return false;
    Object.assign(state, { cars: c.cars, entry: c.entry, ov: c.ov, hist: c.hist, offline: true });
    return true;
  } catch { return false; }
}

/** Reload data and redraw. Returns true when fresh data arrived. */
async function refresh({ quiet = false } = {}) {
  if (loading) return false;
  loading = true;
  try {
    await fetchAll();
    render();
    return true;
  } catch (e) {
    if (e instanceof LoginRequired) { showLogin(); return false; }
    if (e instanceof ApiError && e.status === 404) { showWelcome(); return false; }
    if (e instanceof Unreachable || e instanceof TypeError) {
      if (state.ov || loadCache()) { state.offline = true; render(); }
      else showMessage(esc(t("unreachable")), true);
      return false;
    }
    if (!quiet) toast(e.message);
    return false;
  } finally { loading = false; }
}
const relogin = () => { showLogin(); };
initForms({ state, refresh, relogin });

// ------------------------------------------------------------------ model
function movements() {
  const items = state.ov.entries.map((e) => ({
    id: e.id, kind: e.kind, home: e.location === "home", date: e.date, created: e.created || "", cost: e.total_cost,
    station: e.station, liters: e.liters, kwh: e.kwh, hasImage: e.has_image, entry: e,
  }));
  const meter = (state.hist.home_daily || []).map((h) => ({
    id: `meter-${h.date}`, kind: "charge", home: true, meter: true, date: h.date, created: "", cost: h.cost, kwh: h.kwh,
  }));
  return [...items, ...meter].sort((a, b) => b.date.localeCompare(a.date) || b.created.localeCompare(a.created));
}

function rowHtml(m) {
  const refuel = m.kind === "refuel";
  const title = refuel ? m.station || t("refuel") : m.home ? t("charge_home") : m.station || t("charge");
  const qty = refuel ? m.liters : m.kwh;
  const unit = qty ? `${num(qty, 1)} ${refuel ? "L" : "kWh"} · ${eur(m.cost / qty, 3)}/${refuel ? "L" : "kWh"}` : "";
  const sub = [relativeDay(m.date), unit, m.meter ? t("from_meter") : ""].filter(Boolean).join(" · ");
  const icon = refuel ? "⛽" : m.home ? "🏠" : "🔌";
  const lead = m.hasImage ? `<div class="thumb" data-img="${esc(m.id)}">🧾</div>` : `<div class="badge">${icon}</div>`;
  const body = `${lead}<div class="m"><div class="t">${esc(title)}</div><div class="d">${esc(sub)}</div></div><div class="p">${eur(m.cost, 2)}</div>`;
  return m.meter ? `<div class="row">${body}</div>` : `<button class="row" data-open="${esc(m.id)}">${body}</button>`;
}

// ------------------------------------------------------------- overview tab
/** "VW Passat B8" -> "Passat", "Kodiaq iV" -> "Kodiaq" */
function shortName(name) {
  const w = String(name).split(" ");
  if (w.length > 1 && w[0].length <= 3) w.shift();
  return w[0];
}

function breakEvenText(s) {
  if (s.investment > 0 && s.total_savings >= s.investment) return t("breakeven_reached");
  if (!s.break_even_date) return t("breakeven_unknown");
  const d = parseDay(s.break_even_date);
  const far = (d - new Date()) / 86400000 > 365;
  return t("breakeven", { when: far ? d.getFullYear() : dateLabel(s.break_even_date) });
}

function overviewHtml() {
  const { ov, hist } = state, s = ov.summary;
  const ringPct = Math.max(0, Math.min(100, s.amortization ?? 0));
  const max = Math.max(1, s.energy_cost, s.reference_cost);
  const w = (v) => (v <= 0 ? 0 : Math.max(3, (v / max) * 100));
  const ev = s.ev_share_pct != null ? ` · ${t("ev_share", { pct: num(s.ev_share_pct, 0) })}` : "";
  const per100 = s.cost_per_100km != null && s.reference_cost_per_100km != null
    ? t("per100", { a: eur(s.cost_per_100km, 2), b: eur(s.reference_cost_per_100km, 2) }) : "";
  const months = hist.months.slice(-3);
  const moves = movements().slice(0, 3);
  const cls = (n) => (n == null ? "" : n < 0 ? "neg" : "pos");
  return `<header class="top"><div><h1>${esc(ov.title)}${state.offline ? `<span class="offline-badge">${esc(t("offline"))}</span>` : ""}</h1>
      <div class="sub">vs ${esc(ov.ref_name)} · ${esc(t("since", { date: dateLabel(ov.start_date) }))} · ${esc(days(s.days))}</div></div><div class="avatar glass">🚙</div></header>
    <section class="hero glass">
      <div class="ring"><svg width="132" height="132" viewBox="0 0 132 132"><defs><linearGradient id="rg" x1="0" x2="1"><stop offset="0" stop-color="#5ef0a0"/><stop offset="1" stop-color="#7ee8fa"/></linearGradient></defs>
        <circle cx="66" cy="66" r="56" fill="none" class="ring-track" stroke-width="14"/>
        <circle class="fg" cx="66" cy="66" r="56" fill="none" stroke="url(#rg)" stroke-width="14" stroke-linecap="round" stroke-dasharray="${RING.toFixed(1)}" stroke-dashoffset="${RING.toFixed(1)}" data-off="${(RING * (1 - ringPct / 100)).toFixed(1)}"/></svg>
        <div class="c"><b>${s.amortization == null ? "–" : pct(s.amortization)}</b><span>${esc(t("repaid"))}</span></div></div>
      <div><div class="lbl">${esc(t("saved"))}</div><div class="big ${cls(s.total_savings)}">${signedEur(s.total_savings)}</div>
        <div class="muted">${esc(t("on_invested", { amount: eur(s.investment) }))}</div>
        <div class="pill">🏁 ${esc(breakEvenText(s))}</div></div>
    </section>
    <section class="vs glass"><div class="lbl">${esc(t("same_km", { km: num(s.km_driven, 0) }))}</div>
      <div class="vsrow"><div>🚙 ${esc(shortName(ov.title))}</div><div class="bar"><i data-w="${w(s.energy_cost)}" style="background:linear-gradient(90deg,var(--pos),var(--acc))"></i></div><div class="n">${eur(s.energy_cost)}</div></div>
      <div class="vsrow"><div>🚗 ${esc(shortName(ov.ref_name))}</div><div class="bar"><i data-w="${w(s.reference_cost)}" style="background:linear-gradient(90deg,#ffb36b,var(--neg))"></i></div><div class="n">${eur(s.reference_cost)}</div></div>
      <div class="muted">${esc(per100)}${esc(ev)}</div></section>
    <div class="grid">
      <div class="tile glass"><div class="ic">⛽</div><div class="v">${eur(s.fuel_cost)}</div><div class="s">${esc(t("tile_fuel"))} · ${esc(t("tile_fuel_sub", { l: num(s.fuel_liters, 0), c: num(s.avg_fuel_consumption, 1) }))}</div></div>
      <div class="tile glass"><div class="ic">⚡</div><div class="v">${eur(s.electricity_cost)}</div><div class="s">${esc(t("tile_power"))} · ${esc(t("tile_power_sub", { kwh: num(s.electricity_kwh, 0) }))}<br>${esc(t("of_home", { kwh: num(s.home_kwh, 0) }))}</div></div>
      <div class="tile glass"><div class="ic">📄</div><div class="v ${cls(s.fixed_cost_savings)}">${signedEur(s.fixed_cost_savings)}</div><div class="s">${esc(t("tile_fixed"))}</div></div>
      <div class="tile glass"><div class="ic">📈</div><div class="v ${cls(s.savings_per_month)}">${signedEur(s.savings_per_month)}</div><div class="s">${esc(t("tile_month"))}</div></div>
    </div>
    ${months.length ? `<section class="chart glass"><div class="lbl">${esc(t("spend_month"))}</div>
      ${barsChart(months, { height: 100, a: { key: "reference_cost", label: ov.ref_name, fill: "rgba(255,138,128,.55)" }, b: { key: "energy_cost", label: ov.title, fill: "url(#new)" } })}
      <div class="readout" data-readout></div></section>` : ""}
    <div class="sec"><h2>${esc(t("last_moves"))}</h2><button data-goto="log">${esc(t("all"))}</button></div>
    <section class="list glass">${moves.length ? moves.map(rowHtml).join("") : `<div class="empty">${esc(t("no_moves"))}</div>`}</section>`;
}

// ------------------------------------------------------------------ log tab
function logHtml() {
  const f = state.filter, needle = state.q.trim().toLowerCase();
  let items = movements().filter((m) => (f === "fuel" ? m.kind === "refuel" : f === "charges" ? m.kind === "charge" : f === "home" ? m.kind === "charge" && m.home : true));
  if (needle) items = items.filter((m) => (m.station || "").toLowerCase().includes(needle));
  const groups = new Map();
  for (const m of items) { const k = m.date.slice(0, 7); (groups.get(k) || groups.set(k, []).get(k)).push(m); }
  const chip = (id, label) => `<button class="chip ${f === id ? "on" : ""}" data-filter="${id}">${esc(label)}</button>`;
  const body = [...groups].map(([ym, list]) => `<div class="monthhead"><h3>${esc(monthLabel(ym))}</h3><span>${esc(t("month_total"))} ${eur(list.reduce((a, m) => a + m.cost, 0), 2)}</span></div>
      <section class="list glass">${list.map(rowHtml).join("")}</section>`).join("");
  return `<header class="top"><div><h1>${esc(t("nav_log"))}${state.offline ? `<span class="offline-badge">${esc(t("offline"))}</span>` : ""}</h1></div></header>
    <div class="chips">${chip("all", t("f_all"))}${chip("fuel", t("f_fuel"))}${chip("charges", t("f_charges"))}${chip("home", t("f_home"))}</div>
    <input class="search" id="search" type="search" placeholder="${esc(t("search"))}" value="${esc(state.q)}" enterkeyhint="search" autocomplete="off">
    ${body || `<div class="empty">${esc(needle ? t("nothing_found") : t("no_moves"))}</div>`}`;
}

// --------------------------------------------------------------- charts tab
function rangeData() {
  const all = state.hist.months;
  const months = state.range ? all.slice(-state.range) : all;
  const from = months.length ? `${months[0].month}-01` : "0000";
  return { months, daily: state.hist.daily.filter((p) => p.date >= from) };
}

function chartsHtml() {
  const { ov, hist } = state;
  const { months, daily } = rangeData();
  const chip = (n, label) => `<button class="chip ${state.range === n ? "on" : ""}" data-range="${n}">${esc(label)}</button>`;
  const dot = (c) => `<i style="background:${c}"></i>`;
  const pts = (key) => daily.map((p) => ({ t: parseDay(p.date), y: p[key] }));
  const saved = ov.summary.total_savings, inv = hist.investment;
  const bestSaved = Math.max(saved, ...daily.map((p) => p.total_savings));
  // The break-even line only appears once the savings are a visible part of the investment.
  const showGoal = inv > 0 && bestSaved >= inv * 0.25;
  const cum = lineChart([{ points: pts("total_savings"), color: "var(--pos)", area: true }], {
    goal: showGoal ? { y: inv, label: t("ch_goal", { amount: eur(inv) }) } : null,
    yFmt: (v) => (Math.abs(v) >= 1000 ? `${num(v / 1000, 1)}k` : num(v, 0)),
  });
  const per = daily.filter((p) => p.km >= 50);
  const per100 = lineChart([
    { points: per.map((p) => ({ t: parseDay(p.date), y: (p.reference_cost / p.km) * 100 })), color: "var(--neg)", dash: true },
    { points: per.map((p) => ({ t: parseDay(p.date), y: (p.energy_cost / p.km) * 100 })), color: "var(--pos)" },
  ], { yFmt: (v) => num(v, 1) });
  const sum = (k) => months.reduce((a, m) => a + m[k], 0);
  const split = [
    { value: sum("fuel_cost"), color: "#ffb36b", label: t("legend_fuel") },
    { value: sum("public_cost"), color: "#7ee8fa", label: t("legend_public") },
    { value: sum("home_cost"), color: "#5ef0a0", label: t("legend_home") },
  ];
  const total = split.reduce((a, p) => a + p.value, 0);
  const none = `<div class="empty">${esc(t("ch_no_data"))}</div>`;
  const card = (title, inner, extra = "") => `<section class="chart glass"><div class="lbl">${esc(title)}</div>${inner}${extra}<div class="readout" data-readout></div></section>`;
  return `<header class="top"><div><h1>${esc(t("nav_charts"))}${state.offline ? `<span class="offline-badge">${esc(t("offline"))}</span>` : ""}</h1></div></header>
    <div class="chips">${chip(3, t("range_3"))}${chip(12, t("range_12"))}${chip(0, t("range_all"))}</div>
    ${card(t("ch_spend"), months.length ? barsChart(months, { a: { key: "reference_cost", label: ov.ref_name, fill: "rgba(255,138,128,.55)" }, b: { key: "energy_cost", label: ov.title, fill: "url(#new)" } }) : none,
      `<div class="legend"><span>${dot("rgba(255,138,128,.8)")}${esc(ov.ref_name)}</span><span>${dot("var(--pos)")}${esc(ov.title)}</span></div>`)}
    ${card(t("ch_cum"), (inv > 0 ? `<div class="progress-line">${esc(t("ch_progress", { x: eur(saved), y: eur(inv), p: num((saved / inv) * 100, 0) }))}</div>` : "") + (cum || none))}
    ${card(t("ch_per100"), per.length > 1 ? per100 : none,
      `<div class="legend"><span>${dot("var(--neg)")}${esc(ov.ref_name)}</span><span>${dot("var(--pos)")}${esc(ov.title)}</span></div>`)}
    ${card(t("ch_split"), total > 0 ? `<div class="donut-wrap">${donut(split, eur(total), t("total"))}
      <div>${split.map((p) => `<div class="legend" style="margin:6px 0"><span>${dot(p.color)}${esc(p.label)} · <b>${eur(p.value)}</b></span></div>`).join("")}</div></div>` : none)}`;
}

// ------------------------------------------------------------- settings tab
function settingsHtml() {
  const { ov, cars } = state;
  const fuel = t(`fuel_${ov.ref_fuel}`);
  const pref = languagePreference();
  return `<header class="top"><div><h1>${esc(t("nav_settings"))}${state.offline ? `<span class="offline-badge">${esc(t("offline"))}</span>` : ""}</h1></div></header>
    ${cars.length > 1 ? `<section class="group glass"><div class="row"><span class="k">${esc(t("s_car"))}</span>
      <select id="car">${cars.map((c) => `<option value="${esc(c.config_entry_id)}" ${c.config_entry_id === state.entry ? "selected" : ""}>${esc(c.title)}</option>`).join("")}</select></div></section>` : ""}
    <section class="group glass"><h3>${esc(t("s_prices"))}</h3>
      <div class="row"><span class="k">${esc(t("s_power"))}</span><span class="vv">${num(ov.electricity_price, 3)}</span></div>
      <div class="row"><span class="k">${esc(t("s_ref_fuel", { fuel }))}</span><span class="vv">${num(ov.ref_fuel_price, 3)}</span></div>
      <a class="row" href="${auth.BASE}/config/integrations/integration/car_costs" target="_blank" rel="noopener"><span>${esc(t("s_edit_ha"))}</span><span>↗</span></a>
      <div class="footnote">${esc(t("s_prices_note"))}</div></section>
    <section class="group glass"><div class="row"><span class="k">${esc(t("s_language"))}</span>
      <select id="lang"><option value="auto" ${pref === "auto" ? "selected" : ""}>${esc(t("s_auto"))}</option>
      ${LANGS.map((l) => `<option value="${l}" ${pref === l ? "selected" : ""}>${{ it: "Italiano", de: "Deutsch", en: "English" }[l]}</option>`).join("")}</select></div></section>
    <section class="group glass">${auth.EMBEDDED ? "" : `<button class="row" id="logout"><span class="neg">${esc(t("s_logout"))}</span></button>`}
      <div class="row"><span class="k">${esc(t("s_version"))}</span><span class="vv">${esc(ov.version)}</span></div></section>`;
}

// ------------------------------------------------------------------ render
const VIEWS = { overview: overviewHtml, log: logHtml, charts: chartsHtml, settings: settingsHtml };

function labelTabs() {
  $$("[data-l]").forEach((el) => (el.textContent = t(el.dataset.l)));
  document.title = t("app_name");
}

function render() {
  if (!state.ov) return;
  labelTabs();
  const y = window.scrollY;
  root.innerHTML = `<div class="view v-${state.tab}">${VIEWS[state.tab]()}</div>`;
  $("#tabs").hidden = false;
  $$("#tabs [data-tab]").forEach((b) => b.classList.toggle("on", b.dataset.tab === state.tab));
  requestAnimationFrame(() => requestAnimationFrame(() => {
    $$(".ring .fg").forEach((c) => (c.style.strokeDashoffset = c.dataset.off));
    $$(".bar i").forEach((i) => (i.style.width = `${i.dataset.w}%`));
  }));
  loadThumbs(root);
  window.scrollTo(0, y);
  hideSplash();
}

function go(tab) {
  if (tab === state.tab) { window.scrollTo({ top: 0, behavior: "smooth" }); return; }
  buzz(5);
  state.tab = tab;
  render();
  window.scrollTo(0, 0);
}

// ------------------------------------------------------------------ events
document.addEventListener("click", (e) => {
  const el = e.target;
  const tab = el.closest("[data-tab]");
  if (tab) return go(tab.dataset.tab);
  if (el.closest("#fab")) return openAdd();
  const goto = el.closest("[data-goto]");
  if (goto) return go(goto.dataset.goto);
  const open = el.closest("[data-open]");
  if (open) {
    const m = movements().find((x) => x.id === open.dataset.open);
    if (m) { buzz(5); openDetail(m); }
    return;
  }
  const filter = el.closest("[data-filter]");
  if (filter) { state.filter = filter.dataset.filter; buzz(4); return render(); }
  const range = el.closest("[data-range]");
  if (range) { state.range = Number(range.dataset.range); buzz(4); return render(); }
  const tip = el.closest("[data-tip]");
  if (tip) { const r = tip.closest(".chart")?.querySelector("[data-readout]"); if (r) r.textContent = tip.dataset.tip; return; }
  if (el.closest("#logout")) {
    auth.logout().then(() => { state.ov = null; state.hist = null; localStorage.removeItem(CACHE_KEY); showLogin(); });
  }
});
document.addEventListener("input", (e) => {
  if (e.target.id !== "search") return;
  state.q = e.target.value;
  const pos = e.target.selectionStart;
  render();
  const s = $("#search"); s.focus(); s.setSelectionRange(pos, pos);
});
document.addEventListener("change", (e) => {
  if (e.target.id === "car") {
    state.entry = e.target.value; state.ov = null; localStorage.setItem(ENTRY_KEY, state.entry); skeleton(); refresh();
  } else if (e.target.id === "lang") { setLanguage(e.target.value); render(); }
});

// refresh when coming back to the foreground, and every minute while open
document.addEventListener("visibilitychange", () => { if (!document.hidden && state.ov) refresh({ quiet: true }); });
setInterval(() => { if (!document.hidden && state.ov && !document.body.classList.contains("lock")) refresh({ quiet: true }); }, 60000);
addEventListener("online", () => state.ov && refresh({ quiet: true }));

// pull to refresh
{
  const ptr = $("#ptr");
  let y0 = null, dy = 0;
  addEventListener("touchstart", (e) => { y0 = window.scrollY <= 0 && !document.body.classList.contains("lock") ? e.touches[0].clientY : null; }, { passive: true });
  addEventListener("touchmove", (e) => {
    if (y0 == null) return;
    dy = e.touches[0].clientY - y0;
    if (dy > 0) ptr.style.transform = `translate(-50%,${Math.min(dy / 2, 70) - 60}px)`;
  }, { passive: true });
  addEventListener("touchend", async () => {
    if (y0 == null) return;
    const pulled = dy > 110;
    y0 = null; dy = 0;
    if (!pulled) { ptr.style.transform = ""; return; }
    buzz(10);
    ptr.classList.add("spin"); ptr.style.transform = "translate(-50%,10px)";
    await refresh({ quiet: true });
    ptr.classList.remove("spin"); ptr.style.transform = "";
  });
}

// ------------------------------------------------------------------- start
async function start() {
  $("#tabs").hidden = true;
  labelTabs();
  try { await auth.finishLogin(); } catch { /* shown below as unreachable */ }
  if (!auth.hasTokens()) return showLogin();
  if (loadCache()) { render(); state.offline = false; }   // instant first paint, then refresh
  else skeleton();
  const ok = await refresh();
  if (!ok && state.ov && !state.offline) { state.offline = true; render(); }
}

if (auth.EMBEDDED) document.documentElement.classList.add("embed");
if ("serviceWorker" in navigator && !auth.EMBEDDED) navigator.serviceWorker.register("sw.js").catch(() => {});
start();
