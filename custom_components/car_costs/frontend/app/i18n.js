/* Languages (it, de, en) and number/date formatting for the Car Costs web app. */

const LOCALES = { it: "it-IT", de: "de-DE", en: "en-GB" };
export const LANGS = ["it", "de", "en"];
const LANG_KEY = "car_costs_lang";

const DICT = {
  it: {
    app_name: "Costi Auto",
    nav_overview: "Panoramica", nav_log: "Registro", nav_charts: "Grafici", nav_settings: "Impostazioni",
    login_title: "Costi Auto", login_text: "Accedi con il tuo utente di Home Assistant per vedere i costi della tua auto.",
    login_btn: "Accedi a Home Assistant", retry: "Riprova",
    unreachable: "Home Assistant non raggiungibile", no_integration: "Car Costs non è configurato in Home Assistant",
    offline: "offline", loading: "Caricamento…",
    since: "dal {date}", days_one: "{n} giorno", days_other: "{n} giorni",
    repaid: "ripagato", saved: "Risparmiato", on_invested: "su {amount} investiti",
    breakeven: "pareggio ~ {when}", breakeven_reached: "pareggio raggiunto 🎉", breakeven_unknown: "pareggio non ancora prevedibile",
    same_km: "Stessi {km} km", per100: "{a} /100 km invece di {b}", ev_share: "~{pct}% dei km in elettrico (stima)",
    tile_fuel: "benzina", tile_power: "corrente", tile_fixed: "costi fissi", tile_month: "al mese",
    tile_fuel_sub: "{l} L · {c} L/100", tile_power_sub: "{kwh} kWh", of_home: "di cui casa {kwh} kWh",
    spend_month: "Spesa al mese", legend_new: "{name}", legend_old: "{name}",
    last_moves: "Ultimi movimenti", all: "Tutti", no_moves: "Ancora nessun movimento. Tocca ＋ per iniziare.",
    f_all: "Tutto", f_fuel: "Benzina", f_charges: "Ricariche", f_home: "Casa", search: "Cerca distributore", month_total: "Totale",
    refuel: "Rifornimento", charge: "Ricarica", charge_home: "Ricarica a casa", from_meter: "presa",
    today: "Oggi", yesterday: "Ieri", nothing_found: "Nessun risultato",
    detail_receipt: "Scontrino", detail_zoom: "Tocca per ingrandire",
    edit: "Modifica", delete: "Elimina", cancel: "Annulla", close: "Chiudi", save: "Salva",
    confirm_delete: "Eliminare questa voce?", confirm_delete_text: "Verrà eliminata anche la foto dello scontrino. L'azione non si può annullare.",
    deleted: "Voce eliminata", saved_toast: "Salvato ✓", save_error: "Non riesco a salvare: {msg}",
    add_title: "Aggiungi", add_scan: "Scontrino", add_scan_sub: "Scatta o scegli una foto, la leggo io",
    add_refuel: "Rifornimento", add_refuel_sub: "Benzina o diesel, a mano", add_charge: "Ricarica", add_charge_sub: "Casa o colonnina, a mano",
    scanning: "Sto leggendo lo scontrino…", scan_pick: "Scegli una foto", scan_check: "Controlla i dati letti",
    scan_missing: "Mancano alcuni dati: completali qui sotto.", scan_hint_read: "letto dallo scontrino",
    no_ai_title: "AI non configurata",
    no_ai_text: "Per leggere gli scontrini serve un'integrazione AI in Home Assistant (OpenAI, Google Gemini, Anthropic o Ollama con modello vision). Aggiungila, poi scegli l'entità AI Task nelle opzioni di Car Costs.",
    ai_failed: "Non sono riuscito a leggere lo scontrino", enter_manual: "Inserisci a mano",
    f_date: "Data", f_station: "Distributore", f_liters: "Litri", f_kwh: "kWh", f_total: "Totale €", f_total_opt: "Costo € (facoltativo)",
    f_km: "Km (facoltativo)", f_note: "Nota", f_place: "Dove", place_home: "Casa", place_public: "Colonnina",
    f_fuel_name: "Prodotto", price_l: "{p} €/L", price_kwh: "{p} €/kWh", home_cost_hint: "Vuoto = {price} €/kWh di casa",
    err_required: "Controlla i campi in rosso",
    source_receipt: "da scontrino", source_manual: "a mano",
    range_3: "3 mesi", range_12: "12 mesi", range_all: "Tutto",
    ch_spend: "Spesa al mese", ch_cum: "Risparmio cumulato", ch_per100: "€/100 km nel tempo", ch_split: "Benzina e corrente",
    ch_progress: "{x} di {y} ({p}%)", ch_goal: "investimento {amount}", ch_no_data: "Servono ancora alcuni giorni di dati",
    legend_fuel: "Benzina", legend_public: "Colonnina", legend_home: "Casa", total: "totale",
    s_car: "Auto seguita", s_prices: "Prezzi attuali", s_power: "Corrente (€/kWh)", s_ref_fuel: "{fuel} vecchia auto (€/L)",
    s_edit_ha: "Modifica in Home Assistant", s_language: "Lingua", s_auto: "Automatica", s_logout: "Esci", s_version: "Versione",
    s_prices_note: "I prezzi si cambiano nelle opzioni dell'integrazione.", s_about: "Informazioni",
    fuel_diesel: "Diesel", fuel_petrol: "Benzina", fuel_lpg: "GPL", fuel_cng: "Metano",
    ptr_pull: "Trascina per aggiornare",
  },
  de: {
    app_name: "Autokosten",
    nav_overview: "Übersicht", nav_log: "Protokoll", nav_charts: "Diagramme", nav_settings: "Einstellungen",
    login_title: "Autokosten", login_text: "Melde dich mit deinem Home-Assistant-Benutzer an, um die Kosten deines Autos zu sehen.",
    login_btn: "Bei Home Assistant anmelden", retry: "Erneut versuchen",
    unreachable: "Home Assistant nicht erreichbar", no_integration: "Car Costs ist in Home Assistant nicht eingerichtet",
    offline: "offline", loading: "Laden…",
    since: "seit {date}", days_one: "{n} Tag", days_other: "{n} Tage",
    repaid: "amortisiert", saved: "Gespart", on_invested: "bei {amount} Investition",
    breakeven: "Break-even ~ {when}", breakeven_reached: "Break-even erreicht 🎉", breakeven_unknown: "Break-even noch nicht absehbar",
    same_km: "Gleiche {km} km", per100: "{a} /100 km statt {b}", ev_share: "~{pct}% der km elektrisch (Schätzung)",
    tile_fuel: "Benzin", tile_power: "Strom", tile_fixed: "Fixkosten", tile_month: "pro Monat",
    tile_fuel_sub: "{l} L · {c} L/100", tile_power_sub: "{kwh} kWh", of_home: "davon zu Hause {kwh} kWh",
    spend_month: "Ausgaben pro Monat", legend_new: "{name}", legend_old: "{name}",
    last_moves: "Letzte Buchungen", all: "Alle", no_moves: "Noch keine Buchungen. Tippe auf ＋, um zu starten.",
    f_all: "Alle", f_fuel: "Benzin", f_charges: "Laden", f_home: "Zu Hause", search: "Tankstelle suchen", month_total: "Summe",
    refuel: "Tanken", charge: "Laden", charge_home: "Laden zu Hause", from_meter: "Steckdose",
    today: "Heute", yesterday: "Gestern", nothing_found: "Nichts gefunden",
    detail_receipt: "Beleg", detail_zoom: "Zum Vergrößern tippen",
    edit: "Bearbeiten", delete: "Löschen", cancel: "Abbrechen", close: "Schließen", save: "Speichern",
    confirm_delete: "Diesen Eintrag löschen?", confirm_delete_text: "Das Belegfoto wird ebenfalls gelöscht. Das kann nicht rückgängig gemacht werden.",
    deleted: "Eintrag gelöscht", saved_toast: "Gespeichert ✓", save_error: "Speichern nicht möglich: {msg}",
    add_title: "Hinzufügen", add_scan: "Beleg", add_scan_sub: "Foto aufnehmen oder wählen, ich lese es",
    add_refuel: "Tanken", add_refuel_sub: "Benzin oder Diesel, manuell", add_charge: "Laden", add_charge_sub: "Zu Hause oder Säule, manuell",
    scanning: "Ich lese den Beleg…", scan_pick: "Foto wählen", scan_check: "Gelesene Daten prüfen",
    scan_missing: "Einige Daten fehlen: bitte unten ergänzen.", scan_hint_read: "vom Beleg gelesen",
    no_ai_title: "KI nicht eingerichtet",
    no_ai_text: "Zum Lesen von Belegen braucht Home Assistant eine KI-Integration (OpenAI, Google Gemini, Anthropic oder Ollama mit Vision-Modell). Füge sie hinzu und wähle dann die AI-Task-Entität in den Car-Costs-Optionen.",
    ai_failed: "Der Beleg konnte nicht gelesen werden", enter_manual: "Manuell eingeben",
    f_date: "Datum", f_station: "Tankstelle", f_liters: "Liter", f_kwh: "kWh", f_total: "Gesamt €", f_total_opt: "Kosten € (optional)",
    f_km: "Km (optional)", f_note: "Notiz", f_place: "Wo", place_home: "Zu Hause", place_public: "Säule",
    f_fuel_name: "Produkt", price_l: "{p} €/L", price_kwh: "{p} €/kWh", home_cost_hint: "Leer = {price} €/kWh Haushaltsstrom",
    err_required: "Rot markierte Felder prüfen",
    source_receipt: "vom Beleg", source_manual: "manuell",
    range_3: "3 Monate", range_12: "12 Monate", range_all: "Alles",
    ch_spend: "Ausgaben pro Monat", ch_cum: "Kumulierte Ersparnis", ch_per100: "€/100 km im Zeitverlauf", ch_split: "Benzin und Strom",
    ch_progress: "{x} von {y} ({p}%)", ch_goal: "Investition {amount}", ch_no_data: "Es fehlen noch einige Tage an Daten",
    legend_fuel: "Benzin", legend_public: "Säule", legend_home: "Zu Hause", total: "gesamt",
    s_car: "Verfolgtes Auto", s_prices: "Aktuelle Preise", s_power: "Strom (€/kWh)", s_ref_fuel: "{fuel} altes Auto (€/L)",
    s_edit_ha: "In Home Assistant ändern", s_language: "Sprache", s_auto: "Automatisch", s_logout: "Abmelden", s_version: "Version",
    s_prices_note: "Preise ändert man in den Optionen der Integration.", s_about: "Info",
    fuel_diesel: "Diesel", fuel_petrol: "Benzin", fuel_lpg: "Autogas", fuel_cng: "Erdgas",
    ptr_pull: "Zum Aktualisieren ziehen",
  },
  en: {
    app_name: "Car Costs",
    nav_overview: "Overview", nav_log: "Log", nav_charts: "Charts", nav_settings: "Settings",
    login_title: "Car Costs", login_text: "Log in with your Home Assistant user to see what your car costs.",
    login_btn: "Log in to Home Assistant", retry: "Retry",
    unreachable: "Home Assistant not reachable", no_integration: "Car Costs is not set up in Home Assistant",
    offline: "offline", loading: "Loading…",
    since: "since {date}", days_one: "{n} day", days_other: "{n} days",
    repaid: "paid back", saved: "Saved", on_invested: "of {amount} invested",
    breakeven: "break-even ~ {when}", breakeven_reached: "break-even reached 🎉", breakeven_unknown: "break-even not predictable yet",
    same_km: "Same {km} km", per100: "{a} /100 km instead of {b}", ev_share: "~{pct}% of km electric (estimate)",
    tile_fuel: "fuel", tile_power: "electricity", tile_fixed: "fixed costs", tile_month: "per month",
    tile_fuel_sub: "{l} L · {c} L/100", tile_power_sub: "{kwh} kWh", of_home: "of which home {kwh} kWh",
    spend_month: "Spending per month", legend_new: "{name}", legend_old: "{name}",
    last_moves: "Latest entries", all: "All", no_moves: "No entries yet. Tap ＋ to start.",
    f_all: "All", f_fuel: "Fuel", f_charges: "Charges", f_home: "Home", search: "Search station", month_total: "Total",
    refuel: "Refuel", charge: "Charge", charge_home: "Home charge", from_meter: "plug",
    today: "Today", yesterday: "Yesterday", nothing_found: "Nothing found",
    detail_receipt: "Receipt", detail_zoom: "Tap to enlarge",
    edit: "Edit", delete: "Delete", cancel: "Cancel", close: "Close", save: "Save",
    confirm_delete: "Delete this entry?", confirm_delete_text: "The receipt photo is deleted too. This cannot be undone.",
    deleted: "Entry deleted", saved_toast: "Saved ✓", save_error: "Could not save: {msg}",
    add_title: "Add", add_scan: "Receipt", add_scan_sub: "Take or pick a photo, I read it",
    add_refuel: "Refuel", add_refuel_sub: "Petrol or diesel, by hand", add_charge: "Charge", add_charge_sub: "Home or public, by hand",
    scanning: "Reading the receipt…", scan_pick: "Pick a photo", scan_check: "Check what was read",
    scan_missing: "Some data is missing: fill it in below.", scan_hint_read: "read from the receipt",
    no_ai_title: "AI not set up",
    no_ai_text: "Reading receipts needs an AI integration in Home Assistant (OpenAI, Google Gemini, Anthropic or Ollama with a vision model). Add one, then choose the AI Task entity in the Car Costs options.",
    ai_failed: "Could not read the receipt", enter_manual: "Enter by hand",
    f_date: "Date", f_station: "Station", f_liters: "Litres", f_kwh: "kWh", f_total: "Total €", f_total_opt: "Cost € (optional)",
    f_km: "Km (optional)", f_note: "Note", f_place: "Where", place_home: "Home", place_public: "Public",
    f_fuel_name: "Product", price_l: "{p} €/L", price_kwh: "{p} €/kWh", home_cost_hint: "Empty = {price} €/kWh home price",
    err_required: "Check the fields in red",
    source_receipt: "from receipt", source_manual: "manual",
    range_3: "3 months", range_12: "12 months", range_all: "All",
    ch_spend: "Spending per month", ch_cum: "Cumulative savings", ch_per100: "€/100 km over time", ch_split: "Fuel and electricity",
    ch_progress: "{x} of {y} ({p}%)", ch_goal: "investment {amount}", ch_no_data: "A few more days of data are needed",
    legend_fuel: "Fuel", legend_public: "Public", legend_home: "Home", total: "total",
    s_car: "Followed car", s_prices: "Current prices", s_power: "Electricity (€/kWh)", s_ref_fuel: "Old car {fuel} (€/L)",
    s_edit_ha: "Edit in Home Assistant", s_language: "Language", s_auto: "Automatic", s_logout: "Log out", s_version: "Version",
    s_prices_note: "Prices are changed in the integration options.", s_about: "About",
    fuel_diesel: "diesel", fuel_petrol: "petrol", fuel_lpg: "LPG", fuel_cng: "CNG",
    ptr_pull: "Pull to refresh",
  },
};

function detect() {
  const saved = localStorage.getItem(LANG_KEY);
  if (saved && LANGS.includes(saved)) return saved;
  const phone = (navigator.language || "en").slice(0, 2).toLowerCase();
  return LANGS.includes(phone) ? phone : "en";
}

export let lang = detect();
let nf = {};

export function setLanguage(value) {
  if (value === "auto") localStorage.removeItem(LANG_KEY);
  else localStorage.setItem(LANG_KEY, value);
  lang = detect();
  nf = {};
  document.documentElement.lang = lang;
}
export const languagePreference = () => localStorage.getItem(LANG_KEY) || "auto";
document.documentElement.lang = lang;

export function t(key, vars = {}) {
  const s = DICT[lang][key] ?? DICT.en[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ""));
}
export function days(n) { return t(n === 1 ? "days_one" : "days_other", { n }); }

const locale = () => LOCALES[lang];
function fmtr(name, opts) {
  const k = name + JSON.stringify(opts);
  return (nf[k] ||= new Intl.NumberFormat(locale(), opts));
}

export const num = (n, d = 0) => (n == null || Number.isNaN(n) ? "–" : fmtr("n", { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: "always" }).format(n));
export function eur(n, d = 0) {
  if (n == null || Number.isNaN(n)) return "–";
  return fmtr("c", { style: "currency", currency: "EUR", minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: "always" }).format(n);
}
export function signedEur(n, d = 0) {
  if (n == null || Number.isNaN(n)) return "–";
  const s = eur(Math.abs(n), d);
  return n < 0 ? `−${s}` : `+${s}`;
}
export const pct = (n, d = 1) => (n == null ? "–" : `${num(n, d)}%`);

export function parseDay(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}
export const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const todayIso = () => isoDay(new Date());

export function dateLabel(iso, withYear = true) {
  if (!iso) return "";
  return new Intl.DateTimeFormat(locale(), { day: "numeric", month: "short", ...(withYear ? { year: "numeric" } : {}) })
    .format(parseDay(iso)).replace(/\.$/, "");
}
/** Today / Yesterday, else "2 Mar". */
export function relativeDay(iso) {
  const today = todayIso();
  if (iso === today) return t("today");
  const y = new Date(); y.setDate(y.getDate() - 1);
  if (iso === isoDay(y)) return t("yesterday");
  return dateLabel(iso, iso.slice(0, 4) !== today.slice(0, 4)).replace(/\.$/, "");
}
export function monthLabel(ym, long = true) {
  const [y, m] = ym.split("-").map(Number);
  return new Intl.DateTimeFormat(locale(), long ? { month: "long", year: "numeric" } : { month: "short" }).format(new Date(y, m - 1, 1));
}
