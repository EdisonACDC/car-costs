# Changelog

## 0.3.0b3 (pre-release)

- **Fix:** the panel was only about 150 px tall inside Home Assistant; it now fills the screen
  (`100vh`/`100dvh`). The simulated Home Assistant used for the browser tests no longer gives the panel a
  fixed height, so the test catches this.
- **Settings → Phone app:** link of the web app (external address from Nabu Casa or Home Assistant's
  external URL; with only a local address it warns that it works at home only), **QR code** (bundled
  library, no CDN), **Copy** and **Open** buttons, and the iPhone/Android install steps. The same box
  appears once after the first car is added. The overview now returns `app` (`url`, `external`).
- No more "−0": numbers are rounded before they are formatted (ring, chart label, axis).
- The log always opens on "All" (it could stay on "Home").
- Sheets and forms have a **✕** button at the top right (for PC and tablet), besides Esc and a tap outside.

## 0.3.0b2 (pre-release)

- **"Costi Auto" in Home Assistant's side menu** (icon `mdi:car-electric`, address `/costi-auto`): the same
  glass app, mounted by the integration as a custom panel. It uses Home Assistant's own session (no second
  login) and follows its light/dark theme and language. No add-on, no Supervisor.
- The panel adapts: bottom bar on the phone (with the button that opens Home Assistant's menu), navigation
  rail on the left and two columns on tablet and PC. The same layout applies to the web app on a wide screen.
- New option **Show "Costi Auto" in the side menu** (on by default; in the setup and in *Configure*).
- Welcome screen with a button to the Car Costs setup when no car is configured.
- Repository: README in English, Italian and German, `CHANGELOG.md`, ruff and mypy (strict) configuration,
  GitHub Actions for pytest, ruff, mypy, hassfest and HACS validation, release asset `car_costs.zip`,
  badges, logo and brand images.
- Code formatted with ruff and typed for mypy; `scan_receipt` no longer checks the file on the event loop.

## 0.3.0b1 (pre-release)

- New phone web app in the "glass" style (installable PWA): overview, log, charts, settings and the **＋**
  sheet (receipt photo, refuel, charge). Italian, German and English; light and dark.
- `GET /api/car_costs/history`, a snapshot of the totals every midnight (up to 5 years) and the home
  charges from the plug meter saved per day.
- Service `car_costs.update_entry`.
- The receipt photo stays with the entry and can be shown in the log (authenticated image endpoint, only
  from `/media/car_costs`); it is deleted with the entry. Photos that end up in no entry are deleted
  after 24 hours. Photo file names get a random suffix.
- Option *electric consumption* (kWh/100 km) to estimate the share of electric kilometres.
- Deleting the integration deletes its storage file.
- Toast messages are solid, at the top, one at a time.
- The savings chart scales on the savings, with the break-even line only from 25 % of the investment.

## 0.2.0

- Integration "Car Costs": fuel and electricity costs of the new car, comparison with the old car for the
  same kilometres, fixed yearly costs, payback and break-even date.
- Refuels and charges by hand (services), home charging from a kWh sensor, receipt photo read by **AI Task**.
- Lovelace card `car-costs-card`, loaded by the integration, and the first web app at `/car-costs`.

## 0.1.0

- First version, before the repository was published. Not recorded in detail.
