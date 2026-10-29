type PluralMessage = Partial<Record<Intl.LDMLPluralRule, string>> & { other: string };

type Message = string | PluralMessage;

const en = {
  "panel.title": "Marketplace discovery",
  "panel.open_sidebar": "Open sidebar",
  "panel.scan": "Scan",
  "panel.scanning": "Scanning",
  "start.title": "Find devices you can set up with the Marketplace",
  "start.text":
    "Scan checks your network and compares the devices it finds with the discovery rules of Marketplace integrations. A match means an integration may support a device, so check the integration before you install it.",
  "scan.title": "Scanning your network",
  "scan.detail": "Asking Bluetooth, zeroconf and SSDP devices to announce themselves.",
  "scan.duration": { one: "This takes about {count} second.", other: "This takes about {count} seconds." },
  "error.scan_title": "Scan failed",
  "error.ignore_title": "Could not update the ignored integrations",
  "error.not_loaded": "Marketplace discovery is not loaded. Check the integration on the integrations page.",
  "error.unknown": "Unknown error, check the Home Assistant logs",
  "dataset.unavailable_title": "List of Marketplace integrations not available",
  "dataset.unavailable_text": "The list is downloaded when Home Assistant can reach the internet. Try again later.",
  "results.none": "No devices found that a Marketplace integration supports.",
  "results.no_match": "No integration matches your search.",
  "results.all_hidden": "All matching integrations are installed or ignored. Select Installed or Ignored to see them.",
  "summary.integrations": { one: "{count} integration can set up", other: "{count} integrations can set up" },
  "summary.devices": { one: "{count} device", other: "{count} devices" },
  "summary.none": "No matching devices",
  "summary.on_network": "on your network.",
  "summary.compared": { one: "Compared with {count} Marketplace integration", other: "Compared with {count} Marketplace integrations" },
  "summary.compared_date": {
    one: "Compared with {count} Marketplace integration, list from {date}.",
    other: "Compared with {count} Marketplace integrations, list from {date}.",
  },
  "summary.compared_end": {
    one: "Compared with {count} Marketplace integration.",
    other: "Compared with {count} Marketplace integrations.",
  },
  "sources.skipped_title": "Some sources were not scanned",
  "sources.skipped_text": {
    one: "{sources} is not set up in Home Assistant.",
    other: "{sources} are not set up in Home Assistant.",
  },
  "toolbar.enter_selection": "Enter selection mode",
  "toolbar.exit_selection": "Exit selection mode",
  "toolbar.search": "Search",
  "toolbar.filters": "Filters",
  "toolbar.installed": "Installed",
  "toolbar.ignored": "Ignored",
  "selection.label": "Selection",
  "selection.count": { one: "{count} integration selected", other: "{count} integrations selected" },
  "selection.select_all": "Select all",
  "selection.ignore": "Ignore selected",
  "selection.ignore_short": "Ignore",
  "card.select": "Select {name}",
  "card.installed": "Installed",
  "card.ignored": "Ignored",
  "card.devices": { one: "{count} device", other: "{count} devices" },
  "card.more": { one: "{list} and {count} more", other: "{list} and {count} more" },
  "card.stars": { one: "star", other: "stars" },
  "card.updated": "Updated {time}",
  "card.show_all": { one: "Show {count} device", other: "Show all {count} devices" },
  "card.show_all_short": "Show all {count}",
  "card.show_less": "Show less",
  "card.ignore": "Ignore",
  "card.stop_ignoring": "Stop ignoring",
  "card.open": "Open in Marketplace",
  "card.unknown_device": "Unknown device",
  "section.installed": "Installed",
  "section.ignored": "Ignored",
  "section.available": "Available",
} satisfies Record<string, Message>;

export type LocalizeKey = keyof typeof en;

type Dictionary = { [K in LocalizeKey]: (typeof en)[K] extends string ? string : PluralMessage };

const fr: Dictionary = {
  "panel.title": "Marketplace discovery",
  "panel.open_sidebar": "Ouvrir la barre latérale",
  "panel.scan": "Scanner",
  "panel.scanning": "Scan en cours…",
  "start.title": "Trouvez les appareils à configurer avec le Marketplace",
  "start.text":
    "Le scan parcourt votre réseau et compare les appareils trouvés avec les règles de découverte des intégrations du Marketplace. Une correspondance indique qu'une intégration peut prendre en charge un appareil, vérifiez donc l'intégration avant de l'installer.",
  "scan.title": "Scan de votre réseau",
  "scan.detail": "Les appareils Bluetooth, zeroconf et SSDP sont invités à se signaler.",
  "scan.duration": { one: "Cela prend environ {count} seconde.", other: "Cela prend environ {count} secondes." },
  "error.scan_title": "Le scan a échoué",
  "error.ignore_title": "Impossible de mettre à jour les intégrations ignorées",
  "error.not_loaded": "Marketplace discovery n'est pas chargée. Vérifiez l'intégration sur la page des intégrations.",
  "error.unknown": "Erreur inconnue, consultez les journaux de Home Assistant",
  "dataset.unavailable_title": "Liste des intégrations du Marketplace indisponible",
  "dataset.unavailable_text": "La liste est téléchargée lorsque Home Assistant peut accéder à Internet. Réessayez plus tard.",
  "results.none": "Aucun appareil pris en charge par une intégration du Marketplace n'a été trouvé.",
  "results.no_match": "Aucune intégration ne correspond à votre recherche.",
  "results.all_hidden":
    "Toutes les intégrations trouvées sont installées ou ignorées. Sélectionnez Installées ou Ignorées pour les afficher.",
  "summary.integrations": { one: "{count} intégration peut configurer", other: "{count} intégrations peuvent configurer" },
  "summary.devices": { one: "{count} appareil", other: "{count} appareils" },
  "summary.none": "Aucun appareil correspondant",
  "summary.on_network": "sur votre réseau.",
  "summary.compared": {
    one: "Comparé à {count} intégration du Marketplace",
    other: "Comparé à {count} intégrations du Marketplace",
  },
  "summary.compared_date": {
    one: "Comparé à {count} intégration du Marketplace, liste du {date}.",
    other: "Comparé à {count} intégrations du Marketplace, liste du {date}.",
  },
  "summary.compared_end": {
    one: "Comparé à {count} intégration du Marketplace.",
    other: "Comparé à {count} intégrations du Marketplace.",
  },
  "sources.skipped_title": "Certaines sources n'ont pas été scannées",
  "sources.skipped_text": {
    one: "{sources} n'est pas configuré dans Home Assistant.",
    other: "{sources} ne sont pas configurés dans Home Assistant.",
  },
  "toolbar.enter_selection": "Passer en mode sélection",
  "toolbar.exit_selection": "Quitter le mode de sélection",
  "toolbar.search": "Rechercher",
  "toolbar.filters": "Filtres",
  "toolbar.installed": "Installées",
  "toolbar.ignored": "Ignorées",
  "selection.label": "Sélection",
  "selection.count": { one: "{count} intégration sélectionnée", other: "{count} intégrations sélectionnées" },
  "selection.select_all": "Tout sélectionner",
  "selection.ignore": "Ignorer la sélection",
  "selection.ignore_short": "Ignorer",
  "card.select": "Sélectionner {name}",
  "card.installed": "Installée",
  "card.ignored": "Ignorée",
  "card.devices": { one: "{count} appareil", other: "{count} appareils" },
  "card.more": { one: "{list} et {count} autre", other: "{list} et {count} autres" },
  "card.stars": { one: "étoile", other: "étoiles" },
  "card.updated": "Mis à jour {time}",
  "card.show_all": { one: "Afficher {count} appareil", other: "Afficher les {count} appareils" },
  "card.show_all_short": "Tout afficher ({count})",
  "card.show_less": "Afficher moins",
  "card.ignore": "Ignorer",
  "card.stop_ignoring": "Ne plus ignorer",
  "card.open": "Ouvrir dans le Marketplace",
  "card.unknown_device": "Appareil inconnu",
  "section.installed": "Installées",
  "section.ignored": "Ignorées",
  "section.available": "Disponibles",
};

export const DICTIONARIES = { en, fr } as const;

export type Language = keyof typeof DICTIONARIES;

export type LocalizeParams = Record<string, string | number>;

export type LocalizeFunc = (key: LocalizeKey, params?: LocalizeParams) => string;

export interface Localizer {
  language: Language;
  locale: string;
  localize: LocalizeFunc;
  formatNumber: (value: number) => string;
  formatCompact: (value: number) => string;
  formatList: (items: string[]) => string;
  formatDate: (value: string) => string | null;
  formatRelative: (value: string, now?: Date) => string | null;
}

const isLanguage = (value: string): value is Language => Object.hasOwn(DICTIONARIES, value);

export const resolveLanguage = (tag: string | null | undefined): Language => {
  const normalized = (tag ?? "").toLowerCase().replace("_", "-");
  if (isLanguage(normalized)) {
    return normalized;
  }
  const base = normalized.split("-")[0];
  return isLanguage(base) ? base : "en";
};

export const languageOf = (hass?: { locale?: { language?: string }; language?: string }): string | undefined =>
  hass?.locale?.language || hass?.language || undefined;

const intlLocale = (tag: string | null | undefined, language: Language): string => {
  if (!tag || tag.toLowerCase().split(/[-_]/)[0] !== language) {
    return language;
  }
  try {
    return Intl.getCanonicalLocales(tag.replace("_", "-"))[0] ?? language;
  } catch {
    return language;
  }
};

const DAY_MS = 24 * 60 * 60 * 1000;

const parseDate = (value: string): Date | null => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};

const startOfDay = (date: Date): number => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();

export const createLocalizer = (tag?: string | null): Localizer => {
  const language = resolveLanguage(tag);
  const locale = intlLocale(tag, language);
  const dictionary: Record<LocalizeKey, Message> = DICTIONARIES[language];
  const plurals = new Intl.PluralRules(locale);
  const numbers = new Intl.NumberFormat(locale);
  const compact = new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 1 });
  const lists = new Intl.ListFormat(locale, { style: "long", type: "conjunction" });
  const dates = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });
  const relativeDays = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const relative = new Intl.RelativeTimeFormat(locale);

  const formatNumber = (value: number): string => numbers.format(value);

  const localize: LocalizeFunc = (key, params = {}) => {
    const message = dictionary[key] ?? en[key];
    let text: string;
    if (typeof message === "string") {
      text = message;
    } else {
      const count = Number(params.count ?? 0);
      text = message[plurals.select(count)] ?? message.other;
    }
    return text.replace(/\{(\w+)\}/g, (match, name: string) => {
      const value = params[name];
      if (value === undefined) {
        return match;
      }
      return typeof value === "number" ? formatNumber(value) : value;
    });
  };

  const formatRelative = (value: string, now: Date = new Date()): string | null => {
    const date = parseDate(value);
    if (!date) {
      return null;
    }
    const days = Math.max(0, Math.round((startOfDay(now) - startOfDay(date)) / DAY_MS));
    if (days < 30) {
      return relativeDays.format(-days, "day");
    }
    const months = Math.max(1, Math.round(days / 30));
    if (months < 12) {
      return relative.format(-months, "month");
    }
    return relative.format(-Math.max(1, Math.round(days / 365)), "year");
  };

  return {
    language,
    locale,
    localize,
    formatNumber,
    formatCompact: (value) => compact.format(value),
    formatList: (items) => lists.format(items),
    formatDate: (value) => {
      const date = parseDate(value);
      return date ? dates.format(date) : null;
    },
    formatRelative,
  };
};
