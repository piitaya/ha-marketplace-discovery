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
  ignored?: boolean;
  stars?: number | null;
  last_updated?: string | null;
  description?: string | null;
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
  ignored?: string[];
}

export interface MatchesRequest {
  type: "marketplace_discovery/matches";
  refresh?: boolean;
}

export interface IgnoreRequest {
  type: "marketplace_discovery/ignore" | "marketplace_discovery/unignore";
  repository_ids: string[];
}

export interface IgnoreResponse {
  ignored: string[];
}

export interface BrandsTokenRequest {
  type: "brands/access_token";
}

export interface BrandsTokenResponse {
  token: string;
}

export interface HomeAssistant {
  callWS<T>(message: MatchesRequest | IgnoreRequest | BrandsTokenRequest): Promise<T>;
  config: { version: string };
  language?: string;
  locale?: { language: string };
  kioskMode?: boolean;
  themes?: { darkMode?: boolean };
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
