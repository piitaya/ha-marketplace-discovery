import { matchesFilter, SOURCES } from "./format.ts";
import type { MatchDevice, MatchResult, Matcher, Source } from "./types.ts";

export interface IntegrationGroup {
  repository_id: string;
  name: string;
  full_name: string;
  domain: string;
  installed: boolean;
  ignored: boolean;
  marketplace: boolean;
  stars: number | null;
  last_updated: string | null;
  description: string | null;
  results: MatchResult[];
}

export interface Rule {
  source: Source;
  matchers: Matcher[];
}

export interface DeviceEntry {
  key: string;
  result: MatchResult;
  sources: Source[];
  rules: Rule[];
}

export interface ViewOptions {
  filter: string;
  sources: ReadonlySet<Source>;
  showInstalled: boolean;
  showIgnored: boolean;
  showCustom: boolean;
  ignored: ReadonlySet<string>;
}

export interface DiscoveryView {
  integrations: IntegrationGroup[];
  sourceCounts: Record<Source, number>;
  installedCount: number;
  ignoredCount: number;
  customCount: number;
  availableCount: number;
  deviceCount: number;
}

export const groupByIntegration = (results: readonly MatchResult[]): IntegrationGroup[] => {
  const groups = new Map<string, IntegrationGroup>();
  for (const result of results) {
    const group = groups.get(result.repository_id);
    if (group) {
      group.results.push(result);
      continue;
    }
    groups.set(result.repository_id, {
      repository_id: result.repository_id,
      name: result.name,
      full_name: result.full_name,
      domain: result.domain,
      installed: result.installed,
      ignored: result.ignored ?? false,
      marketplace: result.marketplace ?? true,
      stars: result.stars ?? null,
      last_updated: result.last_updated ?? null,
      description: result.description ?? null,
      results: [result],
    });
  }
  return [...groups.values()];
};

const ruleKey = (result: MatchResult): string =>
  [result.source, ...result.matchers.map((matcher) => JSON.stringify(matcher)).sort()].join("\n");

const bySource = (a: MatchResult, b: MatchResult): number => SOURCES.indexOf(a.source) - SOURCES.indexOf(b.source);

export const deviceKey = (device: MatchDevice): string | null => {
  const id = device.ip || device.mac || device.name;
  return id ? id.toLowerCase() : null;
};

const mergeDevice = (results: readonly MatchResult[]): MatchResult => {
  const ordered = [...results].sort(bySource);
  const pick = (field: keyof MatchDevice) => ordered.find((result) => result.device[field])?.device[field] ?? null;
  const bluetooth = ordered.find((result) => result.source === "bluetooth");
  return {
    ...ordered[0],
    device: { name: pick("name"), ip: pick("ip"), mac: pick("mac") },
    discovery: (bluetooth ?? ordered[0]).discovery,
  };
};

export const groupByDevice = (results: readonly MatchResult[]): DeviceEntry[] => {
  const devices = new Map<string, MatchResult[]>();
  results.forEach((result, index) => {
    const key = deviceKey(result.device) ?? `#${index}`;
    devices.set(key, [...(devices.get(key) ?? []), result]);
  });
  return [...devices].map(([key, deviceResults]) => {
    const rules = new Map<string, Rule>();
    for (const result of [...deviceResults].sort(bySource)) {
      rules.set(ruleKey(result), { source: result.source, matchers: result.matchers });
    }
    return { key, result: mergeDevice(deviceResults), sources: sourcesOf(deviceResults), rules: [...rules.values()] };
  });
};

export const countDevices = (results: readonly MatchResult[]): number => groupByDevice(results).length;

export const sourcesOf = (results: readonly MatchResult[]): Source[] =>
  SOURCES.filter((source) => results.some((result) => result.source === source));

const rank = (group: IntegrationGroup): number => (group.installed || group.ignored ? 1 : 0);

const compareGroups = (a: IntegrationGroup, b: IntegrationGroup): number =>
  rank(a) - rank(b) || a.name.toLowerCase().localeCompare(b.name.toLowerCase());

export const buildView = (results: readonly MatchResult[], options: ViewOptions): DiscoveryView => {
  const all = groupByIntegration(results)
    .map((group) => ({ ...group, ignored: options.ignored.has(group.repository_id) }))
    .sort(compareGroups);
  const visible = all
    .filter(
      (group) =>
        (options.showInstalled || !group.installed) &&
        (options.showIgnored || !group.ignored) &&
        (options.showCustom || group.marketplace),
    )
    .map((group) => ({ ...group, results: group.results.filter((result) => matchesFilter(result, options.filter)) }))
    .filter((group) => group.results.length);

  const sourceCounts = Object.fromEntries(
    SOURCES.map((source) => [source, visible.filter((group) => group.results.some((result) => result.source === source)).length]),
  ) as Record<Source, number>;

  const integrations = options.sources.size
    ? visible
        .map((group) => ({ ...group, results: group.results.filter((result) => options.sources.has(result.source)) }))
        .filter((group) => group.results.length)
    : visible;

  const counted = integrations.filter((group) => !group.ignored);
  return {
    integrations,
    sourceCounts,
    installedCount: all.filter((group) => group.installed).length,
    ignoredCount: options.ignored.size,
    customCount: all.filter((group) => !group.marketplace).length,
    availableCount: counted.filter((group) => !group.installed).length,
    deviceCount: countDevices(counted.flatMap((group) => group.results)),
  };
};
