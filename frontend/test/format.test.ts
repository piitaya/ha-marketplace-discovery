import assert from "node:assert/strict";
import { test } from "node:test";
import { brandIconUrl, describeDevice, formatMatcher, matchesFilter } from "../src/format.ts";
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

test("describes a device with its addresses", () => {
  assert.deepEqual(describeDevice(result), { name: "zhimi-airpurifier", details: ["192.168.1.20"] });
  assert.deepEqual(
    describeDevice({ ...result, source: "dhcp", device: { name: "plug", ip: "10.0.0.2", mac: "aa:bb:cc:dd:ee:ff" } }),
    { name: "plug", details: ["10.0.0.2", "aa:bb:cc:dd:ee:ff"] },
  );
  assert.deepEqual(describeDevice({ ...result, device: { name: null, ip: "10.0.0.3", mac: null } }), {
    name: "10.0.0.3",
    details: [],
  });
  assert.deepEqual(describeDevice({ ...result, device: { name: null, ip: null, mac: null } }), {
    name: null,
    details: [],
  });
});

test("adds the signal strength of Bluetooth devices", () => {
  const bluetooth: MatchResult = {
    ...result,
    source: "bluetooth",
    device: { name: "Apple device", ip: null, mac: "0D:64:A6:5E:D0:AB" },
    discovery: { rssi: -48 },
  };
  assert.deepEqual(describeDevice(bluetooth), { name: "Apple device", details: ["0D:64:A6:5E:D0:AB", "-48 dBm"] });
  assert.deepEqual(describeDevice({ ...bluetooth, discovery: {} }).details, ["0D:64:A6:5E:D0:AB"]);
  assert.deepEqual(describeDevice({ ...bluetooth, source: "dhcp" }).details, ["0D:64:A6:5E:D0:AB"]);
});

test("filters on name, device and matcher text", () => {
  assert.ok(matchesFilter(result, ""));
  assert.ok(matchesFilter(result, "xiaomi"));
  assert.ok(matchesFilter(result, "OWNER/xiaomi"));
  assert.ok(matchesFilter(result, "xiaomi_x"));
  assert.ok(matchesFilter(result, "192.168.1.20"));
  assert.ok(matchesFilter(result, "_miio zhimi*"));
  assert.ok(!matchesFilter(result, "shelly"));
});

test("builds brand icon links only with a token", () => {
  assert.equal(brandIconUrl("bermuda", undefined, false), undefined);
  assert.equal(brandIconUrl("bermuda", "abc", false), "/api/brands/marketplace/bermuda/icon.png?token=abc");
  assert.equal(brandIconUrl("bermuda", "a b", true), "/api/brands/marketplace/bermuda/dark_icon.png?token=a%20b");
});
