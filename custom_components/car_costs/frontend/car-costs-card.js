/* Car Costs card — served by the car_costs integration. */
const CC_VERSION = "0.2.0";

const I18N = {
  it: {
    vs: "rispetto a", paid_back: "ammortizzato", saved: "Risparmiato", of: "su",
    break_even: "Pareggio previsto", never: "non ancora prevedibile", reached: "raggiunto!",
    spent: "Speso (benzina + corrente)", ref_would: "{ref} avrebbe speso", energy_sav: "Risparmio carburante",
    fixed_sav: "Costi fissi", per100: "€/100 km", km: "km percorsi", month: "al mese",
    refuel: "Rifornimento", charge: "Ricarica", receipt: "Scontrino",
    liters: "Litri", kwh: "kWh", total: "Totale €", odometer: "Km (facoltativo)", date: "Data",
    station: "Distributore", where: "Dove", home: "Casa", public: "Colonnina",
    save: "Salva", cancel: "Annulla", reading: "Leggo lo scontrino…", check: "Controlla i dati letti e salva",
    incomplete: "Non ho letto tutto: completa i campi mancanti", history: "Ultime voci",
    empty: "Nessuna voce ancora. Aggiungi il primo rifornimento o scatta la foto di uno scontrino.",
    del_confirm: "Eliminare questa voce?", err: "Errore", home_auto: "A casa i kWh arrivano già dalla presa: inserisci a mano solo le ricariche fuori casa.",
    cost_auto: "vuoto = prezzo di casa", days: "giorni", fuel: "benzina", electricity: "corrente",
  },
  en: {
    vs: "compared with", paid_back: "paid back", saved: "Saved", of: "of",
    break_even: "Expected break-even", never: "not predictable yet", reached: "reached!",
    spent: "Spent (fuel + electricity)", ref_would: "{ref} would have spent", energy_sav: "Fuel savings",
    fixed_sav: "Fixed costs", per100: "€/100 km", km: "km driven", month: "per month",
    refuel: "Refuel", charge: "Charge", receipt: "Receipt",
    liters: "Litres", kwh: "kWh", total: "Total €", odometer: "Odometer (optional)", date: "Date",
    station: "Station", where: "Where", home: "Home", public: "Public",
    save: "Save", cancel: "Cancel", reading: "Reading the receipt…", check: "Check what was read and save",
    incomplete: "Could not read everything: fill in the missing fields", history: "Latest entries",
    empty: "No entries yet. Add your first refuel or take a photo of a receipt.",
    del_confirm: "Delete this entry?", err: "Error", home_auto: "Home kWh already come from the plug: only add charges away from home.",
    cost_auto: "empty = home price", days: "days", fuel: "fuel", electricity: "electricity",
  },
  de: {
    vs: "im Vergleich zu", paid_back: "amortisiert", saved: "Gespart", of: "von",
    break_even: "Voraussichtlicher Break-even", never: "noch nicht absehbar", reached: "erreicht!",
    spent: "Ausgegeben (Kraftstoff + Strom)", ref_would: "{ref} hätte gekostet", energy_sav: "Ersparnis Energie",
    fixed_sav: "Fixkosten", per100: "€/100 km", km: "gefahrene km", month: "pro Monat",
    refuel: "Tanken", charge: "Laden", receipt: "Beleg",
    liters: "Liter", kwh: "kWh", total: "Gesamt €", odometer: "Km-Stand (optional)", date: "Datum",
    station: "Tankstelle", where: "Wo", home: "Zu Hause", public: "Öffentlich",
    save: "Speichern", cancel: "Abbrechen", reading: "Beleg wird gelesen…", check: "Gelesene Daten prüfen und speichern",
    incomplete: "Nicht alles lesbar: fehlende Felder ergänzen", history: "Letzte Einträge",
    empty: "Noch keine Einträge. Ersten Tankvorgang hinzufügen oder einen Beleg fotografieren.",
    del_confirm: "Diesen Eintrag löschen?", err: "Fehler", home_auto: "kWh zu Hause kommen schon von der Steckdose: nur Ladungen unterwegs eintragen.",
    cost_auto: "leer = Hauspreis", days: "Tage", fuel: "Kraftstoff", electricity: "Strom",
  },
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

class CarCostsCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._mode = null; // null | refuel | charge | scanning
    this._form = {};
    this._msg = "";
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  static getStubConfig() { return {}; }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: "auto" }; }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) { this._load(); this._subscribe(); }
  }

  get _t() {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").slice(0, 2);
    return I18N[lang] || I18N.en;
  }

  get _lang() { return this._hass?.locale?.language || this._hass?.language || "it"; }

  disconnectedCallback() {
    if (this._unsub) { this._unsub.then((u) => u()).catch(() => {}); this._unsub = null; }
  }
  connectedCallback() { if (this._hass && !this._unsub) { this._subscribe(); this._load(); } }

  _subscribe() {
    if (!this._hass?.connection || this._unsub) return;
    this._unsub = this._hass.connection.subscribeEvents((ev) => {
      const id = ev.data && ev.data.config_entry_id;
      if (this._data && id && id !== this._data.config_entry_id) return;
      // Don't rebuild the form while the user is typing; refresh when it closes.
      if (this._mode) { this._stale = true; return; }
      this._load();
    }, "car_costs_updated");
  }

  async _load() {
    try {
      const msg = { type: "car_costs/entries", limit: this._config.limit || 15 };
      if (this._config.config_entry_id) msg.config_entry_id = this._config.config_entry_id;
      this._data = await this._hass.callWS(msg);
      this._error = null;
    } catch (e) {
      this._error = e.message || String(e);
    }
    this._render();
  }

  _eur(v, digits = 2) {
    if (v === null || v === undefined) return "–";
    return new Intl.NumberFormat(this._lang, { style: "currency", currency: "EUR", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v);
  }
  _num(v, digits = 0) {
    if (v === null || v === undefined) return "–";
    return new Intl.NumberFormat(this._lang, { maximumFractionDigits: digits }).format(v);
  }
  _date(iso) {
    if (!iso) return "";
    const [y, m, d] = iso.split("-").map(Number);
    return new Intl.DateTimeFormat(this._lang, { day: "numeric", month: "short", year: "numeric" }).format(new Date(y, m - 1, d));
  }

  _render() {
    const t = this._t;
    const root = this.shadowRoot;
    if (this._error) {
      root.innerHTML = `${this._style()}<ha-card><div class="pad err">${esc(t.err)}: ${esc(this._error)}</div></ha-card>`;
      return;
    }
    if (!this._data) { root.innerHTML = `${this._style()}<ha-card><div class="pad">…</div></ha-card>`; return; }
    const d = this._data, s = d.summary;
    const pct = s.amortization ?? 0;
    const ring = Math.max(0, Math.min(100, pct));
    const savClass = s.total_savings >= 0 ? "pos" : "neg";
    const today = new Date().toISOString().slice(0, 10);
    let be = t.never;
    if (s.break_even_date) be = s.break_even_date <= today ? t.reached : this._date(s.break_even_date);

    root.innerHTML = `${this._style()}
    <ha-card>
      <div class="head">
        <div>
          <div class="title">${esc(this._config.title || d.title)}</div>
          <div class="sub">${esc(t.vs)} ${esc(d.ref_name)} · ${this._num(s.days)} ${esc(t.days)}</div>
        </div>
        <ha-icon icon="mdi:car-electric"></ha-icon>
      </div>

      <div class="hero">
        <div class="ring" style="--p:${ring}">
          <div class="ring-in"><b>${this._num(pct, 1)}%</b><span>${esc(t.paid_back)}</span></div>
        </div>
        <div class="hero-txt">
          <div class="lbl">${esc(t.saved)}</div>
          <div class="big ${savClass}">${this._eur(s.total_savings)}</div>
          <div class="muted">${esc(t.of)} ${this._eur(s.investment, 0)}</div>
          <div class="muted">${this._eur(s.savings_per_month)} ${esc(t.month)}</div>
          <div class="be"><ha-icon icon="mdi:flag-checkered"></ha-icon>${esc(t.break_even)}: <b>${esc(be)}</b></div>
        </div>
      </div>

      <div class="grid">
        ${this._tile("mdi:cash", t.spent, this._eur(s.energy_cost), `${this._eur(s.fuel_cost)} ${t.fuel} · ${this._eur(s.electricity_cost)} ${t.electricity}`)}
        ${this._tile("mdi:car-side", t.ref_would.replace("{ref}", d.ref_name), this._eur(s.reference_cost), `${this._num(d.ref_fuel_price, 3)} €/L`)}
        ${this._tile("mdi:piggy-bank-outline", t.energy_sav, this._eur(s.energy_savings), "", s.energy_savings >= 0 ? "pos" : "neg")}
        ${this._tile("mdi:file-document-outline", t.fixed_sav, this._eur(s.fixed_cost_savings), "", s.fixed_cost_savings >= 0 ? "pos" : "neg")}
        ${this._tile("mdi:speedometer", t.per100, `${this._eur(s.cost_per_100km)}`, `${esc(d.ref_name)}: ${this._eur(s.reference_cost_per_100km)}`)}
        ${this._tile("mdi:counter", t.km, this._num(s.km_driven), `${this._num(s.fuel_liters, 1)} L · ${this._num(s.electricity_kwh, 1)} kWh`)}
      </div>

      <div class="actions">
        <button data-act="refuel"><ha-icon icon="mdi:gas-station"></ha-icon>${esc(t.refuel)}</button>
        <button data-act="charge"><ha-icon icon="mdi:ev-station"></ha-icon>${esc(t.charge)}</button>
        <button data-act="receipt" class="accent"><ha-icon icon="mdi:camera"></ha-icon>${esc(t.receipt)}</button>
        <input type="file" accept="image/*,application/pdf" hidden>
      </div>

      ${this._formHtml()}

      <div class="hist">
        <div class="lbl">${esc(t.history)}</div>
        ${d.entries.length ? d.entries.map((e) => this._row(e)).join("") : `<div class="muted">${esc(t.empty)}</div>`}
      </div>
    </ha-card>`;
    this._bind();
  }

  _tile(icon, label, value, sub = "", cls = "") {
    return `<div class="tile"><ha-icon icon="${icon}"></ha-icon><div class="tl">${esc(label)}</div><div class="tv ${cls}">${value}</div>${sub ? `<div class="ts">${esc(sub)}</div>` : ""}</div>`;
  }

  _row(e) {
    const t = this._t;
    const refuel = e.kind === "refuel";
    const icon = refuel ? "mdi:gas-station" : e.location === "home" ? "mdi:home-lightning-bolt" : "mdi:ev-station";
    const qty = refuel ? `${this._num(e.liters, 2)} L` : `${this._num(e.kwh, 2)} kWh`;
    const unit = refuel ? (e.liters ? e.total_cost / e.liters : null) : (e.kwh ? e.total_cost / e.kwh : null);
    const extra = [e.station, e.note].filter(Boolean).join(" · ");
    return `<div class="row">
      <ha-icon icon="${icon}"></ha-icon>
      <div class="rm"><div>${qty} · <b>${this._eur(e.total_cost)}</b>${unit ? ` <span class="muted">(${this._num(unit, 3)} €/${refuel ? "L" : "kWh"})</span>` : ""}</div>
      <div class="muted">${this._date(e.date)}${extra ? " · " + esc(extra) : ""}${e.source === "receipt" ? ' · <ha-icon class="mini" icon="mdi:receipt-text-check"></ha-icon>' : ""}</div></div>
      <button class="x" data-del="${esc(e.id)}" title="${esc(t.del_confirm)}"><ha-icon icon="mdi:delete-outline"></ha-icon></button>
    </div>`;
  }

  _formHtml() {
    const t = this._t, f = this._form, m = this._mode;
    if (!m) return "";
    if (m === "scanning") return `<div class="form"><div class="spin"></div><div>${esc(t.reading)}</div></div>`;
    const refuel = m === "refuel";
    const input = (key, label, type = "number", step = "0.01", ph = "") =>
      `<label>${esc(label)}<input name="${key}" type="${type === "number" ? "text" : type}" ${type === "number" ? `inputmode="${step === "1" ? "numeric" : "decimal"}" autocomplete="off"` : ""} value="${esc(f[key] ?? "")}" placeholder="${esc(ph)}"></label>`;
    return `<div class="form">
      ${this._msg ? `<div class="note">${esc(this._msg)}</div>` : ""}
      ${f.image_url ? "" : ""}
      <div class="fields">
        ${refuel ? input("liters", t.liters) : input("kwh", t.kwh)}
        ${input("total_cost", t.total, "number", "0.01", refuel ? "" : (f.location === "home" ? t.cost_auto : ""))}
        ${input("date", t.date, "date")}
        ${input("odometer", t.odometer, "number", "1")}
        ${input("station", t.station, "text")}
        ${refuel ? "" : `<label>${esc(t.where)}<select name="location">
            <option value="public" ${f.location !== "home" ? "selected" : ""}>${esc(t.public)}</option>
            <option value="home" ${f.location === "home" ? "selected" : ""}>${esc(t.home)}</option></select></label>`}
      </div>
      ${!refuel && this._data.has_home_meter ? `<div class="muted small">${esc(t.home_auto)}</div>` : ""}
      <div class="factions"><button data-act="cancel">${esc(t.cancel)}</button><button data-act="save" class="accent">${esc(t.save)}</button></div>
    </div>`;
  }

  _bind() {
    const root = this.shadowRoot;
    root.querySelectorAll("button[data-act]").forEach((b) => b.addEventListener("click", () => this._action(b.dataset.act)));
    root.querySelectorAll("button[data-del]").forEach((b) => b.addEventListener("click", () => this._delete(b.dataset.del)));
    root.querySelectorAll(".form input, .form select").forEach((el) =>
      el.addEventListener("input", () => { this._form[el.name] = el.value; }));
    const file = root.querySelector("input[type=file]");
    file?.addEventListener("change", () => { if (file.files[0]) this._scan(file.files[0]); });
  }

  _action(act) {
    const today = new Date();
    const iso = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    if (act === "refuel" || act === "charge") {
      this._mode = act; this._msg = "";
      this._form = { date: iso, location: act === "charge" ? (this._data.has_home_meter ? "public" : "home") : undefined };
      this._render();
    } else if (act === "receipt") {
      this.shadowRoot.querySelector("input[type=file]").click();
    } else if (act === "cancel") {
      this._mode = null;
      if (this._stale) { this._stale = false; this._load(); } else this._render();
    } else if (act === "save") {
      this._save();
    }
  }

  async _shrink(file) {
    if (!file.type.startsWith("image/")) return file;
    try {
      const bmp = await createImageBitmap(file);
      const scale = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
      const c = document.createElement("canvas");
      c.width = Math.round(bmp.width * scale); c.height = Math.round(bmp.height * scale);
      c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
      const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.85));
      return blob ? new File([blob], "receipt.jpg", { type: "image/jpeg" }) : file;
    } catch (e) { return file; }
  }

  async _scan(file) {
    const t = this._t;
    this._mode = "scanning"; this._render();
    try {
      const body = new FormData();
      body.append("file", await this._shrink(file));
      const res = await this._hass.fetchWithAuth(`/api/car_costs/receipt/${this._data.config_entry_id}`, { method: "POST", body });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || json.message || res.status);
      const r = json.result;
      this._mode = r.kind === "charge" ? "charge" : "refuel";
      this._form = { ...r, source: "receipt" };
      this._msg = r.complete ? t.check : t.incomplete;
    } catch (e) {
      this._mode = null;
      alertMsg(this, `${t.err}: ${e.message || e}`);
    }
    this._render();
  }

  async _save() {
    const f = this._form, refuel = this._mode === "refuel";
    const num = (v) => (v === "" || v === undefined || v === null ? undefined : Number(String(v).replace(",", ".")));
    const data = { config_entry_id: this._data.config_entry_id };
    if (refuel) { data.liters = num(f.liters); } else { data.kwh = num(f.kwh); data.location = f.location || "public"; }
    const total = num(f.total_cost);
    if (total !== undefined) data.total_cost = total;
    if (num(f.odometer)) data.odometer = num(f.odometer);
    if (f.date) data.date = f.date;
    if (f.station) data.station = f.station;
    const note = [f.fuel, f.source === "receipt" ? "📷" : ""].filter(Boolean).join(" ");
    if (note) data.note = note;
    if (!(refuel ? data.liters : data.kwh) || (refuel && data.total_cost === undefined)) {
      this._msg = this._t.incomplete; this._render(); return;
    }
    try {
      await this._hass.callService("car_costs", refuel ? "add_refuel" : "add_charge", data);
      this._mode = null; this._form = {}; this._stale = false;
      await this._load();
    } catch (e) { this._msg = `${this._t.err}: ${e.message || e}`; this._render(); }
  }

  async _delete(id) {
    if (!confirm(this._t.del_confirm)) return;
    try {
      await this._hass.callService("car_costs", "delete_entry", { config_entry_id: this._data.config_entry_id, entry_id: id });
    } catch (e) { alertMsg(this, `${this._t.err}: ${e.message || e}`); }
  }

  _style() {
    return `<style>
      :host { --cc-pos: var(--success-color, #43a047); --cc-neg: var(--error-color, #e53935); --cc-acc: var(--primary-color); }
      ha-card { overflow: hidden; }
      .pad { padding: 16px; } .err { color: var(--cc-neg); }
      .head { display: flex; justify-content: space-between; align-items: center; padding: 16px 16px 4px; }
      .head ha-icon { color: var(--cc-acc); --mdc-icon-size: 30px; }
      .title { font-size: 1.25em; font-weight: 600; }
      .sub, .muted { color: var(--secondary-text-color); font-size: .88em; }
      .small { font-size: .8em; margin-top: 6px; }
      .hero { display: flex; gap: 18px; align-items: center; padding: 12px 16px; }
      .ring { --s: 116px; width: var(--s); height: var(--s); flex: none; border-radius: 50%;
        background: conic-gradient(var(--cc-pos) calc(var(--p) * 1%), var(--divider-color, #ddd) 0); display: grid; place-items: center; }
      .ring-in { width: 84%; height: 84%; border-radius: 50%; background: var(--ha-card-background, var(--card-background-color, #fff));
        display: flex; flex-direction: column; align-items: center; justify-content: center; }
      .ring-in b { font-size: 1.45em; } .ring-in span { font-size: .75em; color: var(--secondary-text-color); }
      .lbl { font-size: .8em; text-transform: uppercase; letter-spacing: .04em; color: var(--secondary-text-color); }
      .big { font-size: 1.9em; font-weight: 700; line-height: 1.15; }
      .pos { color: var(--cc-pos); } .neg { color: var(--cc-neg); }
      .be { margin-top: 6px; font-size: .9em; display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
      .be ha-icon { --mdc-icon-size: 18px; color: var(--cc-acc); }
      .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; padding: 4px 16px 12px; }
      .tile { background: var(--secondary-background-color, rgba(127,127,127,.08)); border-radius: 12px; padding: 10px 12px; }
      .tile ha-icon { --mdc-icon-size: 20px; color: var(--cc-acc); }
      .tl { font-size: .78em; color: var(--secondary-text-color); margin-top: 2px; }
      .tv { font-size: 1.2em; font-weight: 600; } .ts { font-size: .75em; color: var(--secondary-text-color); }
      .actions, .factions { display: flex; gap: 8px; padding: 0 16px 12px; flex-wrap: wrap; }
      .factions { padding: 10px 0 0; justify-content: flex-end; }
      button { font: inherit; display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--divider-color, #ccc);
        background: transparent; color: var(--primary-text-color); border-radius: 999px; padding: 8px 14px; cursor: pointer; }
      .actions button { flex: 1 1 0; justify-content: center; min-width: 0; padding: 8px 8px; gap: 4px; white-space: nowrap; }
      button.accent { background: var(--cc-acc); color: var(--text-primary-color, #fff); border-color: var(--cc-acc); }
      button ha-icon { --mdc-icon-size: 20px; }
      .form { margin: 0 16px 12px; padding: 12px; border-radius: 12px; background: var(--secondary-background-color, rgba(127,127,127,.08)); }
      .fields { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }
      label { display: flex; flex-direction: column; font-size: .8em; color: var(--secondary-text-color); gap: 3px; }
      input, select { font: inherit; font-size: 1rem; padding: 8px; border-radius: 8px; border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, #fff); color: var(--primary-text-color); min-width: 0; }
      .note { margin-bottom: 8px; font-weight: 500; }
      .spin { width: 26px; height: 26px; border: 3px solid var(--divider-color); border-top-color: var(--cc-acc); border-radius: 50%;
        animation: r 1s linear infinite; margin: 4px auto 8px; } @keyframes r { to { transform: rotate(360deg); } }
      .form:has(.spin) { text-align: center; }
      .hist { padding: 4px 16px 16px; }
      .row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid var(--divider-color, #eee); }
      .row > ha-icon { color: var(--cc-acc); } .rm { flex: 1; min-width: 0; }
      .rm .muted { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      ha-icon.mini { --mdc-icon-size: 14px; }
      button.x { border: none; padding: 6px; color: var(--secondary-text-color); }
    </style>`;
  }
}

function alertMsg(el, message) {
  el.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }));
}

if (!customElements.get("car-costs-card")) {
  customElements.define("car-costs-card", CarCostsCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: "car-costs-card", name: "Car Costs", description: "Costi auto, confronto e ammortamento", preview: false });
  console.info(`%c CAR-COSTS-CARD %c ${CC_VERSION} `, "background:#43a047;color:#fff", "");
}
