/* Car Costs web app service worker: the app shell works offline, data is always live. */
const CACHE = "car-costs-0.3.0b6";
const SHELL = [
  "index.html", "app.css", "app.js", "auth.js", "i18n.js", "ui.js", "forms.js", "charts.js", "phones.js", "vendor/qrcode.js",
  "manifest.webmanifest", "icon-192.png", "icon-512.png", "apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL.map((u) => new Request(u, { cache: "reload" }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Only the app's own files; /api and /auth always go to Home Assistant.
  if (e.request.method !== "GET" || !url.pathname.startsWith("/car_costs_static/app/")) return;
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
        return res;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true }).then((r) => r || caches.match("index.html", { ignoreSearch: true }))),
  );
});
