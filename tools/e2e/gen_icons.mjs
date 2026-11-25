// Generates the PWA icons and iPhone splash screens from HTML (run: node gen_icons.mjs).
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../custom_components/car_costs/frontend/app");
fs.mkdirSync(path.join(APP, "splash"), { recursive: true });

const bg = "radial-gradient(120% 80% at 10% 0%,#145c48,transparent 60%),radial-gradient(100% 70% at 100% 30%,#1f6f8b,transparent 60%),#0c3b2e";
const icon = (size, scale) => `<body style="margin:0;width:${size}px;height:${size}px;background:${bg};display:grid;place-items:center;overflow:hidden">
  <div style="position:relative;width:${size * scale}px;height:${size * scale}px">
    <svg viewBox="0 0 100 100" width="100%" height="100%" style="transform:rotate(-90deg)"><defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#5ef0a0"/><stop offset="1" stop-color="#7ee8fa"/></linearGradient></defs>
      <circle cx="50" cy="50" r="42" fill="rgba(255,255,255,.1)" stroke="rgba(255,255,255,.22)" stroke-width="9"/>
      <circle cx="50" cy="50" r="42" fill="none" stroke="url(#g)" stroke-width="9" stroke-linecap="round" stroke-dasharray="263.9" stroke-dashoffset="80"/></svg>
    <div style="position:absolute;inset:0;display:grid;place-items:center;font-size:${size * scale * 0.42}px;font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',sans-serif">🚙</div>
  </div></body>`;
const splash = (w, h) => `<body style="margin:0;width:${w}px;height:${h}px;background:${bg};display:grid;place-content:center;justify-items:center;gap:${w * 0.03}px;color:#fff;font-family:-apple-system,'Segoe UI',sans-serif">
  <div style="font-size:${w * 0.22}px;font-family:'Segoe UI Emoji','Apple Color Emoji',sans-serif">🚙</div><b style="font-size:${w * 0.08}px;letter-spacing:-.02em">Costi Auto</b></body>`;

const browser = await chromium.launch();
async function render(html, w, h, file) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  await page.setContent(html);
  await page.screenshot({ path: path.join(APP, file) });
  await page.close();
  console.log("wrote", file);
}
await render(icon(192, 0.82), 192, 192, "icon-192.png");
await render(icon(512, 0.82), 512, 512, "icon-512.png");
await render(icon(512, 0.6), 512, 512, "icon-maskable-512.png"); // content inside the 80 % safe zone
await render(icon(180, 0.82), 180, 180, "apple-touch-icon.png");
for (const [w, h] of [[1125, 2436], [1170, 2532], [1179, 2556], [1284, 2778], [1290, 2796]]) await render(splash(w, h), w, h, `splash/splash-${w}x${h}.png`);
await browser.close();
