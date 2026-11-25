// Builds docs/images/screenshots.png (collage) and docs/images/demo.gif from the panel in the fake Home Assistant.
// Usage: node make_docs.mjs   (needs Playwright's Chromium; the GIF uses the ffmpeg that Playwright installs)
import { chromium } from "playwright";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import gifenc from "gifenc";
const { GIFEncoder, applyPalette, quantize } = gifenc;
import pngjs from "pngjs";
const { PNG } = pngjs;
import { fileURLToPath } from "node:url";
import { startFake } from "./fake_ha.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const IMAGES = path.resolve(here, "../../docs/images");
fs.mkdirSync(IMAGES, { recursive: true });
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "carcosts-docs-"));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const fake = await startFake();
const browser = await chromium.launch();

async function panel({ w, h, dark, narrow, lang = "it", scale = 2 }) {
  fake.reset();
  const context = await browser.newContext({
    viewport: { width: w, height: h }, deviceScaleFactor: scale, isMobile: narrow, hasTouch: narrow, locale: `${lang}-${lang.toUpperCase()}`,
  });
  const page = await context.newPage();
  await page.goto(`${fake.url}/host?dark=${dark ? 1 : 0}&narrow=${narrow ? 1 : 0}&lang=${lang}`);
  const frame = page.frameLocator("iframe");
  await frame.locator(".hero").waitFor({ timeout: 10000 });
  await wait(1600);
  return { context, page, frame };
}

async function receipt() {
  const ctx = await browser.newContext();
  const p = await ctx.newPage();
  await p.setContent(`<body style="margin:0;width:900px;height:1400px;background:#f4f1ea;font:40px monospace"><div style="padding:80px">ARAL<br>Tauberbischofsheim<br><br>Super E10<br>38,21 L x 1,767<br><br><b>GESAMT 67,50 EUR</b></div></body>`);
  const file = path.join(tmp, "receipt.jpg");
  fs.writeFileSync(file, await p.screenshot({ type: "jpeg", quality: 80, clip: { x: 0, y: 0, width: 900, height: 1400 } }));
  await ctx.close();
  return file;
}
const receiptFile = await receipt();

// ---------------------------------------------------------------- screenshots
const shots = {};
async function phone(name, dark, action) {
  const { context, page, frame } = await panel({ w: 390, h: 844, dark, narrow: true });
  if (action) await action(frame, page);
  shots[name] = (await page.screenshot()).toString("base64");
  await context.close();
}
await phone("overview-dark", true);
await phone("log-light", false, async (f) => { await f.locator('[data-tab="log"]').click(); await wait(900); });
await phone("charts-dark", true, async (f) => { await f.locator('[data-tab="charts"]').click(); await wait(1200); });
await phone("scan-light", false, async (f, page) => {
  await f.locator("#fab").click();
  await f.locator("#scanfile").waitFor();
  await f.locator("#scanfile").setInputFiles(receiptFile);
  await f.locator("#f_qty").waitFor();
  await wait(600);
});
await phone("overview-light", false);
for (const dark of [true, false]) {
  const { context, page } = await panel({ w: 1280, h: 800, dark, narrow: false });
  shots[`tablet-${dark ? "dark" : "light"}`] = (await page.screenshot()).toString("base64");
  await context.close();
}

const img = (k, w) => `<img src="data:image/png;base64,${shots[k]}" style="width:${w}px;border-radius:34px;box-shadow:0 18px 50px rgba(0,0,0,.28)">`;
const html = `<body style="margin:0;padding:48px;width:1640px;background:linear-gradient(135deg,#0c3b2e,#1f6f8b);font-family:sans-serif">
  <div style="display:flex;gap:28px;justify-content:center">${["overview-dark", "log-light", "charts-dark", "scan-light", "overview-light"].map((k) => img(k, 290)).join("")}</div>
  <div style="display:flex;gap:28px;justify-content:center;margin-top:36px">${img("tablet-dark", 760)}${img("tablet-light", 760)}</div></body>`;
const cp = await (await browser.newContext({ viewport: { width: 1736, height: 800 }, deviceScaleFactor: 1 })).newPage();
await cp.setContent(html);
await wait(500);
await cp.screenshot({ path: path.join(IMAGES, "screenshots.png"), fullPage: true });
console.log("wrote screenshots.png");

// ------------------------------------------------------------------- demo gif
{
  const { context, page, frame } = await panel({ w: 390, h: 844, dark: true, narrow: true, scale: 0.77 });
  const frames = [];
  let recording = true;
  const grab = (async () => {
    while (recording) { frames.push({ png: await page.screenshot(), at: Date.now() }); await wait(40); }
  })();
  await wait(1200);
  await frame.locator("#fab").click();
  await wait(900);
  await frame.locator("#scanfile").setInputFiles(receiptFile);
  await frame.locator("#f_qty").waitFor();
  await wait(2200);
  await frame.locator("#save").click();
  await wait(1800);
  await frame.locator('[data-tab="log"]').click();
  await wait(1800);
  await frame.locator('[data-tab="overview"]').click();
  await wait(2200);
  recording = false;
  await grab;
  await context.close();
  const decoded = frames.map((f) => PNG.sync.read(f.png));
  const { width, height } = decoded[0];
  const sample = Buffer.concat([0.15, 0.4, 0.7, 0.95].map((x) => decoded[Math.floor(decoded.length * x)].data));
  const palette = quantize(sample, 128);
  const gif = GIFEncoder();
  decoded.forEach((png, i) => {
    const delay = i + 1 < frames.length ? Math.max(40, frames[i + 1].at - frames[i].at) : 1500;
    gif.writeFrame(applyPalette(png.data, palette), width, height, { palette, delay });
  });
  gif.finish();
  fs.writeFileSync(path.join(IMAGES, "demo.gif"), gif.bytes());
  console.log("wrote demo.gif", (fs.statSync(path.join(IMAGES, "demo.gif")).size / 1024).toFixed(0), "KB,", frames.length, "frames");
}
await browser.close();
await fake.close();
fs.rmSync(tmp, { recursive: true, force: true });
