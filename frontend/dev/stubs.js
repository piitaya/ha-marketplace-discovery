const define = (name, element) => {
  if (!customElements.get(name)) {
    customElements.define(name, element);
  }
};

define(
  "ha-svg-icon",
  class extends HTMLElement {
    set path(value) {
      this._path = value;
      this.innerHTML = `<svg viewBox="0 0 24 24" width="100%" height="100%" fill="currentColor"><path d="${value}"></path></svg>`;
    }
    get path() {
      return this._path;
    }
    connectedCallback() {
      this.style.cssText = "display:inline-flex;width:var(--mdc-icon-size,24px);height:var(--mdc-icon-size,24px)";
    }
  },
);

define(
  "ha-spinner",
  class extends HTMLElement {
    connectedCallback() {
      const size = { tiny: 16, small: 28, medium: 48, large: 68 }[this.getAttribute("size")] ?? 48;
      this.style.cssText = `display:inline-block;width:${size}px;height:${size}px;border:3px solid var(--divider-color);border-top-color:var(--primary-color);border-radius:50%;box-sizing:border-box;animation:spin 1s linear infinite`;
    }
  },
);

define(
  "ha-button",
  class extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" }).innerHTML = `<style>
        button{display:inline-flex;align-items:center;gap:6px;height:var(--ha-button-height,40px);padding:0 16px;border-radius:9999px;border:none;font:inherit;font-weight:500;cursor:pointer;background:var(--primary-color);color:#fff}
        :host([appearance=plain]) button{background:none;color:var(--primary-color)}
        :host([size=s]) button{height:32px;padding:0 12px}
        button:disabled{opacity:.5;cursor:default}
        ::slotted(*){--mdc-icon-size:18px}
      </style><button part="base"><slot name="start"></slot><slot></slot></button>`;
      this._button = this.shadowRoot.querySelector("button");
    }
    set disabled(value) {
      this._button.disabled = Boolean(value);
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
    _render() {
      this.innerHTML = `<button aria-label="${this._label ?? ""}" style="width:48px;height:48px;border:none;background:none;color:inherit;cursor:pointer"><ha-svg-icon></ha-svg-icon></button>`;
      this.querySelector("ha-svg-icon").path = this._path ?? "";
    }
  },
);
