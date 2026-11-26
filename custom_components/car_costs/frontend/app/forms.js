/* "＋" sheet, receipt scan flow, entry forms and entry details. */

import { api, apiJson, ApiError, LoginRequired } from "./auth.js";
import { t, num, eur, dateLabel, todayIso } from "./i18n.js";
import { $, $$, esc, buzz, toast, openSheet, sheetHead, closeAllSheets, confirmDialog, receiptUrl, forgetReceipt, viewImage, shrinkImage } from "./ui.js";

let ctx; // { state, refresh }
export function initForms(c) { ctx = c; }

export function parseNum(value) {
  let s = String(value ?? "").trim().replace(/\s/g, "");
  if (!s) return NaN;
  const comma = s.lastIndexOf(","), dot = s.lastIndexOf(".");
  if (comma > -1 && dot > -1) s = comma > dot ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
  else if (comma > -1) s = s.replace(",", ".");
  return Number(s);
}

const service = (name, data) => apiJson(`/api/services/car_costs/${name}`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ config_entry_id: ctx.state.entry, ...data }),
});

function setSheet(sheet, html) { sheet.el.innerHTML = `${sheetHead()}${html}`; sheet.el.scrollTop = 0; }

// ------------------------------------------------------------------- ＋ sheet
export function openAdd() {
  buzz();
  const sheet = openSheet(`<h2>${esc(t("add_title"))}</h2>
    <label class="choice primary" for="scanfile"><span class="e">📷</span><span><b>${esc(t("add_scan"))}</b><small>${esc(t("add_scan_sub"))}</small></span>
      <input id="scanfile" class="vh" type="file" accept="image/*" aria-label="${esc(t("add_scan"))}"></label>
    <button class="choice" data-kind="refuel"><span class="e">⛽</span><span><b>${esc(t("add_refuel"))}</b><small>${esc(t("add_refuel_sub"))}</small></span></button>
    <button class="choice" data-kind="charge"><span class="e">🔌</span><span><b>${esc(t("add_charge"))}</b><small>${esc(t("add_charge_sub"))}</small></span></button>`);
  $("#scanfile", sheet.el).onchange = (e) => { const file = e.target.files[0]; if (file) scanFlow(sheet, file); };
  sheet.el.onclick = (e) => {
    const b = e.target.closest("[data-kind]");
    if (b) openForm(sheet, { mode: "add", kind: b.dataset.kind });
  };
}

// ------------------------------------------------------------------- receipt
async function scanFlow(sheet, file) {
  const preview = URL.createObjectURL(file);
  setSheet(sheet, `<div class="scanning"><div class="scanbox" style="background-image:url('${preview}')"></div>
    <b>${esc(t("scanning"))}</b></div>`);
  buzz(12);
  let image = null;
  try {
    const blob = await shrinkImage(file);
    const fd = new FormData();
    fd.append("file", blob, "receipt.jpg");
    const res = await api(`/api/car_costs/receipt/${ctx.state.entry}`, { method: "POST", body: fd });
    const body = await res.json().catch(() => ({}));
    if (res.status === 422) {
      image = body.image || null;
      return scanFailed(sheet, body.error || "", image);
    }
    if (!res.ok) throw new ApiError(body.message || `HTTP ${res.status}`, res.status, body);
    const r = body.result;
    const read = new Set(), missing = new Set();
    (r[r.kind === "refuel" ? "liters" : "kwh"] ? read : missing).add("qty");
    (r.total_cost != null ? read : missing).add("total");
    if (r.station) read.add("station");
    buzz([10, 40, 10]);
    openForm(sheet, {
      mode: "add", kind: r.kind, scan: true, allowKind: true, image: r.image, read, missing,
      location: "public",
      values: { date: r.date, station: r.station || "", qty: r.liters ?? r.kwh ?? "", total: r.total_cost ?? "", note: r.fuel || "" },
    });
  } catch (e) {
    if (e instanceof LoginRequired) return ctx.relogin();
    scanFailed(sheet, e.message || "", image);
  } finally {
    setTimeout(() => URL.revokeObjectURL(preview), 60000);
  }
}

function scanFailed(sheet, message, image) {
  const noAi = /AI Task is not set up/i.test(message);
  setSheet(sheet, `<h2>${esc(noAi ? t("no_ai_title") : t("ai_failed"))}</h2>
    <div class="note warn"><b>${esc(noAi ? t("no_ai_title") : t("ai_failed"))}</b>${esc(noAi ? t("no_ai_text") : message)}</div>
    <div class="btns"><button class="btn" id="manual">${esc(t("enter_manual"))}</button></div>`);
  $("#manual", sheet.el).onclick = () => openForm(sheet, { mode: "add", kind: "refuel", image, allowKind: true });
}

// ----------------------------------------------------------------- the form
function lastStation(kind) {
  const entries = ctx.state.ov.entries;
  if (kind === "refuel") return ctx.state.ov.last_station || "";
  return entries.find((e) => e.kind === "charge" && e.location !== "home" && e.station)?.station || "";
}
function stationList() {
  return [...new Set(ctx.state.ov.entries.map((e) => e.station).filter(Boolean))].slice(0, 12);
}

function field({ id, label, value = "", type = "text", cls = "", hint = "", list = "", mode = "" }) {
  return `<div class="field ${cls}" data-f="${id}"><label for="f_${id}">${esc(label)}</label>
    <input id="f_${id}" name="${id}" type="${type}" value="${esc(value)}" ${mode ? `inputmode="${mode}"` : ""} ${list ? `list="${list}"` : ""}
      autocomplete="off" autocapitalize="${type === "text" && !mode ? "words" : "off"}" enterkeyhint="done">
    ${hint ? `<div class="hint">${esc(hint)}</div>` : ""}</div>`;
}

function formHtml(f) {
  const refuel = f.kind === "refuel";
  const home = !refuel && f.location === "home";
  const v = f.values;
  const flag = (k) => (f.read.has(k) ? "read" : f.missing.has(k) ? "missing" : "");
  const title = f.mode === "edit" ? t("edit") : f.scan ? t("scan_check") : refuel ? t("add_refuel") : t("add_charge");
  const price = ctx.state.ov.electricity_price;
  return `<h2>${esc(title)}</h2>
  ${f.scan ? `<p class="muted" style="margin:-6px 2px 12px">${esc(f.missing.size ? t("scan_missing") : "✓ " + t("scan_hint_read"))}</p>` : ""}
  <form class="form" novalidate>
    ${f.allowKind ? `<div class="seg" data-seg="kind"><button type="button" data-v="refuel" class="${refuel ? "on" : ""}">⛽ ${esc(t("add_refuel"))}</button><button type="button" data-v="charge" class="${refuel ? "" : "on"}">🔌 ${esc(t("add_charge"))}</button></div>` : ""}
    ${refuel ? "" : `<div class="seg" data-seg="location"><button type="button" data-v="home" class="${home ? "on" : ""}">🏠 ${esc(t("place_home"))}</button><button type="button" data-v="public" class="${home ? "" : "on"}">🔌 ${esc(t("place_public"))}</button></div>`}
    <div class="two">
      ${field({ id: "date", label: t("f_date"), value: v.date, type: "date" })}
      ${field({ id: "qty", label: refuel ? t("f_liters") : t("f_kwh"), value: v.qty, mode: "decimal", cls: flag("qty") })}
    </div>
    <div class="two">
      ${field({ id: "total", label: home ? t("f_total_opt") : t("f_total"), value: v.total, mode: "decimal", cls: flag("total"), hint: home ? t("home_cost_hint", { price: num(price, 3) }) : "" })}
      ${field({ id: "km", label: t("f_km"), value: v.km ?? "", mode: "numeric" })}
    </div>
    ${home ? "" : field({ id: "station", label: t("f_station"), value: v.station, list: "stations", cls: flag("station") })}
    <datalist id="stations">${stationList().map((s) => `<option value="${esc(s)}">`).join("")}</datalist>
    <div class="muted" id="priceLine" style="min-height:20px;text-align:center"></div>
    <div class="btns"><button class="btn" type="submit" id="save">${esc(t("save"))}</button></div>
  </form>`;
}

function collect(sheet, f) {
  for (const k of ["date", "qty", "total", "km", "station"]) {
    const el = $(`#f_${k}`, sheet.el);
    if (el) f.values[k] = el.value;
  }
}

function openForm(sheet, init) {
  const f = {
    mode: "add", kind: "refuel", location: "public", read: new Set(), missing: new Set(), image: null, scan: false, allowKind: false,
    ...init,
    values: { date: todayIso(), qty: "", total: "", km: "", station: "", note: "", ...(init.values || {}) },
  };
  if (f.mode === "add" && !f.values.station && !init.values?.station) f.values.station = lastStation(f.kind);
  const render = () => {
    setSheet(sheet, formHtml(f));
    const form = $("form", sheet.el);
    const priceLine = () => {
      const q = parseNum($("#f_qty", sheet.el).value), c = parseNum($("#f_total", sheet.el).value);
      $("#priceLine", sheet.el).textContent = q > 0 && c > 0 ? t(f.kind === "refuel" ? "price_l" : "price_kwh", { p: num(c / q, 3) }) : "";
    };
    form.addEventListener("input", (e) => {
      e.target.closest(".field")?.classList.remove("read", "missing", "bad");
      priceLine();
    });
    priceLine();
    sheet.el.querySelectorAll("[data-seg] button").forEach((b) => (b.onclick = () => {
      collect(sheet, f);
      const seg = b.parentElement.dataset.seg;
      if (seg === "kind") {
        f.kind = b.dataset.v;
        if (f.mode === "add" && !f.read.has("station")) f.values.station = lastStation(f.kind);
        f.read.delete("qty"); f.missing.delete("qty");
      } else f.location = b.dataset.v;
      buzz(6); render();
    }));
    form.onsubmit = (e) => { e.preventDefault(); submit(sheet, f); };
  };
  render();
}

async function submit(sheet, f) {
  collect(sheet, f);
  const v = f.values, refuel = f.kind === "refuel", home = !refuel && f.location === "home";
  const qty = parseNum(v.qty), total = parseNum(v.total), km = parseNum(v.km);
  const bad = [];
  if (!(qty > 0)) bad.push("qty");
  if (!home && !(total > 0)) bad.push("total");
  if (home && v.total !== "" && !(total >= 0)) bad.push("total");
  if (!v.date) bad.push("date");
  $$(".field", sheet.el).forEach((el) => el.classList.toggle("bad", bad.includes(el.dataset.f)));
  if (bad.length) { buzz([20, 30, 20]); sheet.el.classList.remove("shake"); void sheet.el.offsetWidth; $("form", sheet.el).classList.add("shake"); toast(t("err_required")); return; }

  const station = home ? null : (v.station || "").trim() || null;
  const odometer = Number.isFinite(km) && km > 0 ? km : null;
  const data = { [refuel ? "liters" : "kwh"]: qty, date: v.date, station, odometer };
  if (!home || Number.isFinite(total)) data.total_cost = total;
  if (!refuel) data.location = f.location;
  const btn = $("#save", sheet.el);
  btn.disabled = true;
  try {
    if (f.mode === "edit") {
      if (home && !Number.isFinite(total)) data.total_cost = Math.round(qty * ctx.state.ov.electricity_price * 100) / 100;
      await service("update_entry", { entry_id: f.id, ...data });
    } else {
      if (f.image) data.image = f.image;
      if (v.note && refuel) data.note = v.note;
      if (station === null) delete data.station;
      if (odometer === null) delete data.odometer;
      await service(refuel ? "add_refuel" : "add_charge", data);
    }
  } catch (e) {
    btn.disabled = false;
    if (e instanceof LoginRequired) return ctx.relogin();
    toast(t("save_error", { msg: e.message }));
    return;
  }
  buzz([12, 40, 12]);
  closeAllSheets();
  toast(t("saved_toast"));
  await ctx.refresh();
}

// ------------------------------------------------------------------- details
export function openDetail(m) {
  const e = m.entry;
  const refuel = e.kind === "refuel", home = e.location === "home";
  const title = refuel ? e.station || t("refuel") : home ? t("charge_home") : e.station || t("charge");
  const qty = refuel ? `${num(e.liters, 2)} L` : `${num(e.kwh, 2)} kWh`;
  const unit = `${eur(e.total_cost / (refuel ? e.liters : e.kwh), 3)}/${refuel ? "L" : "kWh"}`;
  const rows = [
    [t("f_date"), dateLabel(e.date)],
    e.station && [t("f_station"), esc(e.station)],
    [refuel ? t("f_liters") : t("f_kwh"), qty],
    [refuel ? "€/L" : "€/kWh", unit],
    !refuel && [t("f_place"), home ? t("place_home") : t("place_public")],
    e.odometer && [t("f_km"), `${num(e.odometer, 0)} km`],
    e.note && [refuel ? t("f_fuel_name") : t("f_note"), esc(e.note)],
    [" ", e.source === "receipt" ? `🧾 ${t("source_receipt")}` : t("source_manual")],
  ].filter(Boolean);
  const sheet = openSheet(`<h2>${esc(title)}</h2>
    <div class="detail-amount">${eur(e.total_cost, 2)}</div>
    <div id="receipt"></div>
    <div class="kv">${rows.map(([k, val]) => `<div><span>${k}</span><span>${val}</span></div>`).join("")}</div>
    <div class="btns two"><button class="btn ghost" id="edit">✏️ ${esc(t("edit"))}</button><button class="btn danger" id="del">🗑️ ${esc(t("delete"))}</button></div>`);
  if (e.has_image) {
    receiptUrl(e.id).then((url) => {
      if (!url) return;
      $("#receipt", sheet.el).innerHTML = `<img class="receipt-thumb" alt="${esc(t("detail_receipt"))}" src="${url}"><div class="receipt-cap">${esc(t("detail_zoom"))}</div>`;
      $("#receipt img", sheet.el).onclick = () => viewImage(url);
    });
  }
  $("#edit", sheet.el).onclick = () => openForm(sheet, {
    mode: "edit", id: e.id, kind: e.kind, location: e.location || "public", image: e.image,
    values: { date: e.date, qty: refuel ? e.liters : e.kwh, total: e.total_cost, km: e.odometer ?? "", station: e.station || "", note: e.note || "" },
  });
  $("#del", sheet.el).onclick = async () => {
    const yes = await confirmDialog({ title: t("confirm_delete"), text: t("confirm_delete_text"), ok: t("delete") });
    if (!yes) return;
    try { await service("delete_entry", { entry_id: e.id }); }
    catch (err) { if (err instanceof LoginRequired) return ctx.relogin(); toast(t("save_error", { msg: err.message })); return; }
    forgetReceipt(e.id);
    buzz([10, 30, 10]);
    sheet.close();
    toast(t("deleted"));
    await ctx.refresh();
  };
}
