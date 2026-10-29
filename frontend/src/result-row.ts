import { mdiAccessPointNetwork, mdiBluetooth, mdiCheckCircle, mdiIpNetworkOutline, mdiOpenInNew, mdiRouterNetwork } from "@mdi/js";
import { css, html, LitElement, type TemplateResult } from "lit";
import { property } from "lit/decorators.js";
import { describeDevice, formatMatcher, SOURCE_LABELS } from "./format.ts";
import { navigate } from "./navigate.ts";
import { buildReportUrl } from "./report.ts";
import { sharedStyles } from "./styles.ts";
import type { MatchResult, Source } from "./types.ts";

const SOURCE_ICONS: Record<Source, string> = {
  bluetooth: mdiBluetooth,
  zeroconf: mdiAccessPointNetwork,
  dhcp: mdiIpNetworkOutline,
  ssdp: mdiRouterNetwork,
};

export class MpdResultRow extends LitElement {
  @property({ attribute: false }) public result!: MatchResult;

  @property({ attribute: false }) public haVersion = "";

  @property({ type: Boolean, reflect: true }) public narrow = false;

  protected render(): TemplateResult {
    const result = this.result;
    const device = describeDevice(result.device);
    const sourceLabel = SOURCE_LABELS[result.source] ?? result.source;
    return html`
      <div class="source" title=${sourceLabel}>
        <ha-svg-icon .path=${SOURCE_ICONS[result.source] ?? mdiAccessPointNetwork}></ha-svg-icon>
      </div>
      <div class="info">
        <div class="title">
          <span class="name">${result.name}</span>
          <span class="full-name">${result.full_name}</span>
        </div>
        <div class="device">
          <span class="visually-hidden">${sourceLabel} device:</span>
          <span class="device-name">${device.name}</span>
          ${device.address ? html`<span class="address">${device.address}</span>` : ""}
        </div>
        <ul class="matchers" aria-label="Matched by">
          ${result.matchers.map((matcher) => html`<li><code>${formatMatcher(result.source, matcher)}</code></li>`)}
        </ul>
      </div>
      <div class="actions">
        ${
          result.installed
            ? html`<span class="badge"><ha-svg-icon .path=${mdiCheckCircle}></ha-svg-icon>Installed</span>`
            : html`<ha-button size="s" appearance="filled" @click=${this._openInMarketplace}>Open in marketplace</ha-button>`
        }
        <a class="report" href=${buildReportUrl(result, this.haVersion)} target="_blank" rel="noopener noreferrer">
          Report false positive<ha-svg-icon .path=${mdiOpenInNew}></ha-svg-icon><span class="visually-hidden">(opens in a new tab)</span>
        </a>
      </div>
    `;
  }

  private _openInMarketplace(): void {
    navigate(`/marketplace/repository/${encodeURIComponent(this.result.repository_id)}`);
  }

  static styles = [
    sharedStyles,
    css`
      :host {
        display: flex;
        align-items: flex-start;
        gap: var(--ha-space-4, 16px);
        padding: var(--ha-space-4, 16px);
      }
      :host([narrow]) {
        flex-wrap: wrap;
        gap: var(--ha-space-3, 12px);
      }
      .source {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border-radius: var(--ha-border-radius-circle, 50%);
        background-color: var(--secondary-background-color, #f2f2f2);
        color: var(--secondary-text-color, #5e5e5e);
        flex: none;
      }
      .info {
        flex: 1;
        min-width: 0;
      }
      .title {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        column-gap: var(--ha-space-2, 8px);
      }
      .name {
        font-size: var(--ha-font-size-l, 16px);
        font-weight: var(--ha-font-weight-medium, 500);
        line-height: var(--ha-line-height-condensed, 1.2);
      }
      .full-name,
      .address {
        color: var(--secondary-text-color, #5e5e5e);
        font-size: var(--ha-font-size-s, 12px);
        overflow-wrap: anywhere;
      }
      .device {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        column-gap: var(--ha-space-2, 8px);
        margin-top: var(--ha-space-1, 4px);
        font-size: var(--ha-font-size-m, 14px);
        overflow-wrap: anywhere;
      }
      .matchers {
        display: flex;
        flex-wrap: wrap;
        gap: var(--ha-space-1, 4px);
        list-style: none;
        margin: var(--ha-space-2, 8px) 0 0;
        padding: 0;
      }
      code {
        display: inline-block;
        font-family: var(--ha-font-family-code, ui-monospace, monospace);
        font-size: var(--ha-font-size-s, 12px);
        padding: 2px var(--ha-space-2, 8px);
        border-radius: var(--ha-border-radius-sm, 4px);
        background-color: var(--secondary-background-color, #f2f2f2);
        color: var(--primary-text-color, #141414);
        overflow-wrap: anywhere;
      }
      .actions {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: var(--ha-space-2, 8px);
        flex: none;
      }
      :host([narrow]) .actions {
        flex-direction: row;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        padding-inline-start: calc(40px + var(--ha-space-3, 12px));
        box-sizing: border-box;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: var(--ha-space-1, 4px);
        height: 32px;
        padding: 0 var(--ha-space-3, 12px);
        border-radius: var(--ha-border-radius-pill, 9999px);
        font-size: var(--ha-font-size-m, 14px);
        font-weight: var(--ha-font-weight-medium, 500);
        color: var(--ha-color-on-success-normal, var(--success-color, #43a047));
        background-color: var(
          --ha-color-fill-success-normal-resting,
          color-mix(in srgb, var(--success-color, #43a047) 15%, transparent)
        );
        --mdc-icon-size: 18px;
      }
      .report {
        display: inline-flex;
        align-items: center;
        gap: var(--ha-space-1, 4px);
        font-size: var(--ha-font-size-s, 12px);
        color: var(--primary-color, #009ac7);
        text-decoration: none;
        --mdc-icon-size: 14px;
      }
      .report:hover {
        text-decoration: underline;
      }
      .report:focus-visible {
        outline: 2px solid var(--primary-color, #009ac7);
        outline-offset: 2px;
        border-radius: var(--ha-border-radius-sm, 4px);
      }
    `,
  ];
}

if (!customElements.get("mpd-result-row")) {
  customElements.define("mpd-result-row", MpdResultRow);
}
