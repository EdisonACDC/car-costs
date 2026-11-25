// Screenshots (390x844, light and dark) and checks of the web app against the fake Home Assistant.
// Usage: npm install && npx playwright install chromium && node run.mjs
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startFake } from "./fake_ha.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(here, "shots");
fs.mkdirSync(OUT, { recursive: true });

let failures = 0;
const ok = (cond, msg) => { if (cond) console.log(`  ok   ${msg}`); else { failures++; console.log(`  FAIL ${msg}`); } };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const fake = await startFake();
const browser = await chromium.launch();

async function newPage(scheme, locale = "it-IT") {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, colorScheme: scheme, locale,
    permissions: [],
  });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => { if (["error", "warning"].includes(m.type())) errors.push(`${m.type()}: ${m.text()}`); });
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  return { context, page, errors };
}

const shot = (page, name, opts = {}) => page.screenshot({ path: path.join(OUT, `${name}.png`), ...opts });
const settle = async (page, ms = 1300) => { await page.waitForLoadState("networkidle").catch(() => {}); await wait(ms); };

// a receipt photo for the upload: render something photo-like
async function receiptJpeg(browserCtx) {
  const p = await browserCtx.newPage();
  await p.setContent(`<body style="margin:0;width:900px;height:1400px;background:#f4f1ea;font:40px monospace"><div style="padding:80px">ARAL<br>Tauberbischofsheim<br><br>Super E10<br>38,21 L x 1,767<br><br><b>GESAMT 67,50 EUR</b></div></body>`);
  const buf = await p.screenshot({ type: "jpeg", quality: 80, clip: { x: 0, y: 0, width: 900, height: 1400 } });
  await p.close();
  const file = path.join(OUT, "_receipt.jpg");
  fs.writeFileSync(file, buf);
  return file;
}

// ------------------------------------------------------------------ mockup
{
  const { context, page } = await newPage("dark");
  await page.goto(`file://${path.resolve(here, "../../mockup.html")}`);
  await shot(page, "mockup-dark", { fullPage: true });
  await context.close();
  const l = await newPage("light");
  await l.page.goto(`file://${path.resolve(here, "../../mockup.html")}`);
  await shot(l.page, "mockup-light", { fullPage: true });
  await l.context.close();
}

for (const scheme of ["light", "dark"]) {
  console.log(`\n== ${scheme} ==`);
  fake.reset();
  const { context, page, errors } = await newPage(scheme);
  const S = (n) => `${scheme}-${n}`;
  const receipt = await receiptJpeg(context);

  // login
  await page.goto(`${fake.url}/car-costs`);
  await page.waitForSelector("#go");
  await shot(page, S("00-login"));
  ok(await page.locator("#go").innerText() === "Accedi a Home Assistant", "login screen in Italian");
  await page.click("#go");
  await page.waitForSelector(".hero");
  ok(!page.url().includes("code="), "code removed from the address after login");
  await settle(page);

  // overview
  await shot(page, S("01-overview"));
  await shot(page, S("01-overview-full"), { fullPage: true });
  const title = await page.locator("header.top h1").innerText();
  ok(title.startsWith("Kodiaq iV"), "overview shows the car name");
  ok((await page.locator(".big").innerText()).includes("1.052"), "savings shown in euro");
  ok((await page.locator(".pill").innerText()).includes("pareggio"), "break-even pill");
  ok(await page.locator(".grid .tile").count() === 4, "four tiles");
  ok(await page.locator(".list .row").count() === 3, "last 3 movements");
  const dash = await page.locator(".ring .fg").evaluate((c) => c.style.strokeDashoffset);
  ok(Number(dash) > 300 && Number(dash) < 352, "ring animated to 4%");

  // log
  await page.click('[data-tab="log"]');
  await settle(page, 500);
  await shot(page, S("02-log"));
  await shot(page, S("02-log-full"), { fullPage: true });
  ok(await page.locator(".monthhead").count() >= 3, "log grouped by month");
  await page.click('[data-filter="home"]');
  ok(await page.locator(".list .row").count() >= 2, "home filter keeps home charges and plug days");
  await shot(page, S("02-log-home"));
  await page.click('[data-filter="all"]');
  await page.fill("#search", "aral");
  ok(await page.locator(".list .row").count() === 2, "search by station");
  await page.fill("#search", "");

  // detail with receipt
  await page.locator('[data-open="e1"]').click();
  await page.waitForSelector(".receipt-thumb");
  await settle(page, 600);
  await shot(page, S("03-detail"));
  await page.click(".receipt-thumb");
  ok(await page.locator(".viewer img").count() === 1, "receipt opens full screen");
  await shot(page, S("03-detail-zoom"));
  await page.click(".viewer");

  // edit
  await page.click("#edit");
  await page.waitForSelector("#f_qty");
  await shot(page, S("04-edit"));
  await page.fill("#f_total", "68,10");
  await page.click("#save");
  await page.waitForSelector("#toast.in");
  const upd = fake.calls.findLast((c) => c.service === "update_entry");
  ok(upd && upd.data.total_cost === 68.1 && upd.data.entry_id === "e1" && upd.data.liters === 38.2, "edit sends update_entry with comma decimal parsed");
  await settle(page, 400);

  // delete (cancel first, then confirm)
  await page.locator('[data-open="e3"]').click();
  await page.waitForSelector("#del");
  await page.click("#del");
  await page.waitForSelector(".dialog.in");
  await shot(page, S("05-delete-confirm"));
  await page.click('.dialog [data-r="0"]');
  ok(!fake.calls.some((c) => c.service === "delete_entry"), "cancel does not delete");
  await page.click("#del");
  await page.waitForSelector(".dialog.in");
  await page.click('.dialog [data-r="1"]');
  await page.waitForSelector(".sheet", { state: "detached" });
  ok(fake.calls.some((c) => c.service === "delete_entry" && c.data.entry_id === "e3"), "delete sends delete_entry");

  // charts
  await page.click('[data-tab="charts"]');
  await settle(page, 600);
  await shot(page, S("06-charts"));
  await shot(page, S("06-charts-full"), { fullPage: true });
  ok(await page.locator(".chart svg").count() >= 4, "four charts");
  await page.locator(".chart [data-tip]").first().click();
  ok((await page.locator("[data-readout]").first().innerText()).includes("€"), "tapping a bar shows its value");
  await page.click('[data-range="3"]');
  await page.click('[data-range="0"]');

  // settings
  await page.click('[data-tab="settings"]');
  await settle(page, 300);
  await shot(page, S("07-settings"));
  ok((await page.locator(".group").first().innerText()).includes("0,320"), "electricity price read-only");
  ok((await page.locator('a[href$="/config/integrations/integration/car_costs"]').count()) === 1, "link to the integration options");

  // + sheet
  await page.click('[data-tab="overview"]');
  await page.click("#fab");
  await page.waitForSelector(".choice");
  await settle(page, 500);
  await shot(page, S("08-add-sheet"));

  // receipt scan (with AI)
  await page.setInputFiles("#scanfile", receipt);
  await page.waitForSelector(".scanbox");
  await wait(350);
  await shot(page, S("09-scanning"));
  await page.waitForSelector("#f_qty");
  await settle(page, 300);
  await shot(page, S("10-scan-form"));
  ok(await page.locator(".field.read").count() >= 2, "fields read by the AI are highlighted");
  ok((await page.inputValue("#f_qty")) === "38.21" && (await page.inputValue("#f_station")).startsWith("Aral"), "form pre-filled from the receipt");
  await page.click("#save");
  await page.waitForSelector("#toast.in");
  const added = fake.calls.findLast((c) => c.service === "add_refuel");
  ok(added && added.data.liters === 38.21 && added.data.image?.startsWith("media-source://"), "saving passes the photo's media id");
  await settle(page, 400);

  // scan with missing data
  fake.station.aiResult = { kind: "refuel", liters: 20.5, total_cost: null, date: new Date().toISOString().slice(0, 10), station: null, fuel: null, image: "media-source://media_source/local/car_costs/y.jpg", complete: false };
  await page.click("#fab");
  await page.waitForSelector("#scanfile");
  await page.setInputFiles("#scanfile", receipt);
  await page.waitForSelector("#f_qty");
  await settle(page, 300);
  await shot(page, S("11-scan-missing"));
  ok(await page.locator(".field.missing").count() === 1, "missing amount is marked red");
  await page.click("#save");
  ok(await page.locator(".field.bad").count() >= 1, "saving with a missing amount is refused");
  await wait(400);
  await shot(page, S("11-scan-missing-toast"));
  const tb = await page.locator("#toast").evaluate((e) => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return { top: r.top, bottom: r.bottom, bg: cs.backgroundColor, n: document.querySelectorAll("#toast").length }; });
  ok(tb.top >= 0 && tb.bottom < 90 && /^rgb\(/.test(tb.bg) && tb.n === 1, `toast is solid and sits at the top (top ${Math.round(tb.top)}, ${tb.bg})`);
  await page.keyboard.press("Escape");
  fake.station.aiResult = null;

  // scan without AI
  fake.station.ai = false;
  await settle(page, 400);
  await page.click("#fab");
  await page.waitForSelector("#scanfile");
  await page.setInputFiles("#scanfile", receipt);
  await page.waitForSelector("#manual");
  await shot(page, S("12-no-ai"));
  ok((await page.locator(".note").innerText()).includes("AI Task"), "clear message when AI is not set up");
  await page.click("#manual");
  await page.waitForSelector("#f_qty");
  await page.keyboard.press("Escape");
  fake.station.ai = true;

  // manual refuel
  await settle(page, 400);
  await page.click("#fab");
  await page.waitForSelector(".choice");
  await page.click('[data-kind="refuel"]');
  await page.waitForSelector("#f_qty");
  await settle(page, 300);
  await shot(page, S("13-form-refuel"));
  const inputs = await page.locator(".sheet input").evaluateAll((els) => els.map((e) => ({ id: e.id, size: parseFloat(getComputedStyle(e).fontSize) })));
  ok(inputs.every((i) => i.size >= 16), "all fields use at least 16px (no zoom on iPhone)");
  ok((await page.inputValue("#f_station")) !== "", "last station proposed");
  await page.fill("#f_qty", "31,5");
  await page.fill("#f_total", "55.10");
  await page.fill("#f_km", "12480");
  await page.click("#save");
  await page.waitForSelector("#toast.in");
  await wait(350);
  await shot(page, S("13-form-refuel-saved"));
  const r = fake.calls.findLast((c) => c.service === "add_refuel");
  ok(r.data.liters === 31.5 && r.data.total_cost === 55.1 && r.data.odometer === 12480, "comma and dot both accepted; km optional");
  await settle(page, 400);

  // home charge
  await page.click("#fab");
  await page.waitForSelector(".choice");
  await page.click('[data-kind="charge"]');
  await page.waitForSelector("#f_qty");
  await page.click('[data-seg="location"] [data-v="home"]');
  await shot(page, S("14-form-charge-home"));
  await page.fill("#f_qty", "21,4");
  await page.click("#save");
  await page.waitForSelector("#toast.in");
  const c = fake.calls.findLast((x) => x.service === "add_charge");
  ok(c.data.kwh === 21.4 && c.data.location === "home" && !("total_cost" in c.data), "home charge without cost leaves the cost to the integration");
  await settle(page, 400);

  // the 422 is the expected answer of the "AI not set up" case
  const real = errors.filter((e) => !/status of 422/.test(e));
  ok(real.length === 0, `no console errors${real.length ? ": " + real.join(" | ") : ""}`);
  await context.close();
}

// ------------------------------------------------- offline, languages, PWA
{
  console.log("\n== offline / languages / pwa ==");
  const { context, page, errors } = await newPage("dark");
  await page.goto(`${fake.url}/car-costs`);
  await page.waitForSelector("#go");
  await page.click("#go");
  await page.waitForSelector(".hero");
  await page.evaluate(() => navigator.serviceWorker.ready);
  await settle(page, 800);
  const cdp = await context.newCDPSession(page);
  const inst = await cdp.send("Page.getInstallabilityErrors");
  ok(inst.installabilityErrors.length === 0, `installable PWA${inst.installabilityErrors.length ? ": " + JSON.stringify(inst.installabilityErrors) : ""}`);
  const manifest = await page.evaluate(() => fetch(document.querySelector('link[rel="manifest"]').href).then((r) => r.json()));
  ok(manifest.icons.some((i) => i.sizes === "192x192") && manifest.icons.some((i) => i.sizes === "512x512"), "manifest has 192 and 512 icons");
  ok(await page.evaluate(() => !!document.querySelector('link[rel="apple-touch-icon"]')), "apple-touch-icon present");
  ok(await page.evaluate(() => getComputedStyle(document.body).paddingBottom !== undefined) && (await page.content()).includes("viewport-fit=cover"), "safe-area viewport");
  await context.setOffline(true);
  await page.reload();
  await page.waitForSelector(".hero", { timeout: 8000 });
  await settle(page, 600);
  await shot(page, "dark-15-offline");
  ok((await page.locator(".offline-badge").innerText()).toLowerCase() === "offline", "offline: cached summary with the offline badge");
  await context.setOffline(false);
  await context.close();
  ok(errors.filter((e) => !/Failed to load resource|net::ERR/.test(e)).length === 0, "no console errors offline/online" + errors.join(" | "));

  for (const [loc, expect] of [["de-DE", "Übersicht"], ["en-GB", "Overview"]]) {
    const p = await newPage("light", loc);
    await p.page.goto(`${fake.url}/car-costs`);
    await p.page.click("#go");
    await p.page.waitForSelector(".hero");
    await settle(p.page);
    await shot(p.page, `light-16-${loc}`);
    ok((await p.page.locator('[data-tab="overview"]').innerText()).includes(expect), `${loc}: tab label "${expect}"`);
    await p.context.close();
  }
}

// logout revokes
{
  const { context, page } = await newPage("light");
  await page.goto(`${fake.url}/car-costs`);
  await page.click("#go");
  await page.waitForSelector(".hero");
  await page.click('[data-tab="settings"]');
  await page.click("#logout");
  await page.waitForSelector("#go");
  ok(fake.calls.some((c) => c.action === "revoke"), "logout revokes the token");
  ok(await page.evaluate(() => !localStorage.getItem("car_costs_tokens")), "tokens removed from the phone");
  await context.close();
}

// ------------------------------------------- the panel inside Home Assistant
{
  console.log("\n== panel (side menu) ==");
  for (const [name, w, h, narrow] of [["phone", 390, 844, true], ["tablet", 1280, 800, false]]) {
    for (const scheme of ["light", "dark"]) {
      fake.reset();
      const context = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, isMobile: narrow, hasTouch: narrow, colorScheme: scheme === "dark" ? "light" : "dark", locale: "it-IT" });
      const page = await context.newPage();
      const errors = [];
      page.on("console", (m) => { if (["error", "warning"].includes(m.type())) errors.push(m.text()); });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(`${fake.url}/host?dark=${scheme === "dark" ? 1 : 0}&narrow=${narrow ? 1 : 0}`);
      const frame = page.frameLocator("iframe");
      await frame.locator(".hero").waitFor({ timeout: 10000 });
      await wait(1500);
      const tag = `panel-${name}-${scheme}`;
      await shot(page, tag);
      ok(!fake.calls.some((c) => c.path === "/auth/token"), `${tag}: no login, no token request`);
      ok(await page.evaluate(() => window.__fetches > 0), `${tag}: calls go through hass.fetchWithAuth`);
      // the phone's colour scheme is the opposite of Home Assistant's: the panel must follow Home Assistant
      const theme = await frame.locator("html").evaluate((e) => e.dataset.theme);
      ok(theme === scheme, `${tag}: follows Home Assistant's theme (${theme})`);
      const navBox = await frame.locator("#tabs").boundingBox();
      if (narrow) {
        ok(navBox.y > h - 120, `${tag}: bottom bar on the phone`);
        await page.locator("car-costs-panel #menu").click();
        ok(await page.evaluate(() => window.__menu) === 1, `${tag}: menu button opens Home Assistant's sidebar`);
      } else {
        ok(navBox.x < 40 && navBox.height > 250 && navBox.width < 120, `${tag}: navigation rail on the left (tablet/PC)`);
        const cols = await frame.locator(".v-overview").evaluate((e) => getComputedStyle(e).columnCount);
        ok(cols === "2", `${tag}: content on two columns`);
        ok(await page.locator("car-costs-panel #menu").isHidden(), `${tag}: no menu button when the sidebar is docked`);
      }
      await frame.locator('[data-tab="settings"]').click();
      await wait(400);
      ok(await frame.locator("#logout").count() === 0, `${tag}: no log-out button inside Home Assistant`);
      if (name === "tablet") { await frame.locator('[data-tab="charts"]').click(); await wait(900); await shot(page, `${tag}-charts`); }
      ok(errors.filter((e) => !/Failed to load resource/.test(e)).length === 0, `${tag}: no console errors${errors.length ? " " + errors.join(" | ") : ""}`);
      await context.close();
    }
  }
  // no car yet: welcome screen with the button that opens the setup
  fake.reset(); fake.station.noCars = true;
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, colorScheme: "dark", locale: "it-IT" });
  const page = await context.newPage();
  await page.goto(`${fake.url}/host?dark=1&narrow=1`);
  const frame = page.frameLocator("iframe");
  await frame.locator(".center .btn").waitFor({ timeout: 10000 });
  await wait(500);
  await shot(page, "panel-phone-dark-welcome");
  const href = await frame.locator(".center .btn").getAttribute("href");
  ok(/\/config\/integrations\/dashboard\/add\?domain=car_costs$/.test(href) && await frame.locator(".center .btn").getAttribute("target") === "_top", "welcome screen opens the Car Costs setup");
  await context.close();
  fake.reset();
}

await browser.close();
await fake.close();
console.log(failures ? `\n${failures} check(s) FAILED` : "\nAll checks passed");
process.exit(failures ? 1 : 0);
