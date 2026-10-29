const APPLE = [
  ["0D:64:A6:5E:D0:AB", -48],
  ["25:AD:05:E2:C4:A3", -52],
  ["42:52:94:BC:46:49", -55],
  ["42:84:A4:99:C7:5C", -58],
  ["44:9A:DC:77:B2:D5", -61],
  ["48:B7:45:33:57:6B", -63],
  ["48:E1:5C:A6:36:3D", -64],
  ["49:34:89:24:AB:14", -66],
  ["4C:3A:91:0E:7B:22", -67],
  ["52:6E:13:F0:8A:97", -69],
  ["58:C1:2B:7D:44:E6", -70],
  ["5C:8F:E0:19:A3:72", -71],
  ["5E:11:A7:C3:90:4D", -73],
  ["60:3B:D4:82:5E:0F", -74],
  ["66:A9:17:CE:B1:58", -76],
  ["6A:F2:08:1B:5C:E3", -77],
  ["6D:12:F8:43:07:9C", -79],
  ["71:9D:4E:A2:16:B8", -81],
  ["73:E5:9A:2C:D6:81", -83],
  ["77:4B:01:BE:68:2A", -85],
  ["7B:04:C6:5F:E9:31", -87],
  ["7C:D0:63:15:F9:C4", -89],
  ["7F:28:BC:A0:3D:56", -92],
];

const integration = (repository_id, full_name, domain, name, stars, last_updated, description, installed = false, marketplace = true) => ({
  repository_id,
  full_name,
  domain,
  name,
  installed,
  ignored: false,
  marketplace,
  stars,
  last_updated,
  description,
});

const bluetooth = (base, matchers, name, address, rssi, manufacturer_data = {}) => ({
  ...base,
  source: "bluetooth",
  matchers,
  device: { name, ip: null, mac: address },
  discovery: {
    name,
    address,
    rssi,
    source: "hci0",
    connectable: false,
    manufacturer_data,
    service_data: {},
    service_uuids: [],
  },
});

const zeroconf = (base, matchers, name, type, ip, properties = {}) => ({
  ...base,
  source: "zeroconf",
  matchers,
  device: { name, ip, mac: null },
  discovery: {
    name: `${name}.${type}`,
    type,
    hostname: `${name.toLowerCase()}.local.`,
    ip_address: ip,
    port: 80,
    properties,
  },
});

const dhcp = (base, matchers, hostname, ip, mac) => ({
  ...base,
  source: "dhcp",
  matchers,
  device: { name: hostname, ip, mac },
  discovery: { hostname, ip, macaddress: mac.replaceAll(":", "") },
});

const ssdp = (base, matchers, friendlyName, ip, st, extra = {}) => ({
  ...base,
  source: "ssdp",
  matchers,
  device: { name: friendlyName, ip, mac: null },
  discovery: {
    ssdp_st: st,
    ssdp_nt: null,
    ssdp_usn: `uuid:${ip.replaceAll(".", "")}::${st}`,
    ssdp_location: `http://${ip}:49152/description.xml`,
    ssdp_server: "Linux/4.9 UPnP/1.0",
    upnp: { friendlyName, deviceType: st, ...extra },
  },
});

const bermuda = integration(
  "676091897",
  "agittins/bermuda",
  "bermuda",
  "Bermuda BLE Trilateration",
  2108,
  "2026-10-20T14:02:11Z",
  "Bermuda Bluetooth/BLE Triangulation / Trilateration for HomeAssistant",
);
const govee = integration(
  "1133923244",
  "lasswellt/govee-homeassistant",
  "govee",
  "Govee Cloud Integration",
  149,
  "2026-10-27T09:41:00Z",
  "Govee Integration for Home Assistant - A HACS custom component for Govee lights and smart devices",
);
const lametric = integration(
  "1199759176",
  "ElectroAttacks/lametric-hass-local",
  "lametric_hass_local",
  "LaMetric Local",
  6,
  "2026-10-21T18:30:00Z",
  "Local Home Assistant integration for LaMetric Time and Sky. Control your devices entirely via your local network, no cloud dependency for notifications or lighting effects.",
);
const meross = integration(
  "341500126",
  "krahabb/meross_lan",
  "meross_lan",
  "Meross LAN",
  756,
  "2026-10-26T07:12:00Z",
  "Home Assistant integration for Meross devices",
);
const roomba = integration(
  "1241238352",
  "johnnyh1975/ha_roomba_plus",
  "roomba_plus",
  "Roomba+",
  55,
  "2026-10-25T21:05:00Z",
  "Platinum-quality Home Assistant custom integration for iRobot Roomba & Braava, local MQTT, no cloud required, 100+ entities",
);
const wiim = integration(
  "989080760",
  "mjcumming/wiim",
  "wiim",
  "WiiM",
  141,
  "2026-10-29T06:00:00Z",
  "WiiM (LinkPlay) Audio Integration for Home Assistant with multiroom support",
);
const xiaomi = integration(
  "854347601",
  "XiaoMi/ha_xiaomi_home",
  "xiaomi_home",
  "Xiaomi Home",
  22265,
  "2026-09-28T03:00:00Z",
  "Xiaomi Home Integration for Home Assistant",
);
const bambu = integration(
  "588734673",
  "greghesp/ha-bambulab",
  "bambu_lab",
  "Bambu Lab",
  2400,
  "2026-09-21T12:00:00Z",
  "A Home Assistant Integration for Bambu Lab Printers",
  true,
);
const mammotion = integration(
  "679404307",
  "mikey0000/Mammotion-HA",
  "mammotion",
  "Mammotion",
  559,
  "2026-10-28T07:44:30Z",
  "Home Assistant integration for Mammotion lawn mowers",
  false,
  false,
);
const marstek = integration(
  "1012345678",
  "jaapp/ha-marstek-local-api",
  "marstek_local_api",
  "Marstek Local API",
  210,
  "2026-10-24T18:20:00Z",
  "Local API integration for Marstek home batteries (Venus, Jupiter)",
  false,
  false,
);

const MEDIA_RENDERER = "urn:schemas-upnp-org:device:MediaRenderer:1";

export const results = [
  ...APPLE.map(([address, rssi]) =>
    bluetooth(bermuda, [{ manufacturer_id: 76, connectable: false }], "Apple device", address, rssi, {
      76: "1005031c2f9a41",
    }),
  ),
  bluetooth(govee, [{ local_name: "Govee_*" }], "Govee_H5075_3A1F", "C4:7C:8D:6A:3A:1F", -61, { 60552: "00031b5a6400" }),
  bluetooth(govee, [{ local_name: "Govee_*" }], "Govee_H5179_88B2", "A4:C1:38:22:88:B2", -77, { 34817: "ec0001010a0" }),
  bluetooth(mammotion, [{ local_name: "Luba-*", service_uuid: "0000ffff-0000-1000-8000-00805f9b34fb" }], "Luba-VSNKC2MA", "E8:3C:1A:52:7F:04", -71),
  dhcp(marstek, [{ hostname: "marstek*" }], "marstek-venus-e", "192.168.1.66", "f0:9e:9e:41:2b:7a"),
  zeroconf(lametric, [{ type: "_lametric-api._tcp.local." }], "LaMetric TIME", "_lametric-api._tcp.local.", "192.168.1.57"),
  ssdp(lametric, [{ deviceType: "urn:schemas-upnp-org:device:LaMetric:1" }], "LaMetric TIME", "192.168.1.57", "urn:schemas-upnp-org:device:LaMetric:1", {
    manufacturer: "LaMetric Inc.",
    modelName: "LaMetric TIME",
  }),
  dhcp(lametric, [{ hostname: "lametric-*" }], "lametric-time", "192.168.1.57", "50:02:91:a8:3e:11"),
  dhcp(meross, [{ hostname: "*", macaddress: "48E1E9*" }], "Meross_Garage_Door", "192.168.1.75", "48:e1:e9:5b:02:d4"),
  dhcp(meross, [{ hostname: "*", macaddress: "48E1E9*" }], "Meross_Smart_Plug", "192.168.1.71", "48:e1:e9:2a:61:0c"),
  dhcp(meross, [{ hostname: "*", macaddress: "48E1E9*" }], "Meross_Smart_Plug", "192.168.1.72", "48:e1:e9:2a:7f:93"),
  zeroconf(roomba, [{ type: "_amzn-alexa._tcp.local.", name: "irobot-*" }], "iRobot-5D3F8A1C", "_amzn-alexa._tcp.local.", "192.168.1.42"),
  dhcp(roomba, [{ hostname: "irobot-*", macaddress: "501479*" }], "irobot-5d3f8a1c", "192.168.1.42", "50:14:79:8a:1c:42"),
  ssdp(wiim, [{ deviceType: MEDIA_RENDERER, st: MEDIA_RENDERER }], "[TV] Samsung Q80 Series", "192.168.1.80", MEDIA_RENDERER, {
    manufacturer: "Samsung Electronics",
    modelName: "QE65Q80T",
  }),
  ssdp(wiim, [{ deviceType: MEDIA_RENDERER, st: MEDIA_RENDERER }], "Sonos One Kitchen", "192.168.1.84", MEDIA_RENDERER, {
    manufacturer: "Sonos, Inc.",
    modelName: "Sonos One",
  }),
  zeroconf(wiim, [{ type: "_linkplay._tcp.local." }], "WiiM Pro Living Room", "_linkplay._tcp.local.", "192.168.1.61"),
  ssdp(wiim, [{ deviceType: MEDIA_RENDERER, st: MEDIA_RENDERER }], "WiiM Pro Living Room", "192.168.1.61", MEDIA_RENDERER, {
    manufacturer: "Linkplay",
    modelName: "WiiM Pro",
  }),
  zeroconf(xiaomi, [{ type: "_miot-central._tcp.local." }], "Xiaomi Central Hub Gateway", "_miot-central._tcp.local.", "192.168.1.30"),
  ssdp(bambu, [{ st: "urn:bambulab-com:device:3dprinter:1" }], "P1S Office", "192.168.1.91", "urn:bambulab-com:device:3dprinter:1"),
  ssdp(bambu, [{ st: "urn:bambulab-com:device:3dprinter:1" }], "X1C Workshop", "192.168.1.90", "urn:bambulab-com:device:3dprinter:1"),
];

const rank = (result, ignored) => (result.installed || ignored.has(result.repository_id) ? 1 : 0);

export const response = (ignored = new Set(), overrides = {}) => ({
  dataset: { generated_at: "2026-10-29T08:50:43+00:00", fetched_at: "2026-10-29T09:00:00+00:00", integrations: 442, custom_integrations: 1650 },
  sources: { bluetooth: true, zeroconf: true, dhcp: true, ssdp: true },
  results: results
    .map((result) => ({ ...result, ignored: ignored.has(result.repository_id) }))
    .sort((a, b) => rank(a, ignored) - rank(b, ignored)),
  ignored: [...ignored].sort(),
  ...overrides,
});
