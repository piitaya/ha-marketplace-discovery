import { describeDevice } from "./format.ts";
import type { MatchResult } from "./types.ts";

export const REPORT_ISSUE_URL = "https://github.com/piitaya/ha-marketplace-discovery/issues/new";
export const MAX_REPORT_URL_LENGTH = 6000;

const MAX_TITLE_LENGTH = 200;
const CUT_MARKER = "\n... (cut)";
const DISCOVERY_CUT_NOTE = "The discovery data was cut to keep this link short.";
const BOTH_CUT_NOTE = "The matchers and the discovery data were cut to keep this link short.";

const cut = (text: string, length: number): string => {
  let end = Math.min(length, text.length);
  const last = text.charCodeAt(end - 1);
  if (end > 0 && end < text.length && last >= 0xd800 && last <= 0xdbff) {
    end -= 1;
  }
  return text.slice(0, end);
};

const issueUrl = (title: string, body: string): string =>
  `${REPORT_ISSUE_URL}?${new URLSearchParams({ title, body }).toString()}`;

const fitsInUrl = (url: string, maxLength: number): boolean => url.length < maxLength;

const longestFit = (text: string, toUrl: (part: string) => string, maxLength: number): string | null => {
  if (fitsInUrl(toUrl(text), maxLength)) {
    return text;
  }
  let low = 0;
  let high = text.length - 1;
  let best: string | null = null;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    const candidate = cut(text, middle) + CUT_MARKER;
    if (fitsInUrl(toUrl(candidate), maxLength)) {
      best = candidate;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return best;
};

export const reportTitle = (result: MatchResult): string =>
  cut(`False positive: ${result.name} (${result.source})`, MAX_TITLE_LENGTH);

export const reportBody = (
  result: MatchResult,
  haVersion: string,
  matchersJson: string,
  discoveryJson: string,
  note: string | null,
): string => {
  const device = describeDevice(result.device);
  return [
    "**What is this device, and why should this integration not match it?**",
    "",
    "",
    "",
    "**Details**",
    "",
    `- Repository: [${result.full_name}](https://github.com/${result.full_name})`,
    `- Repository id: ${result.repository_id}`,
    `- Domain: \`${result.domain}\``,
    `- Source: ${result.source}`,
    `- Device: ${device.address ? `${device.name} (${device.address})` : device.name}`,
    `- Home Assistant: ${haVersion}`,
    "",
    "**Matched by**",
    "",
    "```json",
    matchersJson,
    "```",
    "",
    "**Discovery data**",
    "",
    "```json",
    discoveryJson,
    "```",
    ...(note ? ["", `_${note}_`] : []),
    "",
  ].join("\n");
};

export const buildReportUrl = (
  result: MatchResult,
  haVersion: string,
  maxLength: number = MAX_REPORT_URL_LENGTH,
): string => {
  const title = reportTitle(result);
  const matchersJson = JSON.stringify(result.matchers, null, 2);
  const discoveryJson = JSON.stringify(result.discovery, null, 2);

  const full = issueUrl(title, reportBody(result, haVersion, matchersJson, discoveryJson, null));
  if (fitsInUrl(full, maxLength)) {
    return full;
  }

  const discovery = longestFit(
    discoveryJson,
    (part) => issueUrl(title, reportBody(result, haVersion, matchersJson, part, DISCOVERY_CUT_NOTE)),
    maxLength,
  );
  if (discovery !== null) {
    return issueUrl(title, reportBody(result, haVersion, matchersJson, discovery, DISCOVERY_CUT_NOTE));
  }

  const emptyDiscovery = CUT_MARKER.trimStart();
  const matchers = longestFit(
    matchersJson,
    (part) => issueUrl(title, reportBody(result, haVersion, part, emptyDiscovery, BOTH_CUT_NOTE)),
    maxLength,
  );
  if (matchers !== null) {
    return issueUrl(title, reportBody(result, haVersion, matchers, emptyDiscovery, BOTH_CUT_NOTE));
  }

  return issueUrl(title, BOTH_CUT_NOTE);
};
