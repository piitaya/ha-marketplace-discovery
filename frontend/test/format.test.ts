import assert from "node:assert/strict";
import { test } from "node:test";
import { describeDevice, formatMatcher, matchesFilter } from "../src/format.ts";
import type { MatchResult } from "../src/types.ts";

const result: MatchResult = {
  repository_id: "123456",
  full_name: "owner/xiaomi-x",
  domain: "xiaomi_x",
  name: "Xiaomi X",
  installed: false,
  source: "zeroconf",
  matchers: [{ type: "_miio._udp.local.", name: "zhimi*" }],
  device: { name: "zhimi-airpurifier", ip: "192.168.1.20", mac: null },
  discovery: {},
};

test("formats matchers per source", () => {
  assert.equal(formatMatcher("zeroconf", { type: "_miio._udp.local." }), "zeroconf: _miio._udp.local.");
  assert.equal(
    formatMatcher("zeroconf", { name: "shelly*", type: "_http._tcp.local.", properties: { model: "abc*" } }),
    "zeroconf: _http._tcp.local., name=shelly*, properties.model=abc*",
  );
  assert.equal(
    formatMatcher("bluetooth", { manufacturer_id: 1234, manufacturer_data_start: [1, 2] }),
    "bluetooth: manufacturer_id=1234, manufacturer_data_start=[1,2]",
  );
  assert.equal(formatMatcher("bluetooth", { local_name: "LED*", connectable: false }), "bluetooth: local_name=LED*, connectable=false");
  assert.equal(formatMatcher("dhcp", { hostname: "foo*" }), "dhcp: hostname=foo*");
  assert.equal(formatMatcher("ssdp", { manufacturer: "Acme" }), "ssdp: manufacturer=Acme");
});

test("describes a device with a fallback name", () => {
  assert.deepEqual(describeDevice({ name: "plug", ip: "10.0.0.2", mac: null }), { name: "plug", address: "10.0.0.2" });
  assert.deepEqual(describeDevice({ name: null, ip: null, mac: "aa:bb:cc:dd:ee:ff" }), {
    name: "aa:bb:cc:dd:ee:ff",
    address: null,
  });
  assert.deepEqual(describeDevice({ name: null, ip: null, mac: null }), { name: "Unknown device", address: null });
});

test("filters on name, device and matcher text", () => {
  assert.ok(matchesFilter(result, ""));
  assert.ok(matchesFilter(result, "xiaomi"));
  assert.ok(matchesFilter(result, "OWNER/xiaomi"));
  assert.ok(matchesFilter(result, "192.168.1.20"));
  assert.ok(matchesFilter(result, "_miio zhimi*"));
  assert.ok(!matchesFilter(result, "shelly"));
});
