import { describeDevice, matchesFilter, SOURCES } from "./format.ts";
import type { MatchDevice, MatchResult, Matcher, Source } from "./types.ts";

export interface IntegrationGroup {
  repository_id: string;
  name: string;
  full_name: string;
  domain: string;
  installed: boolean;
  ignored: boolean;
  stars: number | null;
  last_updated: string | null;
  description: string | null;
  results: MatchResult[];
}

export interface RuleGroup {
  key: string;
  source: Source;
  matchers: Matcher[];
  results: MatchResult[];
}

export interface PreviewEntry {
  name: string | null;
  count: number;
}

export interface ViewOptions {
  filter: string;
  sources: ReadonlySet<Source>;
  showInstalled: boolean;
  showIgnored: boolean;
  ignored: ReadonlySet<string>;
}

export interface DiscoveryView {
  integrations: IntegrationGroup[];
  sourceCounts: Record<Source, number>;
  installedCount: number;
  ignoredCount: number;
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

export const groupByRule = (results: readonly MatchResult[]): RuleGroup[] => {
  const groups = new Map<string, RuleGroup>();
  for (const result of results) {
    const key = ruleKey(result);
    const group = groups.get(key);
    if (group) {
      group.results.push(result);
    } else {
      groups.set(key, { key, source: result.source, matchers: result.matchers, results: [result] });
    }
  }
  return [...groups.values()].sort((a, b) => SOURCES.indexOf(a.source) - SOURCES.indexOf(b.source));
};

export const deviceKey = (device: MatchDevice): string | null => {
  const id = device.ip || device.mac || device.name;
  return id ? id.toLowerCase() : null;
};

export const countDevices = (results: readonly MatchResult[]): number => {
  const keys = new Set<string>();
  let unnamed = 0;
  for (const result of results) {
    const key = deviceKey(result.device);
    if (key === null) {
      unnamed += 1;
    } else {
      keys.add(key);
    }
  }
  return keys.size + unnamed;
};

export const devicePreview = (results: readonly MatchResult[]): PreviewEntry[] => {
  const seen = new Set<string>();
  const entries = new Map<string | null, PreviewEntry>();
  for (const rule of groupByRule(results)) {
    for (const result of rule.results) {
      const key = deviceKey(result.device);
      if (key !== null) {
        if (seen.has(key)) {
          continue;
        }
        seen.add(key);
      }
      const { name } = describeDevice(result);
      const entry = entries.get(name);
      if (entry) {
        entry.count += 1;
      } else {
        entries.set(name, { name, count: 1 });
      }
    }
  }
  return [...entries.values()];
};

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
    .filter((group) => (options.showInstalled || !group.installed) && (options.showIgnored || !group.ignored))
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
    availableCount: counted.filter((group) => !group.installed).length,
    deviceCount: countDevices(counted.flatMap((group) => group.results)),
  };
};
