import assert from "node:assert/strict";
import { test } from "node:test";
import { buildView, countDevices, groupByDevice, groupByIntegration, sourcesOf, type ViewOptions } from "../src/group.ts";
import type { MatchDevice, MatchResult, Matcher, Source } from "../src/types.ts";

const make = (
  repository_id: string,
  source: Source,
  device: Partial<MatchDevice>,
  matchers: Matcher[] = [{ hostname: "x*" }],
  installed = false,
): MatchResult => ({
  repository_id,
  full_name: `owner/${repository_id}`,
  domain: `domain_${repository_id}`,
  name: `Name ${repository_id}`,
  installed,
  source,
  matchers,
  device: { name: null, ip: null, mac: null, ...device },
  discovery: {},
});

const lametric = [
  make("lametric", "zeroconf", { name: "LaMetric TIME", ip: "192.168.1.57" }, [{ type: "_lametric-api._tcp.local." }]),
  make("lametric", "dhcp", { name: "lametric-time", ip: "192.168.1.57", mac: "50:02:91:a8:3e:11" }, [{ hostname: "lametric-*" }]),
  make("lametric", "ssdp", { name: "LaMetric TIME", ip: "192.168.1.57" }, [{ deviceType: "urn:LaMetric:1" }]),
];
const wiim = [
  make("wiim", "zeroconf", { name: "WiiM Pro", ip: "192.168.1.61" }, [{ type: "_linkplay._tcp.local." }]),
  make("wiim", "ssdp", { name: "WiiM Pro", ip: "192.168.1.61" }, [{ st: "MediaRenderer" }]),
  make("wiim", "ssdp", { name: "Samsung TV", ip: "192.168.1.80" }, [{ st: "MediaRenderer" }]),
  make("wiim", "ssdp", { name: "Sonos", ip: "192.168.1.84" }, [{ st: "MediaRenderer" }, { manufacturer: "Sonos" }]),
];
const bambu = [make("bambu", "ssdp", { name: "X1C", ip: "192.168.1.90" }, [{ st: "3dprinter" }], true)];
const results = [...lametric, ...wiim, ...bambu];

const options = (overrides: Partial<ViewOptions> = {}): ViewOptions => ({
  filter: "",
  sources: new Set(),
  showInstalled: false,
  showIgnored: false,
  showCustom: true,
  ignored: new Set(),
  ...overrides,
});

test("groups results by integration in backend order", () => {
  const groups = groupByIntegration([wiim[0], lametric[0], wiim[1], lametric[1]]);
  assert.deepEqual(
    groups.map((group) => group.repository_id),
    ["wiim", "lametric"],
  );
  assert.deepEqual(groups[0].results, [wiim[0], wiim[1]]);
  assert.equal(groups[0].name, "Name wiim");
  assert.equal(groups[0].domain, "domain_wiim");
});

test("lists each device once with every rule that found it", () => {
  const devices = groupByDevice(wiim);
  assert.deepEqual(
    devices.map((device) => device.result.device.name),
    ["WiiM Pro", "Samsung TV", "Sonos"],
  );
  assert.deepEqual(devices[0].sources, ["zeroconf", "ssdp"]);
  assert.deepEqual(
    devices[0].rules.map((rule) => rule.source),
    ["zeroconf", "ssdp"],
  );
});

test("merges a device found by two rules of the same protocol", () => {
  const scanner = [
    make("escl", "zeroconf", { name: "EcoTank", ip: "10.0.1.3" }, [{ type: "_uscan._tcp.local." }]),
    make("escl", "zeroconf", { name: "EcoTank", ip: "10.0.1.3" }, [{ type: "_uscans._tcp.local." }]),
  ];
  const devices = groupByDevice(scanner);
  assert.equal(devices.length, 1);
  assert.equal(devices[0].rules.length, 2);
});

test("merges name and addresses across protocols", () => {
  const [device] = groupByDevice([lametric[2], lametric[1], lametric[0]]);
  assert.deepEqual(device.result.device, { name: "LaMetric TIME", ip: "192.168.1.57", mac: "50:02:91:a8:3e:11" });
  assert.deepEqual(device.sources, ["zeroconf", "dhcp", "ssdp"]);
});

test("keeps unnamed devices apart", () => {
  assert.equal(groupByDevice([make("a", "ssdp", {}), make("a", "ssdp", {})]).length, 2);
});

test("counts a device seen by several protocols once", () => {
  assert.equal(countDevices(lametric), 1);
  assert.equal(countDevices(wiim), 3);
  assert.equal(countDevices([make("a", "bluetooth", { mac: "AA:BB" }), make("a", "bluetooth", { mac: "aa:bb" })]), 1);
  assert.equal(countDevices([make("a", "ssdp", {}), make("a", "ssdp", {})]), 2);
});

test("lists the protocols of an integration in a fixed order", () => {
  assert.deepEqual(sourcesOf([...lametric].reverse()), ["zeroconf", "dhcp", "ssdp"]);
});

test("builds the view with filters and counts", () => {
  const view = buildView(results, options());
  assert.deepEqual(
    view.integrations.map((group) => group.repository_id),
    ["lametric", "wiim"],
  );
  assert.equal(view.installedCount, 1);
  assert.equal(view.availableCount, 2);
  assert.equal(view.deviceCount, 4);
  assert.deepEqual(view.sourceCounts, { bluetooth: 0, zeroconf: 2, dhcp: 1, ssdp: 2 });
});

test("shows installed integrations when asked", () => {
  const view = buildView(results, options({ showInstalled: true }));
  assert.equal(view.integrations.length, 3);
  assert.equal(view.availableCount, 2);
  assert.equal(view.deviceCount, 5);
  assert.equal(view.sourceCounts.ssdp, 3);
});

test("filters by protocol without changing the protocol counts", () => {
  const view = buildView(results, options({ sources: new Set<Source>(["dhcp"]) }));
  assert.deepEqual(
    view.integrations.map((group) => group.repository_id),
    ["lametric"],
  );
  assert.deepEqual(view.integrations[0].results, [lametric[1]]);
  assert.deepEqual(view.sourceCounts, { bluetooth: 0, zeroconf: 2, dhcp: 1, ssdp: 2 });
});

test("filters devices by text and updates the counts", () => {
  const view = buildView(results, options({ filter: "samsung" }));
  assert.deepEqual(
    view.integrations.map((group) => group.repository_id),
    ["wiim"],
  );
  assert.deepEqual(view.integrations[0].results, [wiim[2]]);
  assert.equal(view.deviceCount, 1);
  assert.deepEqual(view.sourceCounts, { bluetooth: 0, zeroconf: 0, dhcp: 0, ssdp: 1 });
});

test("counts a device matched by two integrations once in the summary", () => {
  const sonos = make("sonos", "ssdp", { name: "Sonos", ip: "192.168.1.84" }, [{ manufacturer: "Sonos" }]);
  const view = buildView([...wiim, sonos], options());
  assert.equal(view.integrations.length, 2);
  assert.equal(view.deviceCount, 3);
});

test("hides ignored integrations unless asked and leaves them out of the summary", () => {
  const ignored = new Set(["wiim", "gone"]);
  const hidden = buildView(results, options({ ignored }));
  assert.deepEqual(
    hidden.integrations.map((group) => group.repository_id),
    ["lametric"],
  );
  assert.equal(hidden.ignoredCount, 2);
  assert.equal(hidden.sourceCounts.ssdp, 1);

  const shown = buildView(results, options({ ignored, showIgnored: true, showInstalled: true }));
  assert.deepEqual(
    shown.integrations.map((group) => [group.repository_id, group.ignored]),
    [
      ["lametric", false],
      ["bambu", false],
      ["wiim", true],
    ],
  );
  assert.equal(shown.availableCount, 1);
  assert.equal(shown.deviceCount, 2);
});

test("lists integrations that are not installed or ignored first, then by name", () => {
  const view = buildView([...wiim, ...bambu, ...lametric], options({ showInstalled: true, showIgnored: true, ignored: new Set(["lametric"]) }));
  assert.deepEqual(
    view.integrations.map((group) => group.repository_id),
    ["wiim", "bambu", "lametric"],
  );
});

test("keeps repository metadata on the group", () => {
  const [group] = groupByIntegration([{ ...lametric[0], stars: 6, last_updated: "2026-10-21T00:00:00Z", description: "Local" }]);
  assert.equal(group.stars, 6);
  assert.equal(group.last_updated, "2026-10-21T00:00:00Z");
  assert.equal(group.description, "Local");
  assert.equal(groupByIntegration([wiim[0]])[0].stars, null);
});

test("marks results without the marketplace field as Marketplace integrations", () => {
  const custom = { ...make("custom", "dhcp", { name: "Plug", ip: "10.0.0.9" }), marketplace: false };
  const groups = groupByIntegration([lametric[0], custom]);
  assert.deepEqual(
    groups.map((group) => [group.repository_id, group.marketplace]),
    [
      ["lametric", true],
      ["custom", false],
    ],
  );
});

test("hides custom repositories when they are turned off", () => {
  const custom = { ...make("custom", "dhcp", { name: "Plug", ip: "10.0.0.9" }), marketplace: false };
  const shown = buildView([...lametric, custom], options());
  assert.equal(shown.customCount, 1);
  assert.deepEqual(
    shown.integrations.map((group) => group.repository_id),
    ["custom", "lametric"].sort((a, b) => `Name ${a}`.localeCompare(`Name ${b}`)),
  );

  const hidden = buildView([...lametric, custom], options({ showCustom: false }));
  assert.equal(hidden.customCount, 1);
  assert.deepEqual(
    hidden.integrations.map((group) => group.repository_id),
    ["lametric"],
  );
});
