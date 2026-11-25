/* Shared UI helpers: escaping, toast, haptics, bottom sheets, dialogs, receipt images. */

import { api } from "./auth.js";
import { t } from "./i18n.js";

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export function buzz(ms = 8) { try { navigator.vibrate?.(ms); } catch { /* not supported */ } }

let toastTimer;
export function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("in");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("in"), 2500);
}

// ------------------------------------------------------------------ sheets
const stack = [];

/** Open a bottom sheet. Returns {el, close}. Sheets can be stacked. */
export function openSheet(html, { onClose } = {}) {
  const backdrop = document.createElement("div");
  backdrop.className = "backdrop";
  const el = document.createElement("div");
  el.className = "sheet";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-modal", "true");
  el.innerHTML = `<div class="grab"></div>${html}`;
  const layer = $("#layer");
  layer.append(backdrop, el);
  document.body.classList.add("lock");
  const sheet = {
    el,
    close() {
      const i = stack.indexOf(sheet);
      if (i < 0) return;
      stack.splice(i, 1);
      backdrop.classList.remove("in"); el.classList.remove("in");
      setTimeout(() => { backdrop.remove(); el.remove(); }, 380);
      if (!stack.length) document.body.classList.remove("lock");
      onClose?.();
    },
  };
  stack.push(sheet);
  backdrop.onclick = () => sheet.close();
  // swipe down on the grab handle / header closes the sheet
  let y0 = null;
  el.addEventListener("touchstart", (e) => { if (el.scrollTop <= 0) y0 = e.touches[0].clientY; }, { passive: true });
  el.addEventListener("touchmove", (e) => {
    if (y0 == null) return;
    const dy = e.touches[0].clientY - y0;
    if (dy > 0) el.style.transform = `translate(-50%,${dy}px)`;
  }, { passive: true });
  el.addEventListener("touchend", (e) => {
    if (y0 == null) return;
    const dy = e.changedTouches[0].clientY - y0;
    y0 = null; el.style.transform = "";
    if (dy > 110) sheet.close();
  });
  requestAnimationFrame(() => requestAnimationFrame(() => { backdrop.classList.add("in"); el.classList.add("in"); }));
  return sheet;
}
export const closeTopSheet = () => stack.at(-1)?.close();
export const closeAllSheets = () => [...stack].forEach((s) => s.close());
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeTopSheet(); });

/** Glass confirmation dialog. Resolves true/false. */
export function confirmDialog({ title, text, ok, danger = true }) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "backdrop";
    backdrop.style.zIndex = 61;
    const box = document.createElement("div");
    box.className = "dialog glass";
    box.setAttribute("role", "alertdialog");
    box.innerHTML = `<h3>${esc(title)}</h3><p>${esc(text)}</p>
      <div class="btns two"><button class="btn ghost" data-r="0">${esc(t("cancel"))}</button>
      <button class="btn ${danger ? "danger" : ""}" data-r="1">${esc(ok)}</button></div>`;
    $("#layer").append(backdrop, box);
    const done = (v) => {
      backdrop.classList.remove("in"); box.classList.remove("in");
      setTimeout(() => { backdrop.remove(); box.remove(); }, 250);
      resolve(v);
    };
    backdrop.onclick = () => done(false);
    box.onclick = (e) => { const b = e.target.closest("[data-r]"); if (b) done(b.dataset.r === "1"); };
    requestAnimationFrame(() => { backdrop.classList.add("in"); box.classList.add("in"); });
  });
}

// ------------------------------------------------------------ receipt images
const blobs = new Map();

/** Object URL of a receipt photo (needs the auth header, so <img src> alone cannot load it). */
export async function receiptUrl(entryId) {
  if (blobs.has(entryId)) return blobs.get(entryId);
  const job = (async () => {
    const res = await api(`/api/car_costs/image/${encodeURIComponent(entryId)}`);
    if (!res.ok) return null;
    return URL.createObjectURL(await res.blob());
  })().catch(() => null);
  blobs.set(entryId, job);
  const url = await job;
  if (!url) blobs.delete(entryId);
  return url;
}
export function forgetReceipt(entryId) {
  const p = blobs.get(entryId);
  blobs.delete(entryId);
  p?.then((u) => u && URL.revokeObjectURL(u));
}

/** Fill every <div data-img="id"> thumbnail that scrolls into view. */
const io = "IntersectionObserver" in window
  ? new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (!en.isIntersecting) continue;
      io.unobserve(en.target);
      const id = en.target.dataset.img;
      receiptUrl(id).then((url) => { if (url) en.target.innerHTML = `<img alt="" src="${url}">`; });
    }
  }, { rootMargin: "200px" })
  : null;
export function loadThumbs(root = document) {
  $$("[data-img]", root).forEach((el) => (io ? io.observe(el) : receiptUrl(el.dataset.img).then((u) => u && (el.innerHTML = `<img alt="" src="${u}">`))));
}

export function viewImage(url) {
  const v = document.createElement("div");
  v.className = "viewer";
  v.innerHTML = `<img alt="" src="${url}">`;
  v.onclick = () => v.remove();
  $("#layer").append(v);
}

/** Resize a photo to at most `max` px and re-encode as JPEG. */
export async function shrinkImage(file, max = 1600, quality = 0.85) {
  let bitmap;
  try { bitmap = await createImageBitmap(file, { imageOrientation: "from-image" }); }
  catch {
    // Safari / HEIC fallbacks: draw through an <img>
    bitmap = await new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = reject;
      img.src = url;
    });
  }
  const w = bitmap.width || bitmap.naturalWidth, h = bitmap.height || bitmap.naturalHeight;
  const k = Math.min(1, max / Math.max(w, h));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(w * k); canvas.height = Math.round(h * k);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("encode"))), "image/jpeg", quality));
}
