# Changelog

## 0.3.0b4 (pre-release)

- **The phone no longer needs a Home Assistant account.** In the panel, **Settings → Phone app → Link a
  phone**: a name, the cars it can see and what it may do (*View only*, *View and add*, *View, add and
  change*). The result is a link with a one-time token after the `#` (24 hours, never in a log), shown as
  a QR code with Copy and Share. The phone trades it for a device token (256 bits, stored in Home
  Assistant only as a SHA-256 hash, renewed every 30 days) and keeps it in `localStorage`. The model is
  Family Hub's guest invites.
- New API for phones under `/api/car_costs/app/` (`requires_auth=False`, device token only): `activate`,
  `me`, `cars`, `overview`, `history`, `image`, `receipt`, `service/{add_refuel,add_charge,update_entry,
  delete_entry}`. A phone only gets its own cars, and only what its permission allows; never entities or
  configuration. Rate limits per device and per address; an address is blocked after 10 wrong activations.
- The panel lists the linked phones (name, last access, permissions) with rename, change of permissions and
  cars, unlink (it stops at once) and *new phone* (the new link replaces the old device). Websocket
  commands `car_costs/phones`, `phone_link`, `phone_update`, `phone_remove` (administrators only).
- The web app has **no Home Assistant login** any more (OAuth removed). Without a link it shows "A link is
  needed" with *Paste the link*. A phone that was unlinked is told so.
- iPhone: a link opened in Safari is kept in the address (`?c=`) and the app explains *Share → Add to Home
  Screen*; the Home Screen icon then opens the app with the link. Other phones are offered to install the
  app.
- "View only" phones have no **＋** and no edit/delete; "View and add" cannot edit or delete.
- The welcome sheet after the first car now offers to link a phone.
- Without an external address the panel warns that the link works at home only.
- `/car-costs` keeps the query string when it redirects.

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
