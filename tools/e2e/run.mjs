// Screenshots (390x844, light and dark) and checks of the web app against the fake Home Assistant.
// Usage: npm install && npx playwright install chromium && node run.mjs
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startFake, LINK_CODE, DEVICE_TOKEN } from "./fake_ha.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(here, "shots");
fs.mkdirSync(OUT, { recursive: true });

let failures = 0;
const ok = (cond, msg) => { if (cond) console.log(`  ok   ${msg}`); else { failures++; console.log(`  FAIL ${msg}`); } };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// The phone opens the link made in the panel: no Home Assistant login. On a desktop browser the app
// then offers to be installed; the tests continue in the browser.
async function openApp(page) {
  await page.goto(`${fake.url}/car-costs#c=${LINK_CODE}`);
  await page.waitForSelector(".hero, #install-go");
  if (await page.locator("#install-go").count()) await page.click("#install-go");
  await page.waitForSelector(".hero");
}

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

  // no access yet: the app offers to ask for it (confirmed in Home Assistant), never Home Assistant's login
  await page.goto(`${fake.url}/car-costs`);
  await page.waitForSelector("#ask");
  await shot(page, S("00-request"));
  ok(await page.locator(".center h1").innerText() === "Richiedi l'accesso", "no token: \"Richiedi l'accesso\" in Italian, no link or QR asked");
  ok(await page.locator("#who").inputValue() === "Telefono", "the phone name is filled in");
  ok(!fake.calls.some((c) => c.action === "request"), "nothing is asked before the button is pressed");
  await page.click("#other");
  await page.waitForSelector("#paste");
  await shot(page, S("00-link"));
  ok(await page.locator(".center h1").innerText() === "Serve un collegamento", "no link: \"Serve un collegamento\" in Italian");
  ok((await page.locator(".center p").innerText()).includes("Copia il link dal pannello"), "no link: tells to copy the link from the panel");
  ok(!fake.calls.some((c) => c.action === "oauth"), "no redirect to Home Assistant's login");
  await page.fill("#pasted", "not a link");
  await page.click("#paste button");
  await page.waitForSelector(".center p");
  ok((await page.locator(".center p").innerText()).includes("non è valido"), "a wrong paste says the link is not valid");
  await page.fill("#pasted", `${fake.url}/car-costs#c=${LINK_CODE}`);
  await page.click("#paste button");
  await page.waitForSelector("#install-go");
  await shot(page, S("00-install"));
  await page.click("#install-go");
  await page.waitForSelector(".hero");
  ok(!page.url().includes(LINK_CODE), "the link's code is out of the address once used");
  ok(await page.evaluate(([t]) => localStorage.getItem("car_costs_device") === t, [DEVICE_TOKEN]), "the phone keeps its own token");
  ok(fake.calls.filter((c) => c.action === "activate").length === 1 && !fake.calls.some((c) => c.action === "oauth"), "linked with one activation, no Home Assistant login");
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
  ok((await page.locator('a[href$="/config/integrations/integration/car_costs"]').count()) === 0, "the phone has no link into Home Assistant");
  ok(await page.locator("#phones").count() === 0, "the phone has no link-a-phone section");

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
  await openApp(page);
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
    await p.page.goto(`${fake.url}/car-costs#c=${LINK_CODE}`);
    await p.page.waitForSelector(".hero, #install-go");
    if (await p.page.locator("#install-go").count()) await p.page.click("#install-go");
    await p.page.waitForSelector(".hero");
    await settle(p.page);
    await shot(p.page, `light-16-${loc}`);
    ok((await p.page.locator('[data-tab="overview"]').innerText()).includes(expect), `${loc}: tab label "${expect}"`);
    await p.context.close();
  }
}

// "Esci" forgets the token on the phone; a revoked phone is sent back to the link screen
{
  const { context, page } = await newPage("light");
  await openApp(page);
  await page.click('[data-tab="settings"]');
  await page.click("#logout");
  await page.waitForSelector("#ask");
  ok(await page.evaluate(() => !localStorage.getItem("car_costs_device")), "the token is removed from the phone");
  await openApp(page);
  fake.station.revoked = true;                 // unlinked from the panel
  await page.reload();
  await page.waitForSelector("#ask");
  ok((await page.locator(".center p").innerText()).includes("scollegato"), "an unlinked phone is told to ask for access again");
  ok(await page.evaluate(() => !localStorage.getItem("car_costs_device")), "an unlinked phone forgets its token");
  fake.station.revoked = false;
  await context.close();
}

// the request: ask, wait with the code, the administrator confirms in Home Assistant
{
  fake.reset();
  const { context, page } = await newPage("light");
  await page.goto(`${fake.url}/car-costs`);
  await page.click("#ask button");
  await page.waitForSelector(".codebox");
  await wait(600);
  await shot(page, "light-00-waiting");
  ok((await page.locator(".codebox").innerText()) === "4821", "waiting: the check code is shown");
  ok((await page.locator(".center p").innerText()).includes("Conferma sul telefono di Home Assistant"), "waiting: \"Conferma sul telefono di Home Assistant\"");
  const asked = fake.calls.find((c) => c.action === "request");
  ok(asked && asked.name === "Telefono" && !asked.auth, "the request carries the phone name and no credentials");
  await page.reload();                                    // the app was closed and opened again
  await page.waitForSelector(".codebox");
  ok((await page.locator(".codebox").innerText()) === "4821" && fake.calls.filter((c) => c.action === "request").length === 1, "closed and reopened: it keeps waiting, no second request");
  await wait(1800);
  ok(fake.calls.some((c) => c.action === "poll"), "the phone checks the request");
  ok(await page.evaluate(() => !localStorage.getItem("car_costs_device")), "no token while waiting");
  fake.decide("approved");
  await page.waitForSelector("#install-go", { timeout: 9000 });
  ok(await page.evaluate(([x]) => localStorage.getItem("car_costs_device") === x && !localStorage.getItem("car_costs_request"), [DEVICE_TOKEN]), "approved: the phone keeps the token it was given");
  await page.click("#install-go");
  await page.waitForSelector(".hero");
  ok(true, "approved: the overview opens");
  await context.close();
}
{
  const { context, page } = await newPage("light");
  await page.goto(`${fake.url}/car-costs`);
  await page.click("#ask button");
  await page.waitForSelector(".codebox");
  fake.decide("rejected");
  await page.waitForSelector("#ask", { timeout: 9000 });
  ok((await page.locator(".center p").innerText()).includes("rifiutata"), "rejected: a clear message");
  ok((await page.locator("#ask button").innerText()) === "Riprova", "rejected: a Retry button");
  await page.click("#ask button");
  await page.waitForSelector(".codebox");
  await page.click("#cancel-req");
  await page.waitForSelector("#ask");
  ok(fake.calls.some((c) => c.action === "cancel") && await page.evaluate(() => !localStorage.getItem("car_costs_request")), "Cancel withdraws the request");
  await page.click("#ask button");
  await page.waitForSelector(".codebox");
  fake.decide("expired");
  await page.waitForSelector("#ask", { timeout: 9000 });
  ok((await page.locator(".center p").innerText()).includes("scaduta"), "expired: a clear message");
  fake.station.limited = true;
  await page.click("#ask button");
  await page.waitForFunction(() => document.querySelector(".center p")?.textContent.includes("Troppe richieste"));
  ok(true, "too many requests: told to wait");
  fake.station.limited = false;
  await context.close();
}

// permissions: "view only" has no + and no edit/delete
{
  const { context, page } = await newPage("light");
  fake.station.perm = "view";
  await openApp(page);
  ok(await page.locator("#fab").evaluate((e) => getComputedStyle(e).visibility) === "hidden", "view only: no + button");
  await page.locator('[data-tab="log"]').click();
  await page.locator('[data-open="e1"]').click();
  await page.waitForSelector(".sheet.in");
  ok(await page.locator("#edit").count() === 0 && await page.locator("#del").count() === 0, "view only: no edit or delete in the details");
  await page.keyboard.press("Escape");
  fake.station.perm = "add";
  await page.reload(); await page.waitForSelector(".hero");
  await page.locator('[data-tab="log"]').click();
  await page.locator('[data-open="e1"]').click();
  await page.waitForSelector(".sheet.in");
  ok(await page.locator("#edit").count() === 0, "add only: cannot edit");
  fake.station.perm = "edit";
  await context.close();
}

// an iPhone opening the link in Safari: the link waits in the address for the Home Screen icon
{
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "it-IT",
    userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1" });
  const page = await context.newPage();
  fake.calls.length = 0;
  await page.goto(`${fake.url}/car-costs#c=${LINK_CODE}`);
  await page.waitForSelector(".center h1");
  ok(await page.locator(".center h1").innerText() === "Metti l'app sulla schermata Home", "iPhone in Safari: how to add the app to the Home Screen");
  ok(!fake.calls.some((c) => c.action === "activate"), "iPhone in Safari: the link is not used up in the browser");
  ok(page.url().includes(`?c=${LINK_CODE}`) && !page.url().includes("#c="), "iPhone: the link moves to ?c= for the icon");
  await wait(900);
  await shot(page, "light-00-install-iphone");
  ok(await page.locator('link[rel="manifest"]').count() === 0, "iPhone: no manifest, so the icon opens the address with the link");
  // simulated installation: iOS stores the page's address as the icon's start address, in new storage
  const start = page.url();
  const installed = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "it-IT", userAgent: await page.evaluate(() => navigator.userAgent) });
  await installed.addInitScript(() => Object.defineProperty(navigator, "standalone", { value: true }));
  const icon = await installed.newPage();
  await icon.goto(start);
  await icon.waitForSelector(".hero, #paste");
  ok(await icon.locator(".hero").count() === 1 && await icon.locator("#paste").count() === 0, "the icon opens the app linked, without asking for the link");
  ok(!icon.url().includes("c="), "the used code leaves the address");
  await installed.close();
  // the Home Screen icon opens that address as an installed app
  await page.addInitScript(() => Object.defineProperty(navigator, "standalone", { value: true }));
  await page.reload();
  await page.waitForSelector(".hero");
  ok(fake.calls.filter((c) => c.action === "activate").length >= 1, "iPhone icon: the app uses the link");
  ok(!page.url().includes(LINK_CODE), "iPhone icon: the code leaves the address");
  // the page itself carries no manifest (Safari reads it while loading), whoever opens it
  const html = await fetch(`${fake.url}/car_costs_static/app/index.html`).then((r) => r.text());
  ok(!/rel=["']manifest["']/.test(html), "index.html has no static manifest link");
  // Safari, no link: the instructions, and no request (the icon makes it)
  fake.reset();
  const sctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "it-IT", userAgent: await page.evaluate(() => navigator.userAgent) });
  const safari = await sctx.newPage();
  await safari.goto(`${fake.url}/car-costs`);
  await safari.waitForSelector(".center h1");
  ok(await safari.locator(".center h1").innerText() === "Metti l'app sulla schermata Home", "iPhone in Safari: instructions, not a request");
  ok((await safari.locator(".center p").innerText()).includes("conferma la richiesta"), "iPhone: tells to confirm the request after opening the icon");
  ok(!fake.calls.some((c) => c.action === "request") && await safari.locator("#other").count() === 1, "iPhone in Safari: no request, other ways offered");
  // the Home Screen icon: empty storage, no link in the address: it asks, the administrator confirms
  const home = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "it-IT", userAgent: await safari.evaluate(() => navigator.userAgent) });
  await home.addInitScript(() => Object.defineProperty(navigator, "standalone", { value: true }));
  const icon2 = await home.newPage();
  await icon2.goto(`${fake.url}/car-costs`);
  await icon2.waitForSelector("#ask");
  ok(await icon2.locator("#who").inputValue() === "iPhone", "the icon: the name is \"iPhone\"");
  await icon2.click("#ask button");
  await icon2.waitForSelector(".codebox");
  await wait(900);
  await shot(icon2, "light-00-waiting-iphone");
  fake.decide("approved");
  await icon2.waitForSelector(".hero", { timeout: 9000 });
  ok(true, "the icon: request, confirmation, overview");
  await home.close();
  await sctx.close();
  await context.close();
}

// ------------------------------------------- the panel inside Home Assistant
{
  console.log("\n== panel (side menu) ==");
  for (const [name, w, h, narrow] of [["phone", 390, 844, true], ["tablet", 1280, 800, false]]) {
    for (const scheme of ["light", "dark"]) {
      fake.reset();
      const context = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, isMobile: narrow, hasTouch: narrow, colorScheme: scheme === "dark" ? "light" : "dark", locale: "it-IT" });
      await context.addInitScript(() => localStorage.setItem("car_costs_welcome", "1"));
      const page = await context.newPage();
      const errors = [];
      page.on("console", (m) => { if (["error", "warning"].includes(m.type())) errors.push(m.text()); });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(`${fake.url}/host?dark=${scheme === "dark" ? 1 : 0}&narrow=${narrow ? 1 : 0}`);
      const frame = page.frameLocator("iframe");
      await frame.locator(".hero").waitFor({ timeout: 10000 });
      await wait(1500);
      const tag = `panel-${name}-${scheme}`;
      const ph = await page.locator("car-costs-panel").evaluate((e) => e.getBoundingClientRect().height);
      ok(Math.abs(ph - h) < 2, `${tag}: panel fills the screen height (${Math.round(ph)} of ${h})`);
      await shot(page, tag);
      ok(!fake.calls.some((c) => c.action === "oauth"), `${tag}: no login, no token request`);
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
      // phone app: the linked phones and the button to link a new one
      await frame.locator("#phones .dev").first().waitFor({ timeout: 5000 });
      ok((await frame.locator("#phones .dev").first().innerText()).includes("iPhone Marius"), `${tag}: linked phones listed`);
      if (name === "phone" && scheme === "light") { await frame.locator("#phones").scrollIntoViewIfNeeded(); await wait(300); await shot(page, "panel-phone-light-settings-phone"); }
      // the log always opens on "All", even after another filter was used
      await frame.locator('[data-tab="log"]').click(); await wait(200);
      ok(await frame.locator(".chip.on").getAttribute("data-filter") === "all", `${tag}: log opens on "All"`);
      await frame.locator('[data-filter="home"]').click(); await wait(100);
      await frame.locator('[data-tab="settings"]').click(); await frame.locator('[data-tab="log"]').click(); await wait(200);
      ok(await frame.locator(".chip.on").getAttribute("data-filter") === "all", `${tag}: log back on "All" after leaving`);
      // sheets have a close button (PC / tablet)
      await frame.locator("#fab").click(); await wait(500);
      await frame.locator(".sheet .x").click(); await wait(600);
      ok(await frame.locator(".sheet").count() === 0, `${tag}: the ✕ closes the sheet`);
      if (name === "phone" && scheme === "light") {
        const fmt = await frame.locator("html").evaluate(async () => { const m = await import("/car_costs_static/app/i18n.js"); return [m.num(-0.04, 1), m.eur(-0.3), m.pct(-0.01), m.signedEur(-0.2), m.num(-1.26, 1)]; });
        ok(!fmt.slice(0, 4).some((s) => /[-−]/.test(s)) && /1,3/.test(fmt[4]), `${tag}: no "-0" after rounding (${fmt.join(" | ")})`);
      }
      if (name === "tablet") { await frame.locator('[data-tab="charts"]').click(); await wait(900); await shot(page, `${tag}-charts`); }
      ok(errors.filter((e) => !/Failed to load resource/.test(e)).length === 0, `${tag}: no console errors${errors.length ? " " + errors.join(" | ") : ""}`);
      await context.close();
    }
  }
  // first car: the welcome sheet offers to link a phone, once
  {
    fake.reset();
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "it-IT" });
    const page = await context.newPage();
    await page.goto(`${fake.url}/host?dark=0&narrow=0`);
    const frame = page.frameLocator("iframe");
    await frame.locator("#hello-go").waitFor({ timeout: 10000 });
    await wait(600); await shot(page, "panel-welcome-phone");
    await frame.locator("#hello-go").click();
    await frame.locator("#ph-go").waitFor();
    ok(true, "welcome: the button opens the link-a-phone form");
    await frame.locator(".sheet.in .x").click(); await wait(700);
    ok(await frame.locator(".sheet").count() === 0, "welcome: ✕ closes it");
    await page.reload(); await frame.locator(".hero").waitFor({ timeout: 10000 }); await wait(800);
    ok(await frame.locator(".sheet").count() === 0, "welcome: shown only once");

    // link a phone: name, cars, permission -> QR + copy
    fake.calls.length = 0;
    await frame.locator('[data-tab="settings"]').click();
    await frame.locator("#phones .qr svg").waitFor();
    ok(await frame.locator("#phones .qr svg").count() === 1, "the panel shows a QR of the app address (no token)");
    ok((await frame.locator("#phones .qr").getAttribute("data-qr")) === "https://demo.ui.nabu.casa/car-costs", "the QR has the app address only");
    await frame.locator("#phones summary").first().click();
    await frame.locator('[data-ph="connect"]').click();
    await frame.locator("#ph-name").fill("iPad Anna");
    await frame.locator('input[name="ph-car"][value="car2"]').uncheck();
    await frame.locator('input[name="ph-perm"][value="view"]').check();
    await wait(400); await shot(page, "panel-connect-form");
    await frame.locator("#ph-go").click();
    await frame.locator(".sheet .qr svg").waitFor();
    const made = fake.calls.find((c) => c.ws === "car_costs/phone_link");
    ok(made && made.msg.name === "iPad Anna" && made.msg.permission === "view" && made.msg.entries.join() === "car1", "link made with the name, the car and the permission chosen");
    await wait(400); await shot(page, "panel-connect-qr");
    await frame.locator("#ph-copy").click(); await wait(200);
    ok(await frame.locator("#toast.in").count() === 1, "Copy confirms with a toast");
    await frame.locator('.sheet [data-close]').last().click(); await wait(600);
    ok((await frame.locator("#phones").innerText()).includes("Waiting") || (await frame.locator("#phones").innerText()).includes("In attesa"), "the unused link is listed as waiting");

    // a request from a phone: accept with permission and cars, or reject
    for (const name of ["iPhone Anna", "Android Luca"]) await fetch(`${fake.url}/api/car_costs/app/request`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
    await frame.locator('[data-tab="log"]').click(); await frame.locator('[data-tab="settings"]').click();
    await frame.locator(".row.req").first().waitFor();
    ok((await frame.locator(".row.req .code").first().innerText()) === "4821" && await frame.locator(".row.req").count() === 2, "waiting requests are listed with their code");
    await wait(300); await shot(page, "panel-requests");
    await frame.locator('[data-ph="accept"]').first().click();
    await frame.locator("#ph-ok").waitFor();
    ok(await frame.locator('input[name="ph-perm"][value="add"]').isChecked() && await frame.locator('input[name="ph-car"]:checked').count() === 2, "accept: \"view and add\" and all cars by default");
    await frame.locator('input[name="ph-perm"][value="edit"]').check();
    await frame.locator('input[name="ph-car"][value="car2"]').uncheck();
    await frame.locator("#ph-ok").click();
    await wait(500);
    const yes = fake.calls.find((c) => c.ws === "car_costs/request_decide" && c.msg.approve);
    ok(yes && yes.msg.permission === "edit" && yes.msg.cars.join() === "car1", "accepted with the permission and the cars chosen");
    await frame.locator('[data-ph="reject"]').first().click(); await wait(500);
    ok(fake.calls.some((c) => c.ws === "car_costs/request_decide" && c.msg.approve === false), "rejected from the panel");
    await frame.locator('[data-notify="mobile_app_marius"]').check(); await wait(300);
    ok(fake.calls.some((c) => c.ws === "car_costs/request_notify" && c.msg.services.join() === "mobile_app_marius"), "the phones to notify can be chosen");

    // a linked phone: rename, change permission, unlink
    // a link still waiting can be shown again (a new identical one replaces it)
    const before = fake.calls.filter((c) => c.ws === "car_costs/phone_link").length;
    await frame.locator('[data-ph="show"]').first().click();
    await frame.locator(".sheet .qr svg").waitFor();
    ok(fake.calls.filter((c) => c.ws === "car_costs/phone_link").length === before + 1 && fake.calls.some((c) => c.ws === "car_costs/phone_remove" && c.msg.invite_id), "\"Mostra link\" shows the link again");
    await frame.locator('.sheet [data-close]').last().click(); await wait(600);
    await frame.locator('[data-ph="device"]').first().click();
    await frame.locator("#ph-save").waitFor();
    await wait(400); await shot(page, "panel-device-sheet");
    await frame.locator("#ph-name").fill("iPhone di Marius");
    await frame.locator('input[name="ph-perm"][value="add"]').check();
    await frame.locator("#ph-save").click(); await wait(500);
    const upd = fake.calls.find((c) => c.ws === "car_costs/phone_update");
    ok(upd && upd.msg.name === "iPhone di Marius" && upd.msg.permission === "add", "rename and permission change are sent");
    await frame.locator('[data-ph="device"]').first().click();
    await frame.locator("#ph-new").click();
    await frame.locator("#ph-go").click();
    await frame.locator(".sheet .qr svg").waitFor();
    ok(fake.calls.filter((c) => c.ws === "car_costs/phone_link").at(-1).msg.replaces === "d1", "\"new phone\" makes a link that replaces the old one");
    await frame.locator('.sheet [data-close]').last().click(); await wait(600);
    await frame.locator('[data-ph="device"]').first().click();
    await frame.locator("#ph-unlink").click();
    await frame.locator(".dialog [data-r='1']").click(); await wait(500);
    ok(fake.calls.some((c) => c.ws === "car_costs/phone_remove" && c.msg.device_id === "d1"), "unlink removes the phone");
    ok((await frame.locator("#phones").innerText()).match(/Nessun telefono/), "the list is empty after unlinking");

    // no external address: warns that the link works at home only
    fake.station.app.external = false;
    await frame.locator('[data-ph="connect"]').click();
    await frame.locator("#ph-name").fill("Local");
    await frame.locator("#ph-go").click();
    await frame.locator(".sheet .qr svg").waitFor();
    ok(await frame.locator(".sheet .warn").count() === 1, "without an external address the link warns it works at home only");
    await context.close();
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
