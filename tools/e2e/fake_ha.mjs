// A tiny fake Home Assistant for the web app: static files, OAuth, and the car_costs API with demo data.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../custom_components/car_costs/frontend");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml" };

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const ago = (n) => { const d = new Date(); d.setDate(d.getDate() - n); return d; };
const r2 = (n) => Math.round(n * 100) / 100;

function seed() {
  const E = (n, kind, o) => ({ id: `e${n}`, kind, date: iso(ago(o.ago)), created: `${iso(ago(o.ago))}T1${n % 10}:00:00`, odometer: null, station: null, note: null, source: "manual", image: null, has_image: false, ...o });
  const log = [
    E(1, "refuel", { ago: 0, liters: 38.2, total_cost: 67.5, station: "Aral · Super E10", source: "receipt", image: "x", has_image: true }),
    E(2, "charge", { ago: 2, kwh: 18.4, total_cost: 10.1, station: "EnBW Lauda", location: "public" }),
    E(3, "refuel", { ago: 11, liters: 12.4, total_cost: 21.9, station: "Shell Lauda" }),
    E(4, "charge", { ago: 17, kwh: 32.0, total_cost: 17.6, station: "Ionity Würzburg", location: "public", source: "receipt", image: "x", has_image: true }),
    E(5, "refuel", { ago: 26, liters: 7.4, total_cost: 12.9, station: "Aral · Super E10" }),
    E(6, "charge", { ago: 33, kwh: 21.0, total_cost: 6.3, location: "home" }),
    E(7, "refuel", { ago: 48, liters: 5.9, total_cost: 10.4, station: "Esso Tauberbischofsheim" }),
    E(8, "charge", { ago: 55, kwh: 24.6, total_cost: 13.5, station: "EnBW Lauda", location: "public" }),
    E(9, "refuel", { ago: 73, liters: 4.7, total_cost: 8.2, station: "Shell Lauda" }),
    E(10, "charge", { ago: 84, kwh: 40.0, total_cost: 22.0, station: "Ionity Würzburg", location: "public" }),
  ];
  const homeDaily = [1, 2, 4, 9, 20, 30, 41, 52, 63, 77].map((a) => ({ date: iso(ago(a)), kwh: r2(8 + (a % 7)), cost: r2((8 + (a % 7)) * 0.32) }));
  const daily = [];
  for (let a = 91; a >= 0; a--) {
    const f = (92 - a) / 92;
    daily.push({ date: iso(ago(a)), km: Math.round(4860 * f), energy_cost: r2(281 * f), reference_cost: r2(612 * f), total_savings: r2(1052 * f * f * 0.4 + 1052 * f * 0.6), home_kwh: r2(120 * f), home_cost: r2(38 * f) });
  }
  return { log, homeDaily, daily };
}

export function startFake({ port = 0, ai = true, aiResult = null } = {}) {
  let db = seed();
  const calls = [];
  const station = { ai, aiResult };

  const summary = () => {
    const refuels = db.log.filter((e) => e.kind === "refuel"), charges = db.log.filter((e) => e.kind === "charge");
    const fuelCost = r2(refuels.reduce((a, e) => a + e.total_cost, 0)), fuelL = r2(refuels.reduce((a, e) => a + e.liters, 0));
    const homeKwh = r2(db.homeDaily.reduce((a, d) => a + d.kwh, 0));
    const elCost = r2(charges.reduce((a, e) => a + e.total_cost, 0) + db.homeDaily.reduce((a, d) => a + d.cost, 0));
    return {
      days: 92, km_driven: 4860, fuel_liters: fuelL, fuel_cost: fuelCost, electricity_kwh: r2(charges.reduce((a, e) => a + e.kwh, 0) + homeKwh),
      electricity_cost: elCost, home_kwh: homeKwh, energy_cost: r2(fuelCost + elCost), cost_per_100km: 5.78, avg_fuel_consumption: 1.2,
      reference_cost: 612, reference_cost_per_100km: 12.59, energy_savings: 331, fixed_cost_savings: -29, total_savings: 1052,
      investment: 26300, amortization: 4.0, break_even_date: iso(new Date(new Date().getFullYear() + 6, 5, 1)), savings_per_month: 343, ev_share_pct: 71,
    };
  };
  const overview = () => ({
    config_entry_id: "car1", title: "Kodiaq iV", version: "0.3.0b1", start_date: iso(ago(92)), ref_name: "VW Passat B8", ref_fuel: "diesel", ref_consumption: 5.8,
    electricity_price: 0.32, ref_fuel_price: 1.65, ev_consumption: 22, has_home_meter: true, ai_task_available: station.ai,
    last_station: db.log.filter((e) => e.kind === "refuel" && e.station).sort((a, b) => b.date.localeCompare(a.date))[0]?.station || null,
    summary: summary(), entries: [...db.log].sort((a, b) => (b.date + b.created).localeCompare(a.date + a.created)),
  });
  const history = () => {
    const names = [], d = new Date(); d.setDate(1);
    for (let i = 3; i >= 0; i--) { const m = new Date(d.getFullYear(), d.getMonth() - i, 1); names.push(`${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, "0")}`); }
    const data = { [names[0]]: [20, 40, 30], [names[1]]: [47, 150, 138], [names[2]]: [73, 190, 210], [names[3]]: [30, 120, 90] };
    return {
      config_entry_id: "car1", investment: 26300, daily: db.daily, home_daily: db.homeDaily,
      months: names.map((m, i) => {
        const [e, ref, _] = [data[m][0] * 1.1, data[m][1], 0];
        const fuel = r2(e * 0.4), pub = r2(e * 0.35), home = r2(e * 0.25);
        return { month: m, fuel_cost: fuel, fuel_liters: r2(fuel / 1.75), public_cost: pub, public_kwh: r2(pub / 0.55), home_cost: home, home_kwh: r2(home / 0.32), energy_cost: r2(fuel + pub + home), reference_cost: ref };
      }),
    };
  };

  const send = (res, status, body, type = "application/json") => {
    res.writeHead(status, { "Content-Type": type, "Cache-Control": "no-store" });
    res.end(typeof body === "string" || Buffer.isBuffer(body) ? body : JSON.stringify(body));
  };
  const readBody = (req) => new Promise((resolve) => { const c = []; req.on("data", (x) => c.push(x)); req.on("end", () => resolve(Buffer.concat(c))); });

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://x");
    const p = url.pathname;
    if (p === "/car-costs") { res.writeHead(302, { Location: "/car_costs_static/app/index.html" }); return res.end(); }
    if (p === "/host") {   // stands in for Home Assistant's frontend: it mounts the panel and gives it `hass`
      const dark = url.searchParams.get("dark") === "1", narrow = url.searchParams.get("narrow") === "1", lang = url.searchParams.get("lang") || "it";
      return send(res, 200, `<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{margin:0;height:100%;background:${dark ? "#111" : "#fafafa"}}car-costs-panel{display:block;height:100%}</style>
        <body><script type="module" src="/car_costs_static/panel.js"></script><script type="module">
        window.__menu = 0; document.addEventListener("hass-toggle-menu", () => window.__menu++);
        await customElements.whenDefined("car-costs-panel");
        const el = document.createElement("car-costs-panel");
        el.addEventListener("hass-toggle-menu", () => {});
        document.body.append(el);
        el.narrow = ${narrow};
        el.hass = { language: "${lang}", themes: { darkMode: ${dark} }, fetchWithAuth: (path, init = {}) => { window.__fetches = (window.__fetches || 0) + 1; return fetch(path, { ...init, headers: { ...(init.headers || {}), Authorization: "Bearer tok" } }); } };
        </script>`, "text/html");
    }
    if (p === "/auth/authorize") {
      const back = new URL(url.searchParams.get("redirect_uri"));
      back.searchParams.set("code", "code123"); back.searchParams.set("state", url.searchParams.get("state"));
      res.writeHead(302, { Location: back.toString() }); return res.end();
    }
    if (p === "/auth/token" && req.method === "POST") {
      const form = new URLSearchParams((await readBody(req)).toString());
      calls.push({ path: p, action: form.get("action") || form.get("grant_type") });
      if (form.get("action") === "revoke") return send(res, 200, {});
      return send(res, 200, { access_token: "tok", refresh_token: "ref", expires_in: 1800, token_type: "Bearer" });
    }
    if (p.startsWith("/car_costs_static/")) {
      const file = path.join(FRONTEND, p.slice("/car_costs_static/".length));
      if (!file.startsWith(FRONTEND) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return send(res, 404, "not found", "text/plain");
      return send(res, 200, fs.readFileSync(file), TYPES[path.extname(file)] || "application/octet-stream");
    }
    if (p.startsWith("/config/")) return send(res, 200, "<h1>Home Assistant</h1>", "text/html");
    if (p.startsWith("/api/")) {
      if (req.headers.authorization !== "Bearer tok") return send(res, 401, { message: "Unauthorized" });
      if (p === "/api/car_costs/cars") return send(res, 200, station.noCars ? [] : [{ config_entry_id: "car1", title: "Kodiaq iV" }]);
      if (p === "/api/car_costs/overview") return send(res, 200, overview());
      if (p === "/api/car_costs/history") return send(res, 200, history());
      if (p.startsWith("/api/car_costs/image/")) {
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="420"><rect width="300" height="420" fill="#fafafa"/><g font-family="monospace" font-size="15" fill="#222"><text x="20" y="40" font-size="20" font-weight="bold">ARAL Tauberbischofsheim</text><text x="20" y="90">Super E10 ........ 38,21 L</text><text x="20" y="115">Preis/L ........... 1,767</text><text x="20" y="160" font-weight="bold">GESAMT EUR ........ 67,50</text><text x="20" y="200">Datum 25.11.2026</text></g></svg>`;
        return send(res, 200, svg, "image/svg+xml");
      }
      if (p.startsWith("/api/car_costs/receipt/") && req.method === "POST") {
        await readBody(req);
        calls.push({ path: p });
        await new Promise((r) => setTimeout(r, 900));
        if (!station.ai) return send(res, 422, { error: "AI Task is not set up. Add an AI integration", image: "media-source://media_source/local/car_costs/x.jpg" });
        const result = station.aiResult || { kind: "refuel", liters: 38.21, total_cost: 67.5, price_per_unit: 1.767, date: iso(new Date()), station: "Aral Tauberbischofsheim", fuel: "Super E10", image: "media-source://media_source/local/car_costs/x.jpg", complete: true };
        return send(res, 200, { result, added: null });
      }
      const m = p.match(/^\/api\/services\/car_costs\/(\w+)$/);
      if (m && req.method === "POST") {
        const data = JSON.parse((await readBody(req)).toString() || "{}");
        calls.push({ service: m[1], data });
        if (m[1] === "add_refuel" || m[1] === "add_charge") {
          const kind = m[1] === "add_refuel" ? "refuel" : "charge";
          const total = data.total_cost ?? r2(data.kwh * 0.32);
          db.log.push({ id: `n${db.log.length + 1}`, kind, date: data.date, created: new Date().toISOString(), liters: data.liters, kwh: data.kwh, total_cost: total, location: data.location, station: data.station || null, odometer: data.odometer || null, note: data.note || null, source: "manual", image: data.image || null, has_image: !!data.image });
        } else if (m[1] === "update_entry") {
          const e = db.log.find((x) => x.id === data.entry_id);
          if (!e) return send(res, 400, { message: "Car Costs: log entry not found." });
          const { entry_id, config_entry_id, ...rest } = data; Object.assign(e, rest);
        } else if (m[1] === "delete_entry") db.log = db.log.filter((x) => x.id !== data.entry_id);
        return send(res, 200, []);
      }
      return send(res, 404, { message: "not found" });
    }
    send(res, 404, "not found", "text/plain");
  });
  return new Promise((resolve) => server.listen(port, "127.0.0.1", () => {
    resolve({ url: `http://127.0.0.1:${server.address().port}`, calls, station, reset: () => { db = seed(); calls.length = 0; station.ai = true; station.aiResult = null; station.noCars = false; }, close: () => new Promise((r) => server.close(r)) });
  }));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const s = await startFake({ port: Number(process.env.PORT || 8123), ai: process.env.AI !== "0" });
  console.log(`Fake Home Assistant: ${s.url}/car-costs`);
}
