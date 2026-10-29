import assert from "node:assert/strict";
import { test } from "node:test";
import { buildReportUrl, MAX_REPORT_URL_LENGTH, REPORT_ISSUE_URL } from "../src/report.ts";
import type { MatchResult } from "../src/types.ts";

const result = (discovery: Record<string, unknown>, matchers: Record<string, unknown>[] = [{ hostname: "foo*" }]): MatchResult => ({
  repository_id: "42",
  full_name: "owner/repo",
  domain: "foo",
  name: "Foo",
  installed: false,
  source: "dhcp",
  matchers,
  device: { name: "foo-1", ip: "10.0.0.5", mac: "aa:bb:cc:dd:ee:ff" },
  discovery,
});

const parse = (url: string) => {
  const parsed = new URL(url);
  return { base: `${parsed.origin}${parsed.pathname}`, title: parsed.searchParams.get("title"), body: parsed.searchParams.get("body") ?? "" };
};

test("builds a prefilled issue link", () => {
  const url = buildReportUrl(result({ hostname: "foo-1", ip: "10.0.0.5", macaddress: "aabbccddeeff" }), "2026.10.4");
  const { base, title, body } = parse(url);
  assert.equal(base, REPORT_ISSUE_URL);
  assert.equal(title, "False positive: Foo (dhcp)");
  assert.match(body, /https:\/\/github\.com\/owner\/repo/);
  assert.match(body, /Home Assistant: 2026\.10\.4/);
  assert.match(body, /"hostname": "foo\*"/);
  assert.match(body, /"macaddress": "aabbccddeeff"/);
  assert.doesNotMatch(body, /cut to keep this link short/);
});

test("cuts the discovery data first to stay under the limit", () => {
  const url = buildReportUrl(result({ blob: "x\n".repeat(5000) }), "2026.10.4");
  assert.ok(url.length < MAX_REPORT_URL_LENGTH);
  const { body } = parse(url);
  assert.match(body, /"hostname": "foo\*"/);
  assert.match(body, /\.\.\. \(cut\)/);
  assert.match(body, /The discovery data was cut/);
});

test("cuts the matchers when the discovery data alone is not enough", () => {
  const matchers = Array.from({ length: 300 }, (_, index) => ({ hostname: `device-${index}-*` }));
  const url = buildReportUrl(result({ blob: "y".repeat(3000) }, matchers), "2026.10.4");
  assert.ok(url.length < MAX_REPORT_URL_LENGTH);
  const { body } = parse(url);
  assert.match(body, /device-0-\*/);
  assert.doesNotMatch(body, /yyyy/);
  assert.match(body, /The matchers and the discovery data were cut/);
});

test("keeps unicode valid when cutting", () => {
  const url = buildReportUrl(result({ name: "\u{1F600}".repeat(4000) }), "2026.10.4");
  assert.ok(url.length < MAX_REPORT_URL_LENGTH);
  assert.doesNotMatch(parse(url).body, /�/);
});
