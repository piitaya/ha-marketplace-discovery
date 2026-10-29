export type Source = "bluetooth" | "zeroconf" | "dhcp" | "ssdp";

export type Matcher = Record<string, unknown>;

export interface MatchDevice {
  name: string | null;
  ip: string | null;
  mac: string | null;
}

export interface MatchResult {
  repository_id: string;
  full_name: string;
  domain: string;
  name: string;
  installed: boolean;
  source: Source;
  matchers: Matcher[];
  device: MatchDevice;
  discovery: Record<string, unknown>;
}

export interface DatasetInfo {
  generated_at: string;
  fetched_at: string;
  integrations: number;
}

export interface MatchesResponse {
  dataset: DatasetInfo | null;
  sources: Record<Source, boolean>;
  results: MatchResult[];
}

export interface MatchesRequest {
  type: "marketplace_discovery/matches";
  refresh?: boolean;
}

export interface HomeAssistant {
  callWS<T>(message: MatchesRequest): Promise<T>;
  config: { version: string };
  language?: string;
  locale?: { language: string };
  kioskMode?: boolean;
  dockedSidebar?: "docked" | "always_hidden" | "auto";
  auth?: { external?: { config?: { hasSidebar?: boolean } } };
}

export interface PanelInfo {
  url_path: string;
  title: string | null;
  config: Record<string, unknown> | null;
}

export interface Route {
  prefix: string;
  path: string;
}
