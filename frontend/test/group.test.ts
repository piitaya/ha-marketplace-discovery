import assert from "node:assert/strict";
import { test } from "node:test";
import { buildView, countDevices, devicePreview, groupByIntegration, groupByRule, sourcesOf, type ViewOptions } from "../src/group.ts";
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

test("groups results by source and identical matchers", () => {
  const rules = groupByRule(wiim);
  assert.equal(rules.length, 3);
  assert.equal(rules[0].source, "zeroconf");
  assert.deepEqual(rules[1].results, [wiim[1], wiim[2]]);
  assert.deepEqual(rules[1].matchers, [{ st: "MediaRenderer" }]);
  assert.deepEqual(rules[2].results, [wiim[3]]);
});

test("orders rules by protocol", () => {
  const rules = groupByRule([wiim[2], wiim[0], lametric[1]]);
  assert.deepEqual(
    rules.map((rule) => rule.source),
    ["zeroconf", "dhcp", "ssdp"],
  );
});

test("ignores matcher order when grouping rules", () => {
  const first = make("a", "dhcp", { ip: "10.0.0.1" }, [{ hostname: "a*" }, { macaddress: "AA*" }]);
  const second = make("a", "dhcp", { ip: "10.0.0.2" }, [{ macaddress: "AA*" }, { hostname: "a*" }]);
  assert.equal(groupByRule([first, second]).length, 1);
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

test("previews unique devices by name with counts", () => {
  assert.deepEqual(devicePreview(lametric), [{ name: "LaMetric TIME", count: 1 }]);
  const plugs = [
    make("m", "dhcp", { name: "Plug", ip: "10.0.0.1" }),
    make("m", "dhcp", { name: "Plug", ip: "10.0.0.2" }),
    make("m", "dhcp", { name: "Door", ip: "10.0.0.3" }),
    make("m", "dhcp", {}),
  ];
  assert.deepEqual(devicePreview(plugs), [
    { name: "Plug", count: 2 },
    { name: "Door", count: 1 },
    { name: null, count: 1 },
  ]);
  assert.deepEqual(
    devicePreview(wiim).map((entry) => entry.name),
    ["WiiM Pro", "Samsung TV", "Sonos"],
  );
});
