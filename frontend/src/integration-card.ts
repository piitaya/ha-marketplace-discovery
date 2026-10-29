import {
  mdiAccessPointNetwork,
  mdiBluetooth,
  mdiCheckCircle,
  mdiChevronDown,
  mdiChevronUp,
  mdiIpNetworkOutline,
  mdiPuzzleOutline,
  mdiRouterNetwork,
  mdiStar,
} from "@mdi/js";
import { css, html, LitElement, nothing, type TemplateResult } from "lit";
import { property, state } from "lit/decorators.js";
import { describeDevice, formatMatcher, SOURCE_LABELS } from "./format.ts";
import { countDevices, devicePreview, groupByRule, type IntegrationGroup, type RuleGroup, sourcesOf } from "./group.ts";
import { createLocalizer, type Localizer } from "./localize.ts";
import { navigate } from "./navigate.ts";
import { sharedStyles } from "./styles.ts";
import type { MatchResult, Source } from "./types.ts";

export const SOURCE_ICONS: Record<Source, string> = {
  bluetooth: mdiBluetooth,
  zeroconf: mdiAccessPointNetwork,
  dhcp: mdiIpNetworkOutline,
  ssdp: mdiRouterNetwork,
};

const DEVICE_LIMIT = 4;
const NARROW_DEVICE_LIMIT = 3;
const PREVIEW_LIMIT = 3;
const NARROW_PREVIEW_LIMIT = 2;

export class MpdIntegrationCard extends LitElement {
  @property({ attribute: false }) public group!: IntegrationGroup;

  @property({ attribute: false }) public localizer: Localizer = createLocalizer("en");

  @property({ type: Boolean, reflect: true }) public open = false;

  @property({ type: Boolean, reflect: true }) public narrow = false;

  @property({ type: Boolean, reflect: true }) public selecting = false;

  @property({ type: Boolean, reflect: true }) public selected = false;

  @property({ type: Boolean, reflect: true }) public ignored = false;

  @property({ type: Boolean }) public busy = false;

  @property({ attribute: false }) public logoUrl?: string;

  @state() private _showAll = new Set<string>();

  @state() private _failedLogo?: string;

  protected render(): TemplateResult {
    const { localize } = this.localizer;
    const group = this.group;
    return html`
      <article>
        <div class="top">
          ${
            this.selecting
              ? html`
                  <label class="select">
                    <input
                      type="checkbox"
                      .checked=${this.selected}
                      aria-label=${localize("card.select", { name: group.name })}
                      @change=${this._selectChanged}
                    />
                  </label>
                `
              : nothing
          }
          <button type="button" class="head" aria-expanded=${this.open ? "true" : "false"} @click=${this._toggle}>
            ${this.narrow ? this._renderNarrowHead() : this._renderWideHead()}
          </button>
        </div>
        ${this.open ? this._renderDetails() : nothing}
      </article>
    `;
  }

  private _renderWideHead(): TemplateResult {
    const group = this.group;
    return html`
      <span class="logo">${this._renderLogo()}</span>
      <span class="main">
        <span class="title">
          <span class="name">${group.name}</span>
          <span class="repo">${group.full_name}</span>
          ${this._renderBadges()}
        </span>
        <span class="preview">${this._preview(PREVIEW_LIMIT)}</span>
        ${this._renderMeta()}
      </span>
      ${this._renderChevron()}
    `;
  }

  private _renderNarrowHead(): TemplateResult {
    const group = this.group;
    return html`
      <span class="row">
        <span class="logo">${this._renderLogo()}</span>
        <span class="main">
          <span class="title"><span class="name">${group.name}</span>${this._renderBadges()}</span>
          <span class="repo">${group.full_name}</span>
        </span>
        ${this._renderChevron()}
      </span>
      <span class="preview">${this._preview(NARROW_PREVIEW_LIMIT)}</span>
      ${this._renderMeta()}
    `;
  }

  private _renderBadges(): TemplateResult {
    const { localize } = this.localizer;
    return html`
      ${
        this.group.installed
          ? html`<span class="badge installed"><ha-svg-icon .path=${mdiCheckCircle}></ha-svg-icon>${localize("card.installed")}</span>`
          : nothing
      }
      ${this.ignored ? html`<span class="badge">${localize("card.ignored")}</span>` : nothing}
    `;
  }

  private _renderChevron(): TemplateResult {
    return html`<span class="chevron"><ha-svg-icon .path=${this.open ? mdiChevronUp : mdiChevronDown}></ha-svg-icon></span>`;
  }

  private _renderMeta(): TemplateResult {
    const { localize, formatCompact, formatRelative } = this.localizer;
    const group = this.group;
    const updated = group.last_updated ? formatRelative(group.last_updated) : null;
    const separator = html`<span class="sep" aria-hidden="true">·</span>`;
    return html`
      <span class="meta">
        <span class="devices-count">${localize("card.devices", { count: countDevices(group.results) })}</span>
        ${separator}
        ${sourcesOf(group.results).map(
          (source) => html`<span class="pill"><ha-svg-icon .path=${SOURCE_ICONS[source]}></ha-svg-icon>${SOURCE_LABELS[source]}</span>`,
        )}
        ${
          group.stars !== null
            ? html`${separator}<span class="stars">
                  <ha-svg-icon .path=${mdiStar}></ha-svg-icon>
                  <span>${formatCompact(group.stars)}<span class="visually-hidden"> ${localize("card.stars", { count: group.stars })}</span></span>
                </span>`
            : nothing
        }
        ${updated ? html`${separator}<span>${localize("card.updated", { time: updated })}</span>` : nothing}
      </span>
    `;
  }

  private _preview(limit: number): string {
    const { localize } = this.localizer;
    const parts = devicePreview(this.group.results).map((entry) => {
      const name = entry.name ?? localize("card.unknown_device");
      return entry.count > 1 ? `${name} (${entry.count})` : name;
    });
    const list = parts.slice(0, limit).join(", ");
    return parts.length > limit ? localize("card.more", { list, count: parts.length - limit }) : list;
  }

  private _renderLogo(): TemplateResult | typeof nothing {
    if (!this.logoUrl) {
      return nothing;
    }
    if (this._failedLogo === this.logoUrl) {
      return html`<ha-svg-icon class="logo-fallback" .path=${mdiPuzzleOutline}></ha-svg-icon>`;
    }
    return html`<img src=${this.logoUrl} alt="" loading="lazy" referrerpolicy="no-referrer" @error=${this._logoError} />`;
  }

  private _renderDetails(): TemplateResult {
    const { localize } = this.localizer;
    const description = this.group.description?.trim();
    return html`
      ${description ? html`<p class="description">${description}</p>` : nothing}
      ${groupByRule(this.group.results).map((rule) => this._renderRule(rule))}
      <div class="footer">
        <ha-button
          appearance=${this.narrow ? "outlined" : "plain"}
          variant=${this.narrow ? "neutral" : "brand"}
          .disabled=${this.busy}
          @click=${this._toggleIgnore}
        >
          ${localize(this.ignored ? "card.stop_ignoring" : "card.ignore")}
        </ha-button>
        <ha-button class="open" appearance="filled" @click=${this._openInMarketplace}>${localize("card.open")}</ha-button>
      </div>
    `;
  }

  private _renderRule(rule: RuleGroup): TemplateResult {
    const { localize } = this.localizer;
    const limit = this.narrow ? NARROW_DEVICE_LIMIT : DEVICE_LIMIT;
    const hasMore = rule.results.length > limit;
    const showAll = this._showAll.has(rule.key);
    const shown = hasMore && !showAll ? rule.results.slice(0, limit) : rule.results;
    const count = rule.results.length;
    return html`
      <section class="rule">
        <div class="matched">
          <span class="matched-label">${localize("card.matched_by")}</span>
          ${rule.matchers.map((matcher) => html`<code>${formatMatcher(rule.source, matcher)}</code>`)}
        </div>
        <ul class="devices">
          ${shown.map((result) => this._renderDevice(result))}
        </ul>
        ${
          hasMore
            ? html`
                <button
                  type="button"
                  class="more"
                  .value=${rule.key}
                  aria-expanded=${showAll ? "true" : "false"}
                  @click=${this._toggleShowAll}
                >
                  <ha-svg-icon .path=${showAll ? mdiChevronUp : mdiChevronDown}></ha-svg-icon>
                  ${
                    showAll
                      ? localize("card.show_less")
                      : localize(this.narrow ? "card.show_all_short" : "card.show_all", { count })
                  }
                </button>
              `
            : nothing
        }
      </section>
    `;
  }

  private _renderDevice(result: MatchResult): TemplateResult {
    const { name, details } = describeDevice(result);
    return html`
      <li>
        <span class="device-icon"><ha-svg-icon .path=${SOURCE_ICONS[result.source]}></ha-svg-icon></span>
        <span class="device-text">
          <span class="device-name">${name ?? this.localizer.localize("card.unknown_device")}</span>
          ${details.length ? html`<span class="device-detail">${details.join(" · ")}</span>` : nothing}
        </span>
      </li>
    `;
  }

  public override focus(options?: FocusOptions): void {
    this.renderRoot.querySelector<HTMLElement>(this.selecting ? ".select input" : ".head")?.focus(options);
  }

  private _logoError(): void {
    this._failedLogo = this.logoUrl;
  }

  private _toggle(): void {
    this.dispatchEvent(new CustomEvent("mpd-toggle", { detail: { open: !this.open } }));
  }

  private _selectChanged(ev: Event): void {
    const selected = (ev.target as HTMLInputElement).checked;
    this.dispatchEvent(new CustomEvent("mpd-select", { detail: { selected } }));
  }

  private _toggleIgnore(): void {
    if (this.busy) {
      return;
    }
    this.dispatchEvent(new CustomEvent("mpd-ignore", { detail: { ignored: !this.ignored } }));
  }

  private _toggleShowAll(ev: Event): void {
    const key = (ev.currentTarget as HTMLButtonElement).value;
    const showAll = new Set(this._showAll);
    if (showAll.has(key)) {
      showAll.delete(key);
    } else {
      showAll.add(key);
    }
    this._showAll = showAll;
  }

  private _openInMarketplace(): void {
    navigate(`/marketplace/repository/${encodeURIComponent(this.group.repository_id)}`);
  }

  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
        font-size: var(--ha-font-size-m, 14px);
        line-height: 1.43;
      }
      article {
        overflow: hidden;
        background: var(--ha-card-background, var(--card-background-color, #ffffff));
        border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e3e3e3));
        border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
      }
      :host([selected]) article {
        border-color: var(--primary-color, #009ac7);
        box-shadow: 0 0 0 1px var(--primary-color, #009ac7);
      }
      :host([ignored]) article {
        opacity: 0.6;
      }
      button {
        font: inherit;
        cursor: pointer;
      }
      button:focus-visible,
      input:focus-visible {
        outline: 2px solid var(--primary-color, #009ac7);
        outline-offset: 2px;
      }
      .top {
        display: flex;
        align-items: stretch;
      }
      .select {
        display: flex;
        align-items: center;
        padding-inline-start: var(--ha-space-5, 20px);
        cursor: pointer;
      }
      :host([narrow]) .select {
        align-items: flex-start;
        padding: 26px 0 0 var(--ha-space-4, 16px);
      }
      .select input {
        width: 20px;
        height: 20px;
        margin: 0;
        accent-color: var(--primary-color, #009ac7);
        cursor: pointer;
      }
      .head {
        display: flex;
        align-items: center;
        gap: var(--ha-space-4, 16px);
        box-sizing: border-box;
        width: 100%;
        min-width: 0;
        padding: var(--ha-space-4, 16px) var(--ha-space-5, 20px);
        border: none;
        background: transparent;
        color: inherit;
        text-align: start;
      }
      .head:focus-visible {
        outline-offset: -2px;
      }
      .head:hover {
        background: color-mix(in srgb, var(--primary-text-color, #141414) 3%, transparent);
      }
      :host([narrow]) .head {
        flex-direction: column;
        align-items: stretch;
        gap: var(--ha-space-2, 8px);
        padding: var(--ha-space-4, 16px);
      }
      .row {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .logo {
        display: flex;
        align-items: center;
        justify-content: center;
        flex: none;
        box-sizing: border-box;
        width: 48px;
        height: 48px;
        border-radius: var(--ha-border-radius-lg, 12px);
        border: 1px solid var(--divider-color, #ececec);
        background: var(--card-background-color, #ffffff);
        color: var(--secondary-text-color, #5e5e5e);
        --mdc-icon-size: 28px;
      }
      :host([narrow]) .logo {
        width: 44px;
        height: 44px;
      }
      .logo img {
        width: 36px;
        height: 36px;
        object-fit: contain;
      }
      :host([narrow]) .logo img {
        width: 32px;
        height: 32px;
      }
      .main {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-1, 4px);
        flex: 1;
        min-width: 0;
      }
      :host([narrow]) .main {
        gap: 0;
      }
      .title {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        column-gap: var(--ha-space-2, 8px);
      }
      :host([narrow]) .title {
        align-items: center;
        gap: 6px;
      }
      .name {
        font-size: var(--ha-font-size-l, 16px);
        font-weight: var(--ha-font-weight-medium, 500);
      }
      .repo {
        font-size: var(--ha-font-size-s, 12px);
        color: var(--secondary-text-color, #5e5e5e);
        overflow-wrap: anywhere;
      }
      :host([narrow]) .repo {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .badge {
        align-self: center;
        display: inline-flex;
        align-items: center;
        gap: var(--ha-space-1, 4px);
        box-sizing: border-box;
        height: 22px;
        padding: 0 var(--ha-space-2, 8px);
        border-radius: var(--ha-border-radius-pill, 9999px);
        background: var(--ha-color-fill-neutral-normal-resting, #ececec);
        color: var(--ha-color-on-neutral-normal, #3d3d3d);
        font-size: var(--ha-font-size-s, 12px);
        font-weight: var(--ha-font-weight-medium, 500);
        white-space: nowrap;
        --mdc-icon-size: 14px;
      }
      .badge.installed {
        background: var(--ha-color-fill-success-normal-resting, #dcf2dc);
        color: var(--ha-color-on-success-normal, #1e6b28);
      }
      .preview {
        display: block;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .meta {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        font-size: var(--ha-font-size-s, 12px);
        color: var(--secondary-text-color, #5e5e5e);
      }
      :host([narrow]) .meta {
        gap: 4px 8px;
      }
      :host([narrow]) .meta .sep {
        display: none;
      }
      .devices-count {
        font-weight: var(--ha-font-weight-medium, 500);
        color: var(--primary-text-color, #141414);
      }
      .pill {
        display: inline-flex;
        align-items: center;
        gap: var(--ha-space-1, 4px);
        height: 22px;
        padding: 0 var(--ha-space-2, 8px);
        border-radius: var(--ha-border-radius-pill, 9999px);
        background: var(--ha-color-fill-neutral-quiet-resting, #f2f2f2);
        color: var(--ha-color-on-neutral-normal, #3d3d3d);
        --mdc-icon-size: 14px;
      }
      .stars {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        --mdc-icon-size: 14px;
      }
      .stars ha-svg-icon {
        color: var(--mpd-star-color, #b27a00);
      }
      .chevron {
        display: flex;
        align-items: center;
        justify-content: center;
        flex: none;
        width: 40px;
        height: 40px;
        margin-inline-end: -8px;
        color: var(--ha-color-on-neutral-normal, #3d3d3d);
      }
      .description {
        margin: 0;
        padding: 12px var(--ha-space-5, 20px);
        border-top: 1px solid var(--divider-color, #ececec);
        color: var(--secondary-text-color, #5e5e5e);
      }
      :host([narrow]) .description {
        padding: 12px var(--ha-space-4, 16px);
      }
      .rule {
        padding: 12px var(--ha-space-5, 20px) var(--ha-space-2, 8px);
        border-top: 1px solid var(--divider-color, #ececec);
      }
      :host([narrow]) .rule {
        padding: 12px var(--ha-space-4, 16px) var(--ha-space-2, 8px);
      }
      .matched {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--ha-space-2, 8px);
        min-width: 0;
      }
      :host([narrow]) .matched {
        display: block;
      }
      .matched-label {
        font-size: var(--ha-font-size-s, 12px);
        color: var(--secondary-text-color, #5e5e5e);
      }
      :host([narrow]) .matched-label {
        display: block;
      }
      code {
        font-family: var(--ha-font-family-code, "Roboto Mono", monospace);
        font-size: var(--ha-font-size-s, 12px);
        padding: 2px var(--ha-space-2, 8px);
        border-radius: 6px;
        background: var(--ha-color-fill-neutral-quiet-resting, #f2f2f2);
        color: var(--primary-text-color, #141414);
        overflow-wrap: anywhere;
      }
      :host([narrow]) code {
        display: inline-block;
        margin: var(--ha-space-1, 4px) var(--ha-space-1, 4px) 0 0;
      }
      .devices {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        column-gap: var(--ha-space-6, 24px);
        margin: var(--ha-space-1, 4px) 0 0;
        padding: 0;
        list-style: none;
      }
      :host([narrow]) .devices {
        grid-template-columns: minmax(0, 1fr);
      }
      .devices li {
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 0;
        padding: var(--ha-space-2, 8px) 0;
      }
      .device-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        flex: none;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--ha-color-fill-primary-quiet-resting, #eff9fe);
        color: var(--mpd-primary-text, #00799f);
        --mdc-icon-size: 18px;
      }
      .device-text {
        display: flex;
        flex-direction: column;
        min-width: 0;
      }
      .device-name,
      .device-detail {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .device-detail {
        font-family: var(--ha-font-family-code, "Roboto Mono", monospace);
        font-size: var(--ha-font-size-s, 12px);
        color: var(--secondary-text-color, #5e5e5e);
      }
      .more {
        display: inline-flex;
        align-items: center;
        gap: var(--ha-space-1, 4px);
        height: 32px;
        margin: 0 0 var(--ha-space-1, 4px) -8px;
        padding: 0 var(--ha-space-2, 8px);
        border: none;
        border-radius: var(--ha-border-radius-pill, 9999px);
        background: transparent;
        color: var(--mpd-primary-text, #00799f);
        font-weight: var(--ha-font-weight-medium, 500);
        --mdc-icon-size: 18px;
      }
      :host([narrow]) .more {
        height: auto;
        min-height: 44px;
        margin: 0 0 0 -8px;
      }
      .more:hover {
        background: var(--ha-color-fill-primary-quiet-resting, #eff9fe);
      }
      .footer {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: var(--ha-space-2, 8px);
        padding: 12px var(--ha-space-5, 20px);
        border-top: 1px solid var(--divider-color, #ececec);
      }
      :host([narrow]) .footer {
        justify-content: flex-start;
        padding: 12px var(--ha-space-4, 16px);
      }
      .footer ha-button {
        --ha-button-height: 36px;
      }
      :host([narrow]) .footer ha-button {
        --ha-button-height: 40px;
      }
      .footer ha-button[appearance="plain"] {
        --wa-color-brand-on-normal: var(--mpd-primary-text, #00799f);
      }
      .footer .open {
        --wa-color-brand-on-normal: var(--mpd-on-primary-fill, #00577a);
      }
    `,
  ];
}

if (!customElements.get("mpd-integration-card")) {
  customElements.define("mpd-integration-card", MpdIntegrationCard);
}
