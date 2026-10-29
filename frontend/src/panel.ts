import { mdiAlertCircleOutline, mdiCheck, mdiInformationOutline, mdiMagnify, mdiMenu, mdiRefresh } from "@mdi/js";
import { css, html, LitElement, nothing, type PropertyValues, type TemplateResult } from "lit";
import { property, state } from "lit/decorators.js";
import { matchesFilter, SOURCE_LABELS, SOURCES } from "./format.ts";
import "./result-row.ts";
import { sharedStyles } from "./styles.ts";
import type { HomeAssistant, MatchesResponse, MatchResult, PanelInfo, Route, Source } from "./types.ts";

const REFRESH_SECONDS = 10;

type SearchMode = "search" | "refresh";

interface ErrorLike {
  code?: string;
  message?: string;
}

const errorMessage = (err: unknown): string => {
  const { code, message } = (typeof err === "object" && err !== null ? err : {}) as ErrorLike;
  if (code === "not_loaded") {
    return "Marketplace discovery is not loaded. Check the integration on the integrations page.";
  }
  return message || (typeof err === "string" ? err : "Unknown error, check the Home Assistant logs");
};

export class MarketplaceDiscoveryPanel extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;

  @property({ type: Boolean, reflect: true }) public narrow = false;

  @property({ attribute: false }) public route?: Route;

  @property({ attribute: false }) public panel?: PanelInfo;

  @state() private _response?: MatchesResponse;

  @state() private _loading?: SearchMode;

  @state() private _error?: string;

  @state() private _filter = "";

  @state() private _selectedSources = new Set<Source>();

  @state() private _showInstalled = false;

  private _requestId = 0;

  protected shouldUpdate(changedProps: PropertyValues<this>): boolean {
    if (changedProps.size !== 1 || !changedProps.has("hass")) {
      return true;
    }
    const oldHass = changedProps.get("hass") as HomeAssistant | undefined;
    return (
      !oldHass ||
      oldHass.config?.version !== this.hass.config?.version ||
      oldHass.kioskMode !== this.hass.kioskMode ||
      oldHass.dockedSidebar !== this.hass.dockedSidebar ||
      oldHass.locale?.language !== this.hass.locale?.language
    );
  }

  protected render(): TemplateResult {
    return html`
      <div class="header">
        ${
          this._showMenuButton()
            ? html`<ha-icon-button .path=${mdiMenu} .label=${"Sidebar toggle"} @click=${this._toggleMenu}></ha-icon-button>`
            : nothing
        }
        <h1 class="main-title">Marketplace discovery</h1>
      </div>
      <div class="content">
        <p class="intro">
          Finds devices on your network that a marketplace integration says it supports. Matches come from the
          discovery info in each integration's manifest, so check the integration before you install it.
        </p>
        <div class="search-buttons">
          <ha-button appearance="filled" .disabled=${this._loading !== undefined} @click=${this._search}>
            ${this._buttonIcon("search", mdiMagnify)} Search
          </ha-button>
          <ha-button appearance="plain" .disabled=${this._loading !== undefined} @click=${this._searchWithRefresh}>
            ${this._buttonIcon("refresh", mdiRefresh)} Search with refresh
          </ha-button>
          <span class="hint">
            Search with refresh first asks devices to announce themselves again. It takes about ${REFRESH_SECONDS}
            seconds.
          </span>
        </div>
        ${this._renderBody()}
      </div>
    `;
  }

  private _buttonIcon(mode: SearchMode, path: string): TemplateResult {
    return this._loading === mode
      ? html`<ha-spinner slot="start" size="tiny" aria-hidden="true"></ha-spinner>`
      : html`<ha-svg-icon slot="start" .path=${path}></ha-svg-icon>`;
  }

  private _renderBody(): TemplateResult | typeof nothing {
    if (this._loading) {
      return html`
        <div class="state" role="status">
          <ha-spinner size="medium"></ha-spinner>
          <p>
            ${
              this._loading === "refresh"
                ? `Asking devices to announce themselves. This takes about ${REFRESH_SECONDS} seconds.`
                : "Searching"
            }
          </p>
        </div>
      `;
    }
    if (this._error) {
      return this._renderAlert("error", "Search failed", this._error);
    }
    const response = this._response;
    if (!response) {
      return html`
        <div class="state">
          <p>Select Search to look for devices that a marketplace integration supports.</p>
        </div>
      `;
    }
    if (!response.dataset) {
      return this._renderAlert(
        "warning",
        "List of marketplace integrations not available",
        "The list is downloaded when Home Assistant can reach the internet. Try again later.",
      );
    }
    return html`
      ${this._renderSummary(response)}
      ${response.results.length ? this._renderResults(response.results) : this._renderEmpty()}
    `;
  }

  private _renderAlert(type: "error" | "warning" | "info", title: string, text: string): TemplateResult {
    return html`
      <div class="alert ${type}" role=${type === "error" ? "alert" : "status"}>
        <ha-svg-icon .path=${type === "info" ? mdiInformationOutline : mdiAlertCircleOutline}></ha-svg-icon>
        <div>
          <div class="alert-title">${title}</div>
          <div>${text}</div>
        </div>
      </div>
    `;
  }

  private _renderSummary(response: MatchesResponse): TemplateResult {
    const dataset = response.dataset!;
    const skipped = SOURCES.filter((source) => response.sources?.[source] === false);
    const generated = this._formatDate(dataset.generated_at);
    return html`
      <p class="summary">
        Compared with ${dataset.integrations} marketplace integrations that have discovery info${
          generated ? `, list from ${generated}` : ""
        }.
      </p>
      ${
        skipped.length
          ? this._renderAlert(
              "info",
              "Some sources were not searched",
              `${skipped.map((source) => SOURCE_LABELS[source]).join(", ")} ${
                skipped.length === 1 ? "is" : "are"
              } not set up in Home Assistant.`,
            )
          : nothing
      }
    `;
  }

  private _renderEmpty(): TemplateResult {
    return html`
      <div class="state">
        <p>No devices found that a marketplace integration supports.</p>
      </div>
    `;
  }

  private _renderResults(results: MatchResult[]): TemplateResult {
    const installedCount = results.filter((result) => result.installed).length;
    const base = results.filter(
      (result) => (this._showInstalled || !result.installed) && matchesFilter(result, this._filter),
    );
    const counts = new Map<Source, number>(SOURCES.map((source) => [source, 0]));
    for (const result of base) {
      counts.set(result.source, (counts.get(result.source) ?? 0) + 1);
    }
    const shown = this._selectedSources.size
      ? base.filter((result) => this._selectedSources.has(result.source))
      : base;
    const version = this.hass?.config?.version ?? "unknown";

    return html`
      <div class="filters">
        <label class="search">
          <ha-svg-icon .path=${mdiMagnify}></ha-svg-icon>
          <span class="visually-hidden">Search matches</span>
          <input
            type="search"
            name="filter"
            placeholder="Search ${results.length} ${results.length === 1 ? "match" : "matches"}"
            .value=${this._filter}
            @input=${this._filterChanged}
          />
        </label>
        <div class="chips" role="group" aria-label="Source">
          ${SOURCES.map((source) => {
            const selected = this._selectedSources.has(source);
            return html`
              <button
                class="chip"
                type="button"
                aria-pressed=${selected ? "true" : "false"}
                .value=${source}
                @click=${this._toggleSource}
              >
                ${selected ? html`<ha-svg-icon .path=${mdiCheck}></ha-svg-icon>` : nothing}
                ${SOURCE_LABELS[source]} <span class="count">${counts.get(source)}</span>
              </button>
            `;
          })}
        </div>
        <label class="installed-toggle">
          <input type="checkbox" name="show-installed" .checked=${this._showInstalled} @change=${this._installedChanged} />
          Show installed (${installedCount})
        </label>
      </div>
      ${
        shown.length
          ? html`
              <ul class="results" aria-label="Matches">
                ${shown.map(
                  (result) => html`
                    <li>
                      <mpd-result-row .result=${result} .haVersion=${version} .narrow=${this.narrow}></mpd-result-row>
                    </li>
                  `,
                )}
              </ul>
            `
          : html`<div class="state"><p>No matches for this search and these filters.</p></div>`
      }
    `;
  }

  private _formatDate(value: string): string | null {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return null;
    }
    try {
      return date.toLocaleDateString(this.hass?.locale?.language ?? this.hass?.language, { dateStyle: "medium" });
    } catch {
      return date.toLocaleDateString();
    }
  }

  private _showMenuButton(): boolean {
    const hass = this.hass;
    if (!hass || hass.kioskMode || hass.auth?.external?.config?.hasSidebar === true) {
      return false;
    }
    return this.narrow || hass.dockedSidebar === "always_hidden";
  }

  private _toggleMenu(): void {
    this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
  }

  private _search(): void {
    this._runSearch("search");
  }

  private _searchWithRefresh(): void {
    this._runSearch("refresh");
  }

  private async _runSearch(mode: SearchMode): Promise<void> {
    const requestId = ++this._requestId;
    this._loading = mode;
    this._error = undefined;
    try {
      const response = await this.hass.callWS<MatchesResponse>({
        type: "marketplace_discovery/matches",
        refresh: mode === "refresh",
      });
      if (requestId !== this._requestId) {
        return;
      }
      this._response = { ...response, results: response.results ?? [] };
    } catch (err) {
      if (requestId !== this._requestId) {
        return;
      }
      this._response = undefined;
      this._error = errorMessage(err);
    } finally {
      if (requestId === this._requestId) {
        this._loading = undefined;
      }
    }
  }

  private _filterChanged(ev: InputEvent): void {
    this._filter = (ev.target as HTMLInputElement).value;
  }

  private _toggleSource(ev: Event): void {
    const source = (ev.currentTarget as HTMLButtonElement).value as Source;
    const selected = new Set(this._selectedSources);
    if (selected.has(source)) {
      selected.delete(source);
    } else {
      selected.add(source);
    }
    this._selectedSources = selected;
  }

  private _installedChanged(ev: Event): void {
    this._showInstalled = (ev.target as HTMLInputElement).checked;
  }

  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
        min-height: 100%;
        background-color: var(--primary-background-color, #fafafa);
      }
      .header {
        position: sticky;
        top: 0;
        z-index: 4;
        display: flex;
        align-items: center;
        gap: var(--ha-space-1, 4px);
        box-sizing: border-box;
        height: var(--header-height, 56px);
        padding: 0 var(--ha-space-1, 4px);
        background-color: var(--app-header-background-color, var(--primary-background-color, #fafafa));
        color: var(--app-header-text-color, var(--primary-text-color, #141414));
        border-bottom: var(--app-header-border-bottom, none);
      }
      .main-title {
        margin: 0;
        margin-inline-start: var(--ha-space-5, 20px);
        font-size: var(--ha-font-size-xl, 20px);
        font-weight: var(--ha-font-weight-normal, 400);
        line-height: var(--ha-line-height-condensed, 1.2);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      ha-icon-button + .main-title {
        margin-inline-start: var(--ha-space-1, 4px);
      }
      .content {
        box-sizing: border-box;
        max-width: 1000px;
        margin: 0 auto;
        padding: var(--ha-space-4, 16px);
        padding-bottom: var(--ha-space-8, 32px);
      }
      :host([narrow]) .content {
        padding: var(--ha-space-2, 8px);
      }
      .intro,
      .summary,
      .hint {
        color: var(--secondary-text-color, #5e5e5e);
        font-size: var(--ha-font-size-m, 14px);
        line-height: var(--ha-line-height-normal, 1.6);
      }
      .intro {
        margin: 0 0 var(--ha-space-4, 16px);
      }
      .summary {
        margin: var(--ha-space-4, 16px) 0 var(--ha-space-2, 8px);
      }
      .search-buttons {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--ha-space-2, 8px);
      }
      .hint {
        flex-basis: 100%;
        font-size: var(--ha-font-size-s, 12px);
      }
      .state {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--ha-space-4, 16px);
        padding: var(--ha-space-8, 32px) var(--ha-space-4, 16px);
        text-align: center;
        color: var(--secondary-text-color, #5e5e5e);
      }
      .state p {
        margin: 0;
      }
      .alert {
        display: flex;
        align-items: flex-start;
        gap: var(--ha-space-3, 12px);
        margin-top: var(--ha-space-4, 16px);
        padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px);
        border-radius: var(--ha-border-radius-md, 8px);
        font-size: var(--ha-font-size-m, 14px);
        line-height: var(--ha-line-height-normal, 1.6);
      }
      .alert.error {
        background-color: var(
          --ha-color-fill-danger-quiet-resting,
          color-mix(in srgb, var(--error-color, #db4437) 12%, transparent)
        );
        --alert-icon-color: var(--error-color, #db4437);
      }
      .alert.warning {
        background-color: var(
          --ha-color-fill-warning-quiet-resting,
          color-mix(in srgb, var(--warning-color, #ffa600) 12%, transparent)
        );
        --alert-icon-color: var(--warning-color, #ffa600);
      }
      .alert.info {
        background-color: var(
          --ha-color-fill-primary-quiet-resting,
          color-mix(in srgb, var(--info-color, #039be5) 12%, transparent)
        );
        --alert-icon-color: var(--info-color, #039be5);
      }
      .alert ha-svg-icon {
        color: var(--alert-icon-color);
      }
      .alert-title {
        font-weight: var(--ha-font-weight-medium, 500);
      }
      .filters {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--ha-space-2, 8px) var(--ha-space-4, 16px);
        margin: var(--ha-space-4, 16px) 0;
      }
      .search {
        display: flex;
        align-items: center;
        gap: var(--ha-space-2, 8px);
        flex: 1 1 260px;
        box-sizing: border-box;
        height: 40px;
        padding: 0 var(--ha-space-3, 12px);
        border: 1px solid var(--ha-color-border-neutral-quiet, var(--divider-color, #e0e0e0));
        border-radius: var(--ha-border-radius-pill, 9999px);
        background-color: var(--card-background-color, #fff);
        color: var(--secondary-text-color, #5e5e5e);
      }
      .search:focus-within {
        border-color: var(--primary-color, #009ac7);
        outline: 1px solid var(--primary-color, #009ac7);
      }
      .search input {
        flex: 1;
        min-width: 0;
        height: 100%;
        border: none;
        outline: none;
        background: none;
        color: var(--primary-text-color, #141414);
        font: inherit;
        font-size: var(--ha-font-size-m, 14px);
      }
      :host([narrow]) .search {
        flex-basis: 100%;
      }
      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: var(--ha-space-2, 8px);
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: var(--ha-space-1, 4px);
        height: 32px;
        padding: 0 var(--ha-space-3, 12px);
        border: 1px solid var(--ha-color-border-neutral-quiet, var(--divider-color, #e0e0e0));
        border-radius: var(--ha-border-radius-md, 8px);
        background: none;
        color: var(--primary-text-color, #141414);
        font: inherit;
        font-size: var(--ha-font-size-m, 14px);
        cursor: pointer;
        --mdc-icon-size: 18px;
      }
      .chip:hover {
        background-color: var(--ha-color-fill-neutral-quiet-hover, var(--secondary-background-color, #f2f2f2));
      }
      .chip[aria-pressed="true"] {
        border-color: transparent;
        background-color: var(
          --ha-color-fill-primary-normal-resting,
          color-mix(in srgb, var(--primary-color, #009ac7) 20%, transparent)
        );
        color: var(--ha-color-on-primary-normal, var(--primary-text-color, #141414));
      }
      .chip:focus-visible,
      .installed-toggle input:focus-visible {
        outline: 2px solid var(--primary-color, #009ac7);
        outline-offset: 2px;
      }
      .count {
        color: var(--secondary-text-color, #5e5e5e);
        font-size: var(--ha-font-size-s, 12px);
      }
      .installed-toggle {
        display: inline-flex;
        align-items: center;
        gap: var(--ha-space-2, 8px);
        font-size: var(--ha-font-size-m, 14px);
        cursor: pointer;
      }
      .installed-toggle input {
        width: 18px;
        height: 18px;
        margin: 0;
        accent-color: var(--primary-color, #009ac7);
        cursor: pointer;
      }
      .results {
        list-style: none;
        margin: 0;
        padding: 0;
        overflow: hidden;
        background: var(--ha-card-background, var(--card-background-color, #fff));
        border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
        border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
        box-shadow: var(--ha-card-box-shadow, none);
      }
      .results li + li {
        border-top: 1px solid var(--divider-color, #e0e0e0);
      }
    `,
  ];
}

if (!customElements.get("marketplace-discovery-panel")) {
  customElements.define("marketplace-discovery-panel", MarketplaceDiscoveryPanel);
}
