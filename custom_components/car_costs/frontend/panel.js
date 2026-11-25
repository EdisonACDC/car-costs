/* "Costi Auto" panel for Home Assistant's side menu.
 *
 * Home Assistant gives this element `hass`. The glass app runs in a same-origin iframe and uses
 * `hass.fetchWithAuth` through this window, so there is no second login. The iframe follows
 * Home Assistant's light/dark theme and language. */

const APP = "/car_costs_static/app/index.html";

class CarCostsPanel extends HTMLElement {
  constructor() {
    super();
    this._narrow = false;
    this._hass = null;
    this.attachShadow({ mode: "open" }).innerHTML = `
      <style>
        :host{display:block;height:100%;background:var(--primary-background-color,#0c3b2e)}
        .wrap{display:flex;flex-direction:column;height:100%}
        .bar{display:none;align-items:center;gap:4px;height:var(--header-height,56px);padding:0 4px;flex:none;
          background:var(--app-header-background-color,var(--primary-color));color:var(--app-header-text-color,#fff);box-sizing:border-box}
        :host([narrow]) .bar{display:flex}
        .bar button{width:48px;height:48px;border:0;background:none;color:inherit;font-size:24px;cursor:pointer;border-radius:50%}
        .bar b{font-size:20px;font-weight:500}
        iframe{flex:1;width:100%;border:0;display:block;background:transparent;color-scheme:normal}
      </style>
      <div class="wrap">
        <div class="bar"><button aria-label="Menu" id="menu">☰</button><b>Costi Auto</b></div>
        <iframe title="Costi Auto" allow="camera; clipboard-write"></iframe>
      </div>`;
    this.shadowRoot.getElementById("menu").addEventListener("click", () =>
      this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true })));
    this._frame = this.shadowRoot.querySelector("iframe");
    this._frame.addEventListener("load", () => this._applyTheme());
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    window.__carCostsHass = hass;           // read by the app inside the iframe (same origin)
    if (first) this._frame.src = `${APP}?embed=1&${this._params()}`;
    this._applyTheme();
  }
  get hass() { return this._hass; }

  set narrow(value) { this._narrow = !!value; this.toggleAttribute("narrow", this._narrow); }
  get narrow() { return this._narrow; }
  set panel(_) {}
  set route(_) {}

  _dark() { return !!this._hass?.themes?.darkMode; }
  _params() {
    return new URLSearchParams({ theme: this._dark() ? "dark" : "light", lang: this._hass?.language || "" }).toString();
  }
  _applyTheme() {
    try {
      const doc = this._frame.contentDocument;
      if (doc?.documentElement) doc.documentElement.dataset.theme = this._dark() ? "dark" : "light";
    } catch { /* not loaded yet */ }
  }
}

if (!customElements.get("car-costs-panel")) customElements.define("car-costs-panel", CarCostsPanel);
