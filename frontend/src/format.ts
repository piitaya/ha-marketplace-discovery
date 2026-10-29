import type { MatchDevice, MatchResult, Matcher, Source } from "./types.ts";

export const SOURCES: readonly Source[] = ["bluetooth", "zeroconf", "dhcp", "ssdp"];

export const SOURCE_LABELS: Record<Source, string> = {
  bluetooth: "Bluetooth",
  zeroconf: "Zeroconf",
  dhcp: "DHCP",
  ssdp: "SSDP",
};

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export const formatValue = (value: unknown): string => {
  if (typeof value === "string") {
    return value;
  }
  if (value === undefined) {
    return "undefined";
  }
  if (typeof value === "number" || typeof value === "boolean" || value === null) {
    return String(value);
  }
  return JSON.stringify(value);
};

export const formatMatcher = (source: Source, matcher: Matcher): string => {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(matcher)) {
    if (source === "zeroconf" && key === "type" && typeof value === "string") {
      parts.unshift(value);
    } else if (source === "zeroconf" && key === "properties" && isPlainObject(value)) {
      for (const [propKey, propValue] of Object.entries(value)) {
        parts.push(`properties.${propKey}=${formatValue(propValue)}`);
      }
    } else {
      parts.push(`${key}=${formatValue(value)}`);
    }
  }
  return `${source}: ${parts.join(", ")}`;
};

export interface DeviceSummary {
  name: string;
  address: string | null;
}

export const describeDevice = (device: MatchDevice): DeviceSummary => {
  const address = device.ip || device.mac || null;
  const name = device.name || address || "Unknown device";
  return { name, address: address === name ? null : address };
};

export const searchText = (result: MatchResult): string =>
  [
    result.name,
    result.full_name,
    result.domain,
    result.device.name,
    result.device.ip,
    result.device.mac,
    ...result.matchers.map((matcher) => formatMatcher(result.source, matcher)),
  ]
    .filter((part): part is string => typeof part === "string" && part !== "")
    .join("\n")
    .toLowerCase();

export const matchesFilter = (result: MatchResult, filter: string): boolean => {
  const terms = filter.toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) {
    return true;
  }
  const text = searchText(result);
  return terms.every((term) => text.includes(term));
};
