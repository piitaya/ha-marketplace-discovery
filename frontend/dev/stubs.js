const define = (name, element) => {
  if (!customElements.get(name)) {
    customElements.define(name, element);
  }
};

const BRANDS_PATH = /^\/api\/brands\/marketplace\/([^/]+)\/((?:dark_)?icon\.png)\?/;
const setAttribute = Element.prototype.setAttribute;
Element.prototype.setAttribute = function (name, value) {
  if (this instanceof HTMLImageElement && name === "src") {
    const match = BRANDS_PATH.exec(String(value));
    if (match) {
      value = `https://brands.home-assistant.io/_/${match[1]}/${match[2]}`;
    }
  }
  return setAttribute.call(this, name, value);
};

define(
  "ha-svg-icon",
  class extends HTMLElement {
    set path(value) {
      this._path = value;
      this.innerHTML = `<svg viewBox="0 0 24 24" width="100%" height="100%" fill="currentColor" aria-hidden="true"><path d="${value}"></path></svg>`;
    }
    get path() {
      return this._path;
    }
    connectedCallback() {
      this.style.cssText =
        "display:inline-flex;flex:none;width:var(--mdc-icon-size,24px);height:var(--mdc-icon-size,24px)";
    }
  },
);

define(
  "ha-spinner",
  class extends HTMLElement {
    connectedCallback() {
      const size = { tiny: 16, small: 28, medium: 48, large: 68 }[this.getAttribute("size")];
      if (size) {
        this.style.setProperty("--ha-spinner-size", `${size}px`);
      }
      this.style.cssText += `;display:inline-block;flex:none;width:var(--ha-spinner-size,48px);height:var(--ha-spinner-size,48px);border:calc(var(--ha-spinner-size,48px) / 10 + 1px) solid var(--ha-spinner-divider-color,var(--divider-color));border-top-color:var(--ha-spinner-indicator-color,var(--primary-color));border-radius:50%;box-sizing:border-box;animation:spin 1s linear infinite`;
    }
  },
);

define(
  "ha-button",
  class extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" }).innerHTML = `<style>
        :host{display:inline-block;--on:var(--wa-color-brand-on-normal,var(--ha-color-on-primary-normal,#009ac7))}
        button{display:inline-flex;align-items:center;justify-content:center;gap:4px;width:100%;height:var(--ha-button-height,40px);padding:0 16px;border-radius:9999px;border:1px solid transparent;box-sizing:border-box;font:inherit;font-weight:500;cursor:pointer;white-space:nowrap;background:var(--primary-color);color:var(--ha-color-on-primary-loud,#fff)}
        button.has-start{padding-inline-start:12px}
        :host([appearance=filled]) button{background:var(--ha-color-fill-primary-normal-resting,#dff3fc);color:var(--on)}
        :host([appearance=plain]) button{background:none;color:var(--on)}
        :host([appearance=outlined]) button{background:none;color:var(--on);border-color:var(--ha-color-border-primary-normal,#7bd4fb)}
        :host([variant=neutral][appearance=outlined]) button{color:var(--primary-text-color);border-color:var(--ha-color-border-neutral-normal,#989898)}
        :host([variant=neutral][appearance=plain]) button{color:var(--primary-text-color)}
        :host([disabled]) button{cursor:default;background:var(--ha-color-fill-disabled-normal-resting,#f3f3f3);color:var(--ha-color-on-disabled-normal,#b1b1b1);border-color:transparent}
        :host([disabled][appearance=plain]) button{background:none}
        ::slotted([slot=start]){margin-inline-end:4px}
      </style><button part="base"><slot name="start"></slot><slot></slot></button>`;
      this._button = this.shadowRoot.querySelector("button");
      const start = this.shadowRoot.querySelector("slot[name=start]");
      start.addEventListener("slotchange", () =>
        this._button.classList.toggle("has-start", start.assignedElements().length > 0),
      );
    }
    set disabled(value) {
      this._button.disabled = Boolean(value);
      this.toggleAttribute("disabled", Boolean(value));
    }
    get disabled() {
      return this._button.disabled;
    }
  },
);

define(
  "ha-icon-button",
  class extends HTMLElement {
    set path(value) {
      this._path = value;
      this._render();
    }
    set label(value) {
      this._label = value;
      this._render();
    }
    focus(options) {
      this.querySelector("button")?.focus(options);
    }
    _render() {
      this.style.display = "inline-flex";
      this.innerHTML = `<button aria-label="${this._label ?? ""}" style="display:flex;align-items:center;justify-content:center;width:var(--ha-icon-button-size,48px);height:var(--ha-icon-button-size,48px);border:none;border-radius:50%;background:none;color:inherit;cursor:pointer"><ha-svg-icon></ha-svg-icon></button>`;
      this.querySelector("ha-svg-icon").path = this._path ?? "";
    }
  },
);
