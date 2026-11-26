/* "Phone app" in the panel: link a phone with a QR code, list the linked phones, change what each
 * may do, unlink. Only inside Home Assistant's panel and only for an administrator: the phone
 * itself never sees any of this. */

import * as auth from "./auth.js";
import { t, relativeDay, isoDay } from "./i18n.js";
import { $, $$, esc, buzz, toast, openSheet, sheetHead, confirmDialog } from "./ui.js";

const PERMS = ["view", "add", "edit"];
const WELCOME_KEY = "car_costs_welcome";

// ------------------------------------------------------------------ helpers
export async function fillQr(scope = document) {
  const boxes = $$("[data-qr]", scope);
  if (!boxes.length) return;
  const { default: qrcode } = await import("./vendor/qrcode.js");
  for (const b of boxes) {
    const qr = qrcode(0, "M");
    qr.addData(b.dataset.qr); qr.make();
    b.innerHTML = qr.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
  }
}

export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); }
  catch {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.append(ta); ta.select();
    try { document.execCommand("copy"); } finally { ta.remove(); }
  }
  toast(t("phone_copied"));
}

const setBody = (sheet, html) => { sheet.el.innerHTML = `${sheetHead()}${html}`; sheet.el.scrollTop = 0; };

function when(iso) {
  if (!iso) return t("ph_never");
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return t("ph_never");
  const hm = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  return `${relativeDay(isoDay(d))} ${hm}`;
}
const carNames = (ids, cars) => ids.map((id) => cars.find((c) => c.id === id)?.title).filter(Boolean).join(", ");
const wsError = (e) => (e?.code === "no_url" ? t("ph_no_url") : t("save_error", { msg: e?.message || e?.code || "" }));

// --------------------------------------------------------------- the section
/** The box in Settings. Fills itself from Home Assistant. */
export const phoneBox = () => (auth.EMBEDDED && auth.isAdmin() ? '<section class="group glass phone" id="phones"></section>' : "");

export async function mountPhones(box = $("#phones")) {
  if (!box) return;
  let data;
  try { data = await auth.callWS({ type: "car_costs/phones" }); }
  catch { box.remove(); return; }   // not an administrator, or Home Assistant is not reachable
  const { devices, invites, cars } = data;
  box.innerHTML = `<h3 style="padding:0 0 6px">${esc(t("s_phone"))}</h3>
    <div class="footnote" style="padding:0 0 12px">${esc(t("ph_intro"))}</div>
    <button class="btn" data-ph="connect">${esc(t("ph_connect"))}</button>
    <h3 style="padding:18px 0 4px">${esc(t("ph_list"))}</h3>
    ${devices.length ? devices.map((d) => `<button class="row dev" data-ph="device" data-id="${esc(d.id)}">
        <span class="m"><b>${esc(d.name)}</b><small>${esc([d.label, t(`ph_${d.permission}`), `${t("ph_last")} ${when(d.last_seen)}`].join(" · "))}</small></span><span>›</span></button>`).join("")
      : `<div class="footnote" style="padding:6px 0">${esc(t("ph_none"))}</div>`}
    ${invites.map((i) => `<div class="row dev"><span class="m"><b>${esc(i.name)}</b><small>${esc(t("ph_pending"))}</small></span>
        <button class="chip" data-ph="show" data-id="${esc(i.id)}">${esc(t("ph_show"))}</button>
        <button class="chip" data-ph="cancel" data-id="${esc(i.id)}">${esc(t("ph_cancel"))}</button></div>`).join("")}`;
  box.onclick = (e) => {
    const b = e.target.closest("[data-ph]");
    if (!b) return;
    buzz(5);
    if (b.dataset.ph === "connect") connect(cars);
    else if (b.dataset.ph === "device") deviceSheet(devices.find((d) => d.id === b.dataset.id), cars);
    else if (b.dataset.ph === "show") relink(invites.find((i) => i.id === b.dataset.id));
    else if (b.dataset.ph === "cancel") auth.callWS({ type: "car_costs/phone_remove", invite_id: b.dataset.id }).then(() => mountPhones(box), (err) => toast(wsError(err)));
  };
}
const refresh = () => mountPhones();

// -------------------------------------------------------------------- forms
function fields({ name = "", entries, permission = "add" }, cars) {
  const picked = entries || (cars.length === 1 ? [cars[0].id] : cars.map((c) => c.id));
  return `<div class="field"><label for="ph-name">${esc(t("ph_name"))}</label>
      <input id="ph-name" maxlength="40" autocomplete="off" placeholder="${esc(t("ph_name_ph"))}" value="${esc(name)}"></div>
    <div class="optgroup"><div class="lbl">${esc(t("ph_cars"))}</div>
      ${cars.map((c) => `<label class="opt"><input type="checkbox" name="ph-car" value="${esc(c.id)}" ${picked.includes(c.id) ? "checked" : ""}><span>${esc(c.title)}</span></label>`).join("")}</div>
    <div class="optgroup"><div class="lbl">${esc(t("ph_perm"))}</div>
      ${PERMS.map((p) => `<label class="opt"><input type="radio" name="ph-perm" value="${p}" ${p === permission ? "checked" : ""}><span>${esc(t(`ph_${p}`))}</span></label>`).join("")}</div>`;
}

function readFields(sheet) {
  const name = $("#ph-name", sheet.el).value.trim();
  const entries = $$('input[name="ph-car"]:checked', sheet.el).map((i) => i.value);
  const permission = $('input[name="ph-perm"]:checked', sheet.el)?.value || "view";
  if (!name) { toast(t("ph_need_name")); $("#ph-name", sheet.el).focus(); return null; }
  if (!entries.length) { toast(t("ph_need_car")); return null; }
  return { name, entries, permission };
}

// ------------------------------------------------------- link a (new) phone
export function connect(cars, preset = {}) {
  const sheet = openSheet(`<h2>${esc(t("ph_connect"))}</h2>${fields(preset, cars)}
    <div class="btns" style="margin-top:14px"><button class="btn" id="ph-go">${esc(t("ph_make"))}</button></div>`);
  $("#ph-go", sheet.el).onclick = async () => {
    const v = readFields(sheet);
    if (!v) return;
    try {
      const res = await auth.callWS({ type: "car_costs/phone_link", ...v, ...(preset.replaces ? { replaces: preset.replaces } : {}) });
      buzz([10, 40, 10]);
      showLink(sheet, res);
      refresh();
    } catch (e) { toast(wsError(e)); }
  };
}

function showLink(sheet, res) {
  setBody(sheet, `<h2>${esc(t("ph_scan_title"))}</h2>
    ${res.external ? "" : `<div class="warn">${esc(t("phone_local"))}</div>`}
    <div class="phone"><div class="qr" data-qr="${esc(res.link)}" role="img" aria-label="QR"></div>
      <p class="footnote" style="text-align:center;padding:0 0 12px">${esc(t("ph_scan"))}</p>
      <div class="btns ${navigator.share ? "two" : ""}"><button class="btn ghost" id="ph-copy">${esc(t("phone_copy"))}</button>
        ${navigator.share ? `<button class="btn" id="ph-share">${esc(t("ph_share"))}</button>` : ""}</div></div>
    <button class="btn ghost" data-close style="margin-top:12px">${esc(t("ph_done"))}</button>`);
  $("#ph-copy", sheet.el).onclick = () => copyText(res.link);
  const share = $("#ph-share", sheet.el);
  if (share) share.onclick = () => navigator.share({ title: "Costi Auto", url: res.link }).catch(() => {});
  fillQr(sheet.el);
}

/** Show a waiting link again. Only its hash is kept, so this makes an identical new link and cancels the old one. */
async function relink(invite) {
  if (!invite) return;
  const sheet = openSheet(`<h2>${esc(t("ph_scan_title"))}</h2>`);
  try {
    const res = await auth.callWS({ type: "car_costs/phone_link", name: invite.name, entries: invite.entries, permission: invite.permission, ...(invite.replaces ? { replaces: invite.replaces } : {}) });
    await auth.callWS({ type: "car_costs/phone_remove", invite_id: invite.id });
    showLink(sheet, res);
    refresh();
  } catch (e) { sheet.close(); toast(wsError(e)); }
}

// -------------------------------------------------- a linked phone: manage it
function deviceSheet(dev, cars) {
  if (!dev) return;
  const sheet = openSheet(`<h2>${esc(dev.name)}</h2>
    <p class="footnote" style="padding:0 0 12px">${esc([dev.label, `${t("ph_last")} ${when(dev.last_seen)}`].join(" · "))}</p>
    ${fields(dev, cars)}
    <div class="btns" style="margin-top:14px">
      <button class="btn" id="ph-save">${esc(t("save"))}</button>
      <button class="btn ghost" id="ph-new">${esc(t("ph_new"))}</button>
      <button class="btn danger" id="ph-unlink">${esc(t("ph_unlink"))}</button></div>`);
  $("#ph-save", sheet.el).onclick = async () => {
    const v = readFields(sheet);
    if (!v) return;
    try { await auth.callWS({ type: "car_costs/phone_update", device_id: dev.id, ...v }); }
    catch (e) { toast(wsError(e)); return; }
    sheet.close(); toast(t("saved_toast")); refresh();
  };
  $("#ph-new", sheet.el).onclick = () => {
    const v = readFields(sheet);
    if (!v) return;
    sheet.close();
    connect(cars, { ...v, replaces: dev.id });   // the old phone stops when the new one is linked
  };
  $("#ph-unlink", sheet.el).onclick = async () => {
    const yes = await confirmDialog({ title: t("ph_unlink_q", { name: dev.name }), text: t("ph_unlink_text"), ok: t("ph_unlink") });
    if (!yes) return;
    try { await auth.callWS({ type: "car_costs/phone_remove", device_id: dev.id }); }
    catch (e) { toast(wsError(e)); return; }
    buzz([10, 30, 10]); sheet.close(); toast(t("ph_unlinked")); refresh();
  };
}

// ------------------------------------------------------- first car: welcome
/** Once, after the first car is shown: offer to link a phone. */
export async function maybeWelcome() {
  if (!auth.EMBEDDED || !auth.isAdmin() || localStorage.getItem(WELCOME_KEY)) return;
  localStorage.setItem(WELCOME_KEY, "1");
  let cars;
  try { ({ cars } = await auth.callWS({ type: "car_costs/phones" })); } catch { return; }
  const sheet = openSheet(`<h2>🎉 ${esc(t("hello_title"))}</h2><p class="footnote" style="padding:0 0 12px">${esc(t("hello_text"))}</p>
    <div class="btns"><button class="btn" id="hello-go">${esc(t("ph_connect"))}</button>
      <button class="btn ghost" data-close>${esc(t("hello_later"))}</button></div>`);
  $("#hello-go", sheet.el).onclick = () => { sheet.close(); connect(cars); };
}
