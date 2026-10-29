import {
  mdiAlertCircleOutline,
  mdiClose,
  mdiFormatListChecks,
  mdiInformationOutline,
  mdiMagnify,
  mdiMenu,
  mdiRefresh,
} from "@mdi/js";
import { css, html, LitElement, nothing, type PropertyValues, type TemplateResult } from "lit";
import { property, state } from "lit/decorators.js";
import { repeat } from "lit/directives/repeat.js";
import { brandIconUrl, SOURCE_LABELS, SOURCES } from "./format.ts";
import { buildView, type DiscoveryView, type IntegrationGroup } from "./group.ts";
import { type MpdIntegrationCard, SOURCE_ICONS } from "./integration-card.ts";
import { createLocalizer, languageOf, type LocalizeFunc, type Localizer } from "./localize.ts";
import { sharedStyles } from "./styles.ts";
import type {
  BrandsTokenResponse,
  HomeAssistant,
  IgnoreResponse,
  MatchesResponse,
  PanelInfo,
  Route,
  Source,
} from "./types.ts";

const REFRESH_SECONDS = 10;
const TOKEN_REFRESH_MS = 30 * 60 * 1000;
const TOKEN_RETRY_DELAYS_MS = [0, 500, 1000, 2000, 5000, 10000, 15000];

interface ErrorLike {
  code?: string;
  message?: string;
}

interface SavedState {
  response: MatchesResponse;
  ignored: Set<string>;
  filter: string;
  selectedSources: Set<Source>;
  showInstalled: boolean;
  showIgnored: boolean;
  openCards: Map<string, boolean>;
}

let savedState: SavedState | undefined;

let savedScrollTop = 0;

const findScroller = (node: Element): HTMLElement => {
  let current: Node | null = node;
  while (current) {
    current = current instanceof ShadowRoot ? current.host : current.parentNode;
    if (current instanceof HTMLElement && /^(auto|scroll)$/.test(getComputedStyle(current).overflowY)) {
      return current;
    }
  }
  return document.scrollingElement as HTMLElement;
};

const errorMessage = (err: unknown, localize: LocalizeFunc): string => {
  const { code, message } = (typeof err === "object" && err !== null ? err : {}) as ErrorLike;
  if (code === "not_loaded") {
    return localize("error.not_loaded");
  }
  return message || (typeof err === "string" && err ? err : localize("error.unknown"));
};

export class MarketplaceDiscoveryPanel extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;

  @property({ type: Boolean, reflect: true }) public narrow = false;

  @property({ attribute: false }) public route?: Route;

  @property({ attribute: false }) public panel?: PanelInfo;

  @state() private _localizer: Localizer = createLocalizer("en");

  @state() private _response?: MatchesResponse;

  @state() private _loading?: "load" | "scan";

  @state() private _error?: unknown;

  @state() private _actionError?: unknown;

  @state() private _busy = false;

  @state() private _ignored = new Set<string>();

  @state() private _filter = "";

  @state() private _selectedSources = new Set<Source>();

  @state() private _showInstalled = false;

  @state() private _showIgnored = false;

  @state() private _selectMode = false;

  @state() private _selected = new Set<string>();

  @state() private _openCards = new Map<string, boolean>();

  @state() private _brandsToken?: string;

  private _requestId = 0;

  private _tokenInterval?: ReturnType<typeof setInterval>;

  private _scroller?: HTMLElement;

  private _restoreScroll = false;

  private _onScroll = (): void => {
    if (this._scroller && this._response) {
      savedScrollTop = this._scroller.scrollTop;
    }
  };

  private get _scrollTarget(): HTMLElement | Window | undefined {
    return this._scroller === document.scrollingElement ? window : this._scroller;
  }

  public connectedCallback(): void {
    super.connectedCallback();
    if (!this._response && savedState) {
      this._response = savedState.response;
      this._ignored = savedState.ignored;
      this._filter = savedState.filter;
      this._selectedSources = savedState.selectedSources;
      this._showInstalled = savedState.showInstalled;
      this._showIgnored = savedState.showIgnored;
      this._openCards = savedState.openCards;
      this._restoreScroll = true;
    }
    this._tokenInterval = setInterval(() => {
      if (this.hass) {
        this._fetchBrandsToken();
      }
    }, TOKEN_REFRESH_MS);
    if (this.hasUpdated && this.hass) {
      this._fetchBrandsToken();
    }
  }

  public disconnectedCallback(): void {
    super.disconnectedCallback();
    this._scrollTarget?.removeEventListener("scroll", this._onScroll);
    this._scroller = undefined;
    clearInterval(this._tokenInterval);
    this._tokenInterval = undefined;
  }

  protected shouldUpdate(changedProps: PropertyValues<this>): boolean {
    if (changedProps.size !== 1 || !changedProps.has("hass")) {
      return true;
    }
    const oldHass = changedProps.get("hass") as HomeAssistant | undefined;
    return (
      !oldHass ||
      oldHass.kioskMode !== this.hass.kioskMode ||
      oldHass.dockedSidebar !== this.hass.dockedSidebar ||
      oldHass.themes?.darkMode !== this.hass.themes?.darkMode ||
      languageOf(oldHass) !== languageOf(this.hass)
    );
  }

  protected firstUpdated(): void {
    this._scroller = findScroller(this);
    this._scrollTarget?.addEventListener("scroll", this._onScroll, { passive: true });
    if (this._restoreScroll) {
      this._restoreScroll = false;
      const top = savedScrollTop;
      requestAnimationFrame(() => {
        if (this._scroller) {
          this._scroller.scrollTop = top;
        }
      });
    }
  }

  protected updated(): void {
    if (!this._response) {
      savedScrollTop = 0;
    }
    savedState = this._response
      ? {
          response: this._response,
          ignored: this._ignored,
          filter: this._filter,
          selectedSources: this._selectedSources,
          showInstalled: this._showInstalled,
          showIgnored: this._showIgnored,
          openCards: this._openCards,
        }
      : undefined;
  }

  protected willUpdate(changedProps: PropertyValues<this>): void {
    if (!changedProps.has("hass") || !this.hass) {
      return;
    }
    this.toggleAttribute("dark", this.hass.themes?.darkMode === true);
    const oldHass = changedProps.get("hass") as HomeAssistant | undefined;
    if (!oldHass || languageOf(oldHass) !== languageOf(this.hass)) {
      this._localizer = createLocalizer(languageOf(this.hass));
    }
    if (!oldHass) {
      this._fetchBrandsToken();
      this._load(false);
    }
  }

  protected render(): TemplateResult {
    const { localize } = this._localizer;
    return html`
      <div class="header">
        ${
          this._showMenuButton()
            ? html`<ha-icon-button .path=${mdiMenu} .label=${localize("panel.open_sidebar")} @click=${this._toggleMenu}></ha-icon-button>`
            : nothing
        }
        <h1 class="main-title">${localize("panel.title")}</h1>
        ${
          this._loading === "scan"
            ? html`<ha-spinner class="header-spinner" size="small" aria-label=${localize("panel.scanning")}></ha-spinner>`
            : this._response || this._error !== undefined
              ? html`<ha-icon-button .path=${mdiRefresh} .label=${localize("panel.rescan")} @click=${this._scan}></ha-icon-button>`
              : nothing
        }
      </div>
      <div class="content">${this._renderBody()}</div>
    `;
  }

  private _renderBody(): TemplateResult {
    const { localize } = this._localizer;
    if (this._loading === "scan") {
      return html`
        <div class="card state" role="status">
          <ha-spinner class="scan-spinner"></ha-spinner>
          <div class="state-text">
            <strong>${localize("scan.title")}</strong>
            <span>
              ${this.narrow ? nothing : `${localize("scan.detail")} `}${localize("scan.duration", { count: REFRESH_SECONDS })}
            </span>
          </div>
        </div>
      `;
    }
    if (this._error !== undefined) {
      return this._renderAlert("error", localize("error.scan_title"), errorMessage(this._error, localize));
    }
    const response = this._response;
    if (!response) {
      return html`
        <div class="card state" role="status">
          <ha-spinner class="scan-spinner"></ha-spinner>
          <span>${localize("panel.loading")}</span>
        </div>
      `;
    }
    if (!response.dataset) {
      return this._renderAlert("warning", localize("dataset.unavailable_title"), localize("dataset.unavailable_text"));
    }
    const view = buildView(response.results, {
      filter: this._filter,
      sources: this._selectedSources,
      showInstalled: this._showInstalled,
      showIgnored: this._showIgnored,
      ignored: this._ignored,
    });
    const hasResults = response.results.length > 0;
    return html`
      <div class="results">
        ${hasResults ? (this.narrow ? this._renderNarrowToolbar(view) : this._renderToolbar(view)) : nothing}
        ${this.narrow && this._selectMode && hasResults ? this._renderSelectionBar(view) : this._renderSummary(response, view)}
        ${this._renderSkippedSources(response)}
        ${
          this._actionError !== undefined
            ? this._renderAlert("error", localize("error.ignore_title"), errorMessage(this._actionError, localize))
            : nothing
        }
        ${
          hasResults
            ? this._renderCards(view)
            : html`<div class="card state"><span>${localize("results.none")}</span></div>`
        }
      </div>
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

  private _renderSummary(response: MatchesResponse, view: DiscoveryView): TemplateResult {
    const { localize, formatDate } = this._localizer;
    const dataset = response.dataset!;
    const count = dataset.integrations;
    const title = response.results.length
      ? `${localize("summary.integrations", { count: view.availableCount })} ${localize("summary.devices", {
          count: view.deviceCount,
        })}`
      : localize("summary.none");
    if (this.narrow) {
      return html`<p class="summary"><strong>${title}</strong><br />${localize("summary.compared", { count })}</p>`;
    }
    const date = formatDate(dataset.generated_at);
    return html`
      <p class="summary">
        <strong>${title}</strong> ${localize("summary.on_network")}
        ${date ? localize("summary.compared_date", { count, date }) : localize("summary.compared_end", { count })}
      </p>
    `;
  }

  private _renderSkippedSources(response: MatchesResponse): TemplateResult | typeof nothing {
    const { localize, formatList } = this._localizer;
    const skipped = SOURCES.filter((source) => response.sources?.[source] === false);
    if (!skipped.length) {
      return nothing;
    }
    return this._renderAlert(
      "info",
      localize("sources.skipped_title"),
      localize("sources.skipped_text", {
        count: skipped.length,
        sources: formatList(skipped.map((source) => SOURCE_LABELS[source])),
      }),
    );
  }

  private _renderSelectChip(): TemplateResult {
    const label = this._localizer.localize("toolbar.enter_selection");
    return html`
      <button type="button" class="chip icon-chip" aria-label=${label} title=${label} @click=${this._enterSelectMode}>
        <ha-svg-icon .path=${mdiFormatListChecks}></ha-svg-icon>
      </button>
    `;
  }

  private _renderFilter(): TemplateResult {
    const { localize } = this._localizer;
    return html`
      <label class="search">
        <ha-svg-icon .path=${mdiMagnify}></ha-svg-icon>
        <span class="visually-hidden">${localize("toolbar.search")}</span>
        <input
          type="search"
          name="filter"
          placeholder=${localize("toolbar.search")}
          .value=${this._filter}
          @input=${this._filterChanged}
        />
      </label>
    `;
  }

  private _renderSourceChips(view: DiscoveryView): TemplateResult[] {
    return SOURCES.map((source) => {
      const selected = this._selectedSources.has(source);
      return html`
        <button
          class="chip"
          type="button"
          aria-pressed=${selected ? "true" : "false"}
          .value=${source}
          @click=${this._toggleSource}
        >
          <ha-svg-icon .path=${SOURCE_ICONS[source]}></ha-svg-icon>
          <span>${SOURCE_LABELS[source]}</span>
          <span class="count">${view.sourceCounts[source]}</span>
        </button>
      `;
    });
  }

  private _renderToggleChips(view: DiscoveryView): TemplateResult {
    const { localize } = this._localizer;
    return html`
      <button
        class="chip"
        type="button"
        aria-pressed=${this._showInstalled ? "true" : "false"}
        @click=${this._toggleInstalled}
      >
        <span>${localize("toolbar.installed")}</span>
        <span class="count">${view.installedCount}</span>
      </button>
      <button class="chip" type="button" aria-pressed=${this._showIgnored ? "true" : "false"} @click=${this._toggleIgnored}>
        <span>${localize("toolbar.ignored")}</span>
        <span class="count">${view.ignoredCount}</span>
      </button>
    `;
  }

  private _renderToolbar(view: DiscoveryView): TemplateResult {
    const { localize } = this._localizer;
    if (this._selectMode) {
      return this._renderSelectionBar(view);
    }
    return html`
      <div class="toolbar">${this._renderSelectChip()} ${this._renderFilter()}</div>
      <div class="chips" role="group" aria-label=${localize("toolbar.filters")}>
        ${this._renderSourceChips(view)}
        <span class="divider" aria-hidden="true"></span>
        ${this._renderToggleChips(view)}
      </div>
    `;
  }

  private _renderNarrowToolbar(view: DiscoveryView): TemplateResult {
    const { localize } = this._localizer;
    return html`
      <div class="toolbar">${this._selectMode ? nothing : this._renderSelectChip()} ${this._renderFilter()}</div>
      <div class="chips scroll" role="group" aria-label=${localize("toolbar.filters")}>
        ${this._renderSourceChips(view)}
        <span class="divider" aria-hidden="true"></span>
        ${this._renderToggleChips(view)}
      </div>
    `;
  }

  private _renderSelectionBar(view: DiscoveryView): TemplateResult {
    const { localize } = this._localizer;
    const count = this._selectedIds(view).length;
    return html`
      <div class="selection-bar" role="toolbar" aria-label=${localize("selection.label")}>
        <ha-icon-button
          class="exit"
          .path=${mdiClose}
          .label=${localize("toolbar.exit_selection")}
          title=${localize("toolbar.exit_selection")}
          @click=${this._exitSelectMode}
        ></ha-icon-button>
        <span class="selected-count">${localize("selection.count", { count })}</span>
        <ha-button appearance="plain" @click=${() => this._selectAll(view)}>${localize("selection.select_all")}</ha-button>
        <ha-button
          class="ignore-selected"
          appearance="accent"
          .disabled=${count === 0 || this._busy}
          @click=${() => this._ignoreSelected(view)}
        >
          ${localize(this.narrow ? "selection.ignore_short" : "selection.ignore")}
        </ha-button>
      </div>
    `;
  }

  private _renderCards(view: DiscoveryView): TemplateResult {
    if (!view.integrations.length) {
      const { localize } = this._localizer;
      const filtering = this._filter.trim() !== "" || this._selectedSources.size > 0;
      return html`<div class="card state"><span>${localize(filtering ? "results.no_match" : "results.all_hidden")}</span></div>`;
    }
    const { localize } = this._localizer;
    const installed = view.integrations.filter((group) => group.installed);
    const ignored = view.integrations.filter((group) => group.ignored && !group.installed);
    const available = view.integrations.filter((group) => !group.installed && !group.ignored);
    const sections = (
      [
        ["section.installed", installed],
        ["section.ignored", ignored],
      ] as const
    ).filter(([, groups]) => groups.length);
    return html`
      ${sections.map(
        ([key, groups]) => html`
          <h2 class="section-title">${localize(key)} <span class="count">${groups.length}</span></h2>
          ${this._renderCardList(groups)}
        `,
      )}
      ${
        available.length && sections.length
          ? html`<h2 class="section-title">${localize("section.available")} <span class="count">${available.length}</span></h2>`
          : nothing
      }
      ${this._renderCardList(available)}
    `;
  }

  private _renderCardList(groups: IntegrationGroup[]): TemplateResult {
    const filtering = this._filter.trim() !== "";
    const dark = this.hass?.themes?.darkMode === true;
    return html`${repeat(
      groups,
      (group) => group.repository_id,
      (group) => html`
        <mpd-integration-card
          .group=${group}
          .localizer=${this._localizer}
          .open=${this._openCards.get(group.repository_id) ?? filtering}
          .narrow=${this.narrow}
          .selecting=${this._selectMode}
          .selected=${this._selected.has(group.repository_id)}
          .ignored=${group.ignored}
          .busy=${this._busy}
          .logoUrl=${brandIconUrl(group.domain, this._brandsToken, dark)}
          @mpd-toggle=${(ev: CustomEvent<{ open: boolean }>) => this._setCardOpen(group.repository_id, ev.detail.open)}
          @mpd-select=${(ev: CustomEvent<{ selected: boolean }>) => this._setSelected(group.repository_id, ev.detail.selected)}
          @mpd-ignore=${this._ignoreCard}
        ></mpd-integration-card>
      `,
    )}`;
  }

  private _selectedIds(view: DiscoveryView): string[] {
    return view.integrations.map((group) => group.repository_id).filter((id) => this._selected.has(id));
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

  private async _fetchBrandsToken(): Promise<void> {
    for (const delay of TOKEN_RETRY_DELAYS_MS) {
      if (delay) {
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
      if (!this.isConnected) {
        return;
      }
      const response = await this.hass
        .callWS<BrandsTokenResponse>({ type: "brands/access_token" })
        .catch(() => undefined);
      if (response?.token) {
        this._brandsToken = response.token;
        return;
      }
    }
  }

  private _scan(): void {
    this._load(true);
  }

  private async _load(refresh: boolean): Promise<void> {
    if (this._loading === "scan") {
      return;
    }
    const requestId = ++this._requestId;
    this._loading = refresh ? "scan" : this._response ? undefined : "load";
    this._error = undefined;
    this._actionError = undefined;
    this._fetchBrandsToken();
    try {
      const response = await this.hass.callWS<MatchesResponse>({
        type: "marketplace_discovery/matches",
        refresh,
      });
      if (requestId !== this._requestId) {
        return;
      }
      const results = response.results ?? [];
      this._response = { ...response, results };
      this._ignored = new Set(
        response.ignored ?? results.filter((result) => result.ignored).map((result) => result.repository_id),
      );
    } catch (err) {
      if (requestId !== this._requestId) {
        return;
      }
      this._response = undefined;
      this._error = err ?? "";
    } finally {
      if (requestId === this._requestId) {
        this._loading = undefined;
      }
    }
  }

  private async _setIgnored(repositoryIds: string[], ignore: boolean): Promise<boolean> {
    if (this._busy || !repositoryIds.length) {
      return false;
    }
    this._busy = true;
    this._actionError = undefined;
    try {
      const response = await this.hass.callWS<IgnoreResponse>({
        type: ignore ? "marketplace_discovery/ignore" : "marketplace_discovery/unignore",
        repository_ids: repositoryIds,
      });
      this._ignored = new Set(response.ignored);
      const openCards = new Map(this._openCards);
      for (const id of repositoryIds) {
        openCards.set(id, false);
      }
      this._openCards = openCards;
      return true;
    } catch (err) {
      this._actionError = err ?? "";
      return false;
    } finally {
      this._busy = false;
    }
  }

  private async _ignoreCard(ev: CustomEvent<{ ignored: boolean }>): Promise<void> {
    const card = ev.currentTarget as MpdIntegrationCard;
    const cards = [...this.renderRoot.querySelectorAll<MpdIntegrationCard>("mpd-integration-card")];
    const index = cards.indexOf(card);
    if (!(await this._setIgnored([card.group.repository_id], ev.detail.ignored))) {
      return;
    }
    await this.updateComplete;
    if (card.isConnected) {
      return;
    }
    const next =
      cards.slice(index + 1).find((other) => other.isConnected) ??
      cards
        .slice(0, index)
        .reverse()
        .find((other) => other.isConnected);
    if (next) {
      next.focus();
    } else {
      this._focus(this._selectMode ? ".selection-bar .exit" : ".icon-chip");
    }
  }

  private async _ignoreSelected(view: DiscoveryView): Promise<void> {
    if (await this._setIgnored(this._selectedIds(view), true)) {
      this._exitSelectMode();
    }
  }

  private _enterSelectMode(): void {
    this._selectMode = true;
    this._selected = new Set();
    this._focus(".selection-bar .exit");
  }

  private _exitSelectMode(): void {
    this._selectMode = false;
    this._selected = new Set();
    this._focus(".icon-chip");
  }

  private async _focus(selector: string): Promise<void> {
    await this.updateComplete;
    this.renderRoot.querySelector<HTMLElement>(selector)?.focus();
  }

  private _selectAll(view: DiscoveryView): void {
    this._selected = new Set(view.integrations.filter((group) => !group.ignored).map((group) => group.repository_id));
  }

  private _setSelected(repositoryId: string, selected: boolean): void {
    const next = new Set(this._selected);
    if (selected) {
      next.add(repositoryId);
    } else {
      next.delete(repositoryId);
    }
    this._selected = next;
  }

  private _setCardOpen(repositoryId: string, open: boolean): void {
    this._openCards = new Map(this._openCards).set(repositoryId, open);
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

  private _toggleInstalled(): void {
    this._showInstalled = !this._showInstalled;
  }

  private _toggleIgnored(): void {
    this._showIgnored = !this._showIgnored;
  }

  static styles = [
    sharedStyles,
    css`
      :host {
        --mpd-on-primary-fill: var(--ha-color-primary-30, #00577a);
        --mpd-primary-text: var(--ha-color-primary-30, #00799f);
        --mpd-control-border: var(--ha-color-neutral-80, #c7c7c7);
        --mpd-star-color: #b27a00;
        display: block;
        min-height: 100%;
        background-color: var(--primary-background-color, #fafafa);
        font-size: var(--ha-font-size-m, 14px);
        line-height: 1.43;
      }
      :host([dark]) {
        --mpd-on-primary-fill: var(--ha-color-on-primary-normal, #37c8fd);
        --mpd-primary-text: var(--ha-color-on-primary-normal, #37c8fd);
        --mpd-control-border: var(--ha-color-border-neutral-quiet, #5e5e5e);
        --mpd-star-color: #e8b33f;
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
        padding: 0 var(--ha-space-4, 16px) 0 var(--ha-space-1, 4px);
        background-color: var(--app-header-background-color, var(--card-background-color, #ffffff));
        color: var(--app-header-text-color, var(--primary-text-color, #141414));
        border-bottom: var(--app-header-border-bottom, 1px solid var(--divider-color, #e3e3e3));
      }
      :host([narrow]) .header {
        padding-inline-end: 12px;
      }
      .main-title {
        flex: 1;
        min-width: 0;
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
      .header-spinner {
        flex: none;
        margin: 0 12px;
      }
      .content {
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-4, 16px);
        max-width: 1040px;
        margin: 0 auto;
        padding: var(--ha-space-5, 20px) var(--ha-space-4, 16px) var(--ha-space-16, 64px);
      }
      :host([narrow]) .content {
        padding: var(--ha-space-4, 16px);
      }
      .card {
        box-sizing: border-box;
        background: var(--ha-card-background, var(--card-background-color, #ffffff));
        border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e3e3e3));
        border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
      }
      .state {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--ha-space-4, 16px);
        padding: var(--ha-space-12, 48px) var(--ha-space-6, 24px);
        text-align: center;
        color: var(--secondary-text-color, #5e5e5e);
      }
      :host([narrow]) .state {
        padding: var(--ha-space-10, 40px) var(--ha-space-5, 20px);
      }
      .state[role="status"] {
        padding: var(--ha-space-16, 64px) var(--ha-space-6, 24px);
      }
      :host([narrow]) .state[role="status"] {
        padding: var(--ha-space-12, 48px) var(--ha-space-5, 20px);
      }
      .scan-spinner {
        --ha-spinner-size: 40px;
        --ha-spinner-divider-color: var(--ha-color-fill-primary-normal-resting, #dff3fc);
      }
      .state-text {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-1, 4px);
        max-width: 640px;
      }
      .state-text strong {
        font-size: var(--ha-font-size-l, 16px);
        font-weight: var(--ha-font-weight-medium, 500);
        color: var(--primary-text-color, #141414);
      }
      .results {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .summary {
        margin: var(--ha-space-1, 4px) 0 0;
        color: var(--secondary-text-color, #5e5e5e);
      }
      .summary strong {
        font-weight: var(--ha-font-weight-medium, 500);
        color: var(--primary-text-color, #141414);
      }
      :host([narrow]) .summary {
        margin: 0;
        font-size: var(--ha-font-size-s, 12px);
      }
      :host([narrow]) .summary strong {
        font-size: var(--ha-font-size-m, 14px);
      }
      .alert {
        display: flex;
        align-items: flex-start;
        gap: var(--ha-space-3, 12px);
        padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px);
        border-radius: var(--ha-border-radius-md, 8px);
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
      .toolbar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--ha-space-2, 8px);
      }
      :host([narrow]) .toolbar {
        flex-wrap: nowrap;
      }
      .search {
        display: flex;
        align-items: center;
        gap: var(--ha-space-2, 8px);
        flex: 1 1 240px;
        box-sizing: border-box;
        height: 36px;
        padding: 0 12px;
        border: 1px solid var(--mpd-control-border, #c7c7c7);
        border-radius: var(--ha-border-radius-pill, 9999px);
        background-color: var(--card-background-color, #ffffff);
        color: var(--secondary-text-color, #5e5e5e);
        --mdc-icon-size: 20px;
      }
      :host([narrow]) .search {
        flex: 1;
        min-width: 0;
        height: 44px;
      }
      .search:focus-within {
        border-color: var(--primary-color, #009ac7);
        outline: 1px solid var(--primary-color, #009ac7);
      }
      .search input {
        flex: 1;
        min-width: 0;
        height: 100%;
        padding: 0;
        border: none;
        outline: none;
        background: none;
        color: var(--primary-text-color, #141414);
        font: inherit;
      }
      .search input::placeholder {
        color: var(--secondary-text-color, #5e5e5e);
      }
      .chips {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--ha-space-2, 8px);
      }
      .chips.scroll {
        flex-wrap: nowrap;
        align-items: center;
        overflow-x: auto;
        margin: 0 calc(-1 * var(--ha-space-4, 16px));
        padding: 0 var(--ha-space-4, 16px);
        scrollbar-width: none;
      }
      .chips.scroll::-webkit-scrollbar {
        display: none;
      }
      .divider {
        flex: none;
        width: 1px;
        height: 24px;
        background: var(--divider-color, #e3e3e3);
      }
      .chip {
        flex: none;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        box-sizing: border-box;
        height: 36px;
        padding: 0 12px;
        border: 1px solid var(--mpd-control-border, #c7c7c7);
        border-radius: var(--ha-border-radius-pill, 9999px);
        background: var(--card-background-color, #ffffff);
        color: var(--primary-text-color, #141414);
        font: inherit;
        cursor: pointer;
        --mdc-icon-size: 18px;
      }
      :host([narrow]) .chip {
        height: 40px;
      }
      .chip:hover {
        background: var(--ha-color-fill-neutral-quiet-resting, #f2f2f2);
      }
      .chip[aria-pressed="true"] {
        border-color: var(--primary-color, #009ac7);
        background: var(--ha-color-fill-primary-normal-resting, #dff3fc);
        color: var(--mpd-on-primary-fill, #00577a);
        font-weight: var(--ha-font-weight-medium, 500);
      }
      .icon-chip {
        justify-content: center;
        width: 36px;
        padding: 0;
        color: var(--ha-color-on-neutral-normal, #3d3d3d);
      }
      :host([narrow]) .icon-chip {
        width: 44px;
        height: 44px;
        --mdc-icon-size: 20px;
      }
      .count {
        box-sizing: border-box;
        min-width: 20px;
        padding: 0 6px;
        border-radius: var(--ha-border-radius-pill, 9999px);
        background: color-mix(in srgb, currentColor 8%, transparent);
        font-size: var(--ha-font-size-s, 12px);
        text-align: center;
      }
      .section-title {
        display: flex;
        align-items: center;
        gap: var(--ha-space-2, 8px);
        margin: var(--ha-space-2, 8px) 0 0;
        font-size: var(--ha-font-size-m, 14px);
        font-weight: var(--ha-font-weight-medium, 500);
        color: var(--secondary-text-color, #5e5e5e);
      }
      .chip:focus-visible {
        outline: 2px solid var(--primary-color, #009ac7);
        outline-offset: 2px;
      }
      .selection-bar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--ha-space-2, 8px);
        min-height: 36px;
      }
      :host([narrow]) .selection-bar {
        row-gap: var(--ha-space-1, 4px);
      }
      .selection-bar .exit {
        --ha-icon-button-size: 36px;
        color: var(--ha-color-on-neutral-normal, #3d3d3d);
      }
      :host([narrow]) .selection-bar .exit {
        --ha-icon-button-size: 44px;
        margin-inline-start: -10px;
      }
      .selected-count {
        font-weight: var(--ha-font-weight-medium, 500);
      }
      .selection-bar ha-button {
        --ha-button-height: 36px;
      }
      :host([narrow]) .selection-bar ha-button {
        --ha-button-height: 40px;
      }
      .selection-bar ha-button[appearance="plain"] {
        --wa-color-brand-on-normal: var(--mpd-primary-text, #00799f);
      }
      .ignore-selected {
        margin-inline-start: auto;
      }
    `,
  ];
}

if (!customElements.get("marketplace-discovery-panel")) {
  customElements.define("marketplace-discovery-panel", MarketplaceDiscoveryPanel);
}
