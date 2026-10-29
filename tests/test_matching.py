from ipaddress import ip_address
import socket
from typing import Any
from unittest.mock import MagicMock, patch

from async_upnp_client.utils import CaseInsensitiveDict
from bleak.backends.device import BLEDevice
import pytest
from zeroconf.asyncio import AsyncServiceInfo

from custom_components.marketplace_discovery.matching import (
    MarketplaceMatchers,
    Match,
    _match_against_props,
    _memorized_fnmatch,
)
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.match import IntegrationMatcher
from homeassistant.components.dhcp import WatcherBase, async_index_integration_matchers
from homeassistant.components.dhcp.models import DHCPData
from homeassistant.components.ssdp.scanner import IntegrationMatchers
from homeassistant.components.zeroconf import discovery as core_zeroconf_discovery
from homeassistant.components.zeroconf.discovery import (
    ZeroconfDiscovery,
    info_from_service,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo


def bluetooth_info(
    *,
    name: str = "Device",
    address: str = "AA:BB:CC:DD:EE:01",
    manufacturer_data: dict[int, bytes] | None = None,
    service_data: dict[str, bytes] | None = None,
    service_uuids: list[str] | None = None,
    connectable: bool = True,
) -> BluetoothServiceInfoBleak:
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data=manufacturer_data or {},
        service_data=service_data or {},
        service_uuids=service_uuids or [],
        source="hci0",
        device=BLEDevice(address, name, None),
        advertisement=None,
        connectable=connectable,
        time=0,
        tx_power=None,
    )


def zeroconf_info(
    name: str,
    service_type: str,
    properties: dict[str, Any] | None = None,
) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.20"),
        ip_addresses=[ip_address("192.168.1.20")],
        port=80,
        hostname="device.local.",
        type=service_type,
        name=name,
        properties=properties or {},
    )


def dhcp_info(hostname: str, macaddress: str) -> DhcpServiceInfo:
    return DhcpServiceInfo(ip="192.168.1.30", hostname=hostname, macaddress=macaddress)


def ssdp_info(
    headers: dict[str, str] | None = None, upnp: dict[str, Any] | None = None
) -> SsdpServiceInfo:
    headers = {
        "st": "upnp:rootdevice",
        "usn": "uuid:1234::upnp:rootdevice",
        "location": "http://192.168.1.40:80/description.xml",
        **(headers or {}),
    }
    return SsdpServiceInfo(
        ssdp_usn=headers["usn"],
        ssdp_st=headers.get("st") or headers.get("nt", ""),
        ssdp_nt=headers.get("nt"),
        ssdp_location=headers["location"],
        ssdp_headers=CaseInsensitiveDict(headers),
        upnp=upnp or {},
    )


def matchers_for(source: str, *matchers: Any) -> MarketplaceMatchers:
    return MarketplaceMatchers({"1": {"domain": "test", source: list(matchers)}})


def matched(results: list[Match]) -> list[tuple[str, dict[str, Any]]]:
    return [(result.repository_id, result.matcher) for result in results]


@pytest.mark.parametrize(
    ("matcher", "info", "expected"),
    [
        (
            {"manufacturer_id": 1234},
            bluetooth_info(manufacturer_data={1234: b"\x01"}),
            True,
        ),
        (
            {"manufacturer_id": 1234},
            bluetooth_info(manufacturer_data={4321: b"\x01"}),
            False,
        ),
        ({"manufacturer_id": 0}, bluetooth_info(manufacturer_data={0: b"\x01"}), True),
        (
            {"manufacturer_id": 1234, "manufacturer_data_start": [1, 2]},
            bluetooth_info(manufacturer_data={1234: b"\x01\x02\x03"}),
            True,
        ),
        (
            {"manufacturer_id": 1234, "manufacturer_data_start": [1, 2]},
            bluetooth_info(manufacturer_data={1234: b"\x01\x03"}),
            False,
        ),
        (
            {"manufacturer_id": 1234, "manufacturer_data_start": []},
            bluetooth_info(manufacturer_data={1234: b"\x09"}),
            True,
        ),
        (
            {"service_uuid": "0000fe95-0000-1000-8000-00805f9b34fb"},
            bluetooth_info(service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"]),
            True,
        ),
        (
            {"service_uuid": "0000FE95-0000-1000-8000-00805F9B34FB"},
            bluetooth_info(service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"]),
            False,
        ),
        (
            {"service_uuid": "fe95"},
            bluetooth_info(service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"]),
            False,
        ),
        (
            {"service_data_uuid": "0000fcd2-0000-1000-8000-00805f9b34fb"},
            bluetooth_info(
                service_data={"0000fcd2-0000-1000-8000-00805f9b34fb": b"\x40"}
            ),
            True,
        ),
        (
            {"service_data_uuid": "0000fcd2-0000-1000-8000-00805f9b34fb"},
            bluetooth_info(service_uuids=["0000fcd2-0000-1000-8000-00805f9b34fb"]),
            False,
        ),
        ({"local_name": "Govee_H5*"}, bluetooth_info(name="Govee_H5075_A1B2"), True),
        ({"local_name": "Govee_H5*"}, bluetooth_info(name="govee_h5075_a1b2"), False),
        ({"local_name": "Govee_H5075"}, bluetooth_info(name="Govee_H5075_A1B2"), False),
        ({"local_name": "Gov?e*"}, bluetooth_info(name="Govee"), True),
        (
            {
                "local_name": "Govee*",
                "service_uuid": "0000ec88-0000-1000-8000-00805f9b34fb",
            },
            bluetooth_info(name="Govee_1"),
            False,
        ),
        (
            {
                "local_name": "Govee*",
                "service_uuid": "0000ec88-0000-1000-8000-00805f9b34fb",
            },
            bluetooth_info(
                name="Govee_1", service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"]
            ),
            True,
        ),
        (
            {"manufacturer_id": 1234},
            bluetooth_info(manufacturer_data={1234: b"\x01"}, connectable=False),
            False,
        ),
        (
            {"manufacturer_id": 1234, "connectable": False},
            bluetooth_info(manufacturer_data={1234: b"\x01"}, connectable=False),
            True,
        ),
        (
            {"manufacturer_id": 1234, "connectable": False},
            bluetooth_info(manufacturer_data={1234: b"\x01"}, connectable=True),
            True,
        ),
    ],
)
def test_bluetooth(
    matcher: dict[str, Any], info: BluetoothServiceInfoBleak, expected: bool
) -> None:
    results = matchers_for("bluetooth", matcher).match_bluetooth([info])
    assert matched(results) == ([("1", matcher)] if expected else [])
    if expected:
        assert results[0].source == "bluetooth"
        assert results[0].device_key == info.address


@pytest.mark.parametrize(
    "matcher",
    [
        {"local_name": "*ovee"},
        {"local_name": "Go[vV]ee"},
        {"connectable": False},
        {"manufacturer_data_start": [1]},
        {"manufacturer_id": "1234"},
        {"manufacturer_id": True},
        {"manufacturer_id": 1234, "manufacturer_data_start": "AQ=="},
        {"manufacturer_id": 1234, "manufacturer_data_start": [256]},
        {"manufacturer_id": 1234, "domain": "acme"},
        {"service_uuid": 1234},
        "0000fe95-0000-1000-8000-00805f9b34fb",
    ],
)
def test_bluetooth_skips_matchers_core_cannot_use(matcher: Any) -> None:
    matchers = matchers_for("bluetooth", matcher)
    assert matchers.skipped == 1
    info = bluetooth_info(
        name="Govee", manufacturer_data={1234: b"\x01"}, connectable=False
    )
    assert matchers.match_bluetooth([info]) == []


def test_bluetooth_repositories_sharing_a_matcher() -> None:
    matchers = MarketplaceMatchers(
        {
            "1": {"bluetooth": [{"manufacturer_id": 76}]},
            "2": {"bluetooth": [{"manufacturer_id": 76}, {"local_name": "Dev*"}]},
        }
    )
    info = bluetooth_info(name="Device", manufacturer_data={76: b"\x02"})
    results = sorted(matched(matchers.match_bluetooth([info])), key=str)
    assert results == [
        ("1", {"manufacturer_id": 76}),
        ("2", {"local_name": "Dev*"}),
        ("2", {"manufacturer_id": 76}),
    ]


BLUETOOTH_PARITY_MATCHERS: list[dict[str, Any]] = [
    {"manufacturer_id": 76, "manufacturer_data_start": [2, 21]},
    {"manufacturer_id": 0},
    {"local_name": "Govee_*"},
    {"local_name": "Gov"},
    {"local_name": "ab?d*", "connectable": False},
    {"service_uuid": "0000fe95-0000-1000-8000-00805f9b34fb"},
    {"service_data_uuid": "0000fcd2-0000-1000-8000-00805f9b34fb", "connectable": False},
    {
        "manufacturer_id": 1234,
        "service_uuid": "0000ec88-0000-1000-8000-00805f9b34fb",
        "local_name": "LED*",
    },
]

BLUETOOTH_PARITY_INFOS = [
    bluetooth_info(name="Govee_H5075", manufacturer_data={76: b"\x02\x15\x00"}),
    bluetooth_info(name="Gov", manufacturer_data={0: b""}, connectable=False),
    bluetooth_info(name="abcd-1", connectable=False),
    bluetooth_info(name="abXd-1", connectable=True),
    bluetooth_info(
        name="LED strip",
        manufacturer_data={1234: b"\x00"},
        service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"],
    ),
    bluetooth_info(
        name="LED strip", manufacturer_data={1234: b"\x00"}, service_uuids=[]
    ),
    bluetooth_info(
        name="Sensor",
        service_data={"0000fcd2-0000-1000-8000-00805f9b34fb": b"\x40"},
        connectable=False,
    ),
    bluetooth_info(
        name="Mi",
        service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
        connectable=False,
    ),
]


@pytest.mark.parametrize("info", BLUETOOTH_PARITY_INFOS)
def test_bluetooth_parity_with_core(info: BluetoothServiceInfoBleak) -> None:
    integrations = {
        str(index): {"bluetooth": [matcher]}
        for index, matcher in enumerate(BLUETOOTH_PARITY_MATCHERS)
    }
    core = IntegrationMatcher(
        [
            {"domain": str(index), **matcher}
            for index, matcher in enumerate(BLUETOOTH_PARITY_MATCHERS)
        ]
    )
    core.async_setup()
    ours = {
        match.repository_id
        for match in MarketplaceMatchers(integrations).match_bluetooth([info])
    }
    assert ours == core.match_domains(info)


@pytest.mark.parametrize(
    ("matcher", "info", "expected"),
    [
        (
            {"type": "_amzn-wplay._tcp.local."},
            zeroconf_info(
                "Anything._amzn-wplay._tcp.local.", "_amzn-wplay._tcp.local."
            ),
            True,
        ),
        (
            {"type": "_amzn-wplay._tcp.local."},
            zeroconf_info("Anything._other._tcp.local.", "_other._tcp.local."),
            False,
        ),
        (
            {"type": "_Volumio._tcp.local."},
            zeroconf_info("volumio._volumio._tcp.local.", "_volumio._tcp.local."),
            False,
        ),
        (
            {"type": "_Volumio._tcp.local."},
            zeroconf_info("volumio._Volumio._tcp.local.", "_Volumio._tcp.local."),
            True,
        ),
        (
            {"type": "_amzn._tcp.local.", "name": "roomba-*"},
            zeroconf_info("Roomba-123._amzn._tcp.local.", "_amzn._tcp.local."),
            True,
        ),
        (
            {"type": "_amzn._tcp.local.", "name": "roomba-123"},
            zeroconf_info("Roomba-123._amzn._tcp.local.", "_amzn._tcp.local."),
            False,
        ),
        (
            {"type": "_amzn._tcp.local.", "name": "roomba-123._amzn._tcp.local."},
            zeroconf_info("Roomba-123._amzn._tcp.local.", "_amzn._tcp.local."),
            True,
        ),
        (
            {"type": "_amzn._tcp.local.", "name": "Roomba-*"},
            zeroconf_info("Roomba-123._amzn._tcp.local.", "_amzn._tcp.local."),
            False,
        ),
        (
            {"type": "_miio._udp.local.", "properties": {"md": "abc*"}},
            zeroconf_info("x._miio._udp.local.", "_miio._udp.local.", {"md": "ABC1"}),
            True,
        ),
        (
            {"type": "_miio._udp.local.", "properties": {"md": "abc*"}},
            zeroconf_info("x._miio._udp.local.", "_miio._udp.local.", {"MD": "abc1"}),
            False,
        ),
        (
            {"type": "_miio._udp.local.", "properties": {"md": "abc*"}},
            zeroconf_info("x._miio._udp.local.", "_miio._udp.local.", {"md": None}),
            False,
        ),
        (
            {"type": "_miio._udp.local.", "properties": {"md": "ABC*"}},
            zeroconf_info("x._miio._udp.local.", "_miio._udp.local.", {"md": "ABC1"}),
            False,
        ),
        (
            {"type": "_miio._udp.local.", "properties": {"md": "abc*"}},
            zeroconf_info("x._miio._udp.local.", "_miio._udp.local.", {}),
            False,
        ),
        (
            {"type": "_miio._udp.local.", "properties": {}},
            zeroconf_info("x._miio._udp.local.", "_miio._udp.local.", {}),
            True,
        ),
        (
            {
                "type": "_miio._udp.local.",
                "name": "zhimi-*",
                "properties": {"md": "abc*"},
            },
            zeroconf_info(
                "zhimi-1._miio._udp.local.", "_miio._udp.local.", {"md": "xyz"}
            ),
            False,
        ),
        (
            {
                "type": "_miio._udp.local.",
                "name": "zhimi-*",
                "properties": {"md": "abc*"},
            },
            zeroconf_info(
                "zhimi-1._miio._udp.local.", "_miio._udp.local.", {"md": "abcd"}
            ),
            True,
        ),
    ],
)
def test_zeroconf(
    matcher: dict[str, Any], info: ZeroconfServiceInfo, expected: bool
) -> None:
    results = matchers_for("zeroconf", matcher).match_zeroconf([info])
    assert matched(results) == ([("1", matcher)] if expected else [])
    if expected:
        assert results[0].device_key == info.name


@pytest.mark.parametrize(
    "matcher",
    [
        {"type": "_hap._tcp.local."},
        {"type": "_hap._udp.local.", "name": "x*"},
        {"name": "x*"},
        {"type": 12},
        {"type": "_x._tcp.local.", "name": 1},
        {"type": "_x._tcp.local.", "properties": {"md": 1}},
        {"type": "_x._tcp.local.", "properties": ["md"]},
        {"type": "_x._tcp.local.", "macaddress": "AABBCC*"},
    ],
)
def test_zeroconf_skips_unusable_matchers(matcher: Any) -> None:
    matchers = matchers_for("zeroconf", matcher)
    assert matchers.skipped == 1
    assert matchers.zeroconf_types == set()


def test_zeroconf_types() -> None:
    matchers = MarketplaceMatchers(
        {
            "1": {"zeroconf": [{"type": "_a._tcp.local."}, {"type": "_b._udp.local."}]},
            "2": {"zeroconf": [{"type": "_a._tcp.local.", "name": "x*"}]},
        }
    )
    assert matchers.zeroconf_types == {"_a._tcp.local.", "_b._udp.local."}


@pytest.mark.parametrize(
    ("name", "pattern"),
    [
        ("roomba-123._amzn._tcp.local.", "roomba-*"),
        ("roomba-123._amzn._tcp.local.", "roomba-123"),
        ("roomba-123._amzn._tcp.local.", "Roomba-*"),
        ("shelly1-abc._http._tcp.local.", "shelly*"),
        ("a.b", "a?b"),
        ("abc", "[ab]bc"),
        ("abc", "[!a]bc"),
        ("", "*"),
    ],
)
def test_zeroconf_fnmatch_parity_with_core(name: str, pattern: str) -> None:
    assert _memorized_fnmatch(name, pattern) == (
        core_zeroconf_discovery._memorized_fnmatch(name, pattern)
    )


@pytest.mark.parametrize(
    ("matcher", "props"),
    [
        ({"md": "abc*"}, {"md": "ABC1"}),
        ({"md": "abc*"}, {"MD": "abc1"}),
        ({"md": "abc*"}, {"md": None}),
        ({"md": "ABC*"}, {"md": "ABC1"}),
        ({"md": "abc*", "fw": "1.*"}, {"md": "abc", "fw": "1.2"}),
        ({"md": "abc*", "fw": "1.*"}, {"md": "abc", "fw": "2.0"}),
        ({}, {}),
    ],
)
def test_zeroconf_props_parity_with_core(
    matcher: dict[str, str], props: dict[str, str | None]
) -> None:
    assert _match_against_props(matcher, props) == (
        core_zeroconf_discovery._match_against_props(matcher, props)
    )


ZEROCONF_PARITY_INTEGRATIONS: dict[str, Any] = {
    "1": {"zeroconf": [{"type": "_amzn._tcp.local."}]},
    "2": {"zeroconf": [{"type": "_amzn._tcp.local.", "name": "roomba-*"}]},
    "3": {"zeroconf": [{"type": "_amzn._tcp.local.", "name": "Roomba-*"}]},
    "4": {"zeroconf": [{"type": "_amzn._tcp.local.", "properties": {"md": "x*"}}]},
    "5": {
        "zeroconf": [
            {"type": "_amzn._tcp.local.", "name": "*", "properties": {"fw": "1.*"}}
        ]
    },
    "6": {"zeroconf": [{"type": "_Other._tcp.local."}]},
}


@pytest.mark.parametrize(
    ("service_type", "name", "properties"),
    [
        ("_amzn._tcp.local.", "Roomba-1._amzn._tcp.local.", {b"md": b"X1"}),
        ("_amzn._tcp.local.", "iRobot._amzn._tcp.local.", {b"fw": b"1.2"}),
        ("_amzn._tcp.local.", "iRobot._amzn._tcp.local.", {b"fw": None}),
        ("_other._tcp.local.", "dev._other._tcp.local.", {}),
        ("_Other._tcp.local.", "dev._Other._tcp.local.", {}),
    ],
)
async def test_zeroconf_parity_with_core(
    hass: HomeAssistant,
    service_type: str,
    name: str,
    properties: dict[bytes, bytes | None],
) -> None:
    async_info = AsyncServiceInfo(
        service_type,
        name,
        addresses=[socket.inet_aton("192.168.1.20")],
        port=80,
        properties=properties,
        server="device.local.",
    )
    core_types: dict[str, list[Any]] = {}
    for repository_id, integration in ZEROCONF_PARITY_INTEGRATIONS.items():
        for matcher in integration["zeroconf"]:
            core_matcher = {"domain": repository_id}
            core_matcher.update((k, v) for k, v in matcher.items() if k != "type")
            core_types.setdefault(matcher["type"], []).append(core_matcher)
    core = ZeroconfDiscovery(
        hass,
        MagicMock(),
        core_types,
        {},
        {},
        AsyncServiceInfo(
            "_home-assistant._tcp.local.", "ha._home-assistant._tcp.local."
        ),
    )
    with patch.object(
        core_zeroconf_discovery.discovery_flow, "async_create_flow"
    ) as create_flow:
        core._async_process_service_update(async_info, service_type, name)
    core_domains = {call.args[1] for call in create_flow.mock_calls}

    info = info_from_service(async_info)
    assert info is not None
    ours = MarketplaceMatchers(ZEROCONF_PARITY_INTEGRATIONS).match_zeroconf([info])
    assert {match.repository_id for match in ours} == core_domains


@pytest.mark.parametrize(
    ("matcher", "info", "expected"),
    [
        ({"macaddress": "AABBCC*"}, dhcp_info("anything", "aabbccddeeff"), True),
        ({"macaddress": "AABBCC*"}, dhcp_info("anything", "aabbcdddeeff"), False),
        ({"macaddress": "AABBCCD*"}, dhcp_info("anything", "aabbcc000000"), True),
        ({"macaddress": "aabbcc*"}, dhcp_info("anything", "aabbccddeeff"), False),
        ({"macaddress": "09E29*"}, dhcp_info("anything", "09e29a000000"), False),
        ({"hostname": "acme-*"}, dhcp_info("acme-plug", "001122334455"), True),
        ({"hostname": "acme-*"}, dhcp_info("other", "001122334455"), False),
        ({"hostname": "Acme-*"}, dhcp_info("acme-plug", "001122334455"), False),
        ({"hostname": "*acme*"}, dhcp_info("my-acme-plug", "001122334455"), False),
        ({"hostname": "*acme*"}, dhcp_info("*acme", "001122334455"), True),
        ({"hostname": "acme-*"}, dhcp_info("ACME-PLUG", "001122334455"), True),
        (
            {"hostname": "acme-*", "macaddress": "AABBCC*"},
            dhcp_info("acme-plug", "aabbccddeeff"),
            True,
        ),
        (
            {"hostname": "acme-*", "macaddress": "AABBCC*"},
            dhcp_info("other", "aabbccddeeff"),
            False,
        ),
        (
            {"hostname": "acme-*", "macaddress": "AABBCC*"},
            dhcp_info("acme-plug", "001122334455"),
            False,
        ),
        (
            {"hostname": "*", "macaddress": "AABBCC*"},
            dhcp_info("", "aabbccddeeff"),
            True,
        ),
        ({"hostname": ""}, dhcp_info("", "aabbccddeeff"), False),
    ],
)
def test_dhcp(matcher: dict[str, Any], info: DhcpServiceInfo, expected: bool) -> None:
    results = matchers_for("dhcp", matcher).match_dhcp([info])
    assert matched(results) == ([("1", matcher)] if expected else [])
    if expected:
        assert results[0].device_key == info.macaddress


@pytest.mark.parametrize(
    "matcher",
    [
        {"registered_devices": True},
        {"registered_devices": False},
        {"hostname": "acme-*", "registered_devices": True},
        {"hostname": 1},
        {},
        "acme-*",
    ],
)
def test_dhcp_skips_unusable_matchers(matcher: Any) -> None:
    matchers = matchers_for("dhcp", matcher)
    assert matchers.skipped == 1
    assert matchers.match_dhcp([dhcp_info("acme-plug", "aabbccddeeff")]) == []


DHCP_PARITY_MATCHERS: list[dict[str, Any]] = [
    {"macaddress": "AABBCC*"},
    {"macaddress": "AABBCCD*"},
    {"macaddress": "aabbcc*"},
    {"macaddress": "09E29*"},
    {"hostname": "acme-*"},
    {"hostname": "Acme-*"},
    {"hostname": "*acme*"},
    {"hostname": "acme-*", "macaddress": "AABBCC*"},
    {"hostname": "*", "macaddress": "001122*"},
    {"hostname": "[ab]cme*", "macaddress": "001122*"},
]


@pytest.mark.parametrize(
    ("hostname", "macaddress"),
    [
        ("acme-plug", "aabbccddeeff"),
        ("Acme-Plug", "aabbcc000000"),
        ("other", "aabbccddeeff"),
        ("my-acme", "001122334455"),
        ("bcme-1", "001122334455"),
        ("", "001122334455"),
        ("acme-x", "09e29a000000"),
    ],
)
async def test_dhcp_parity_with_core(
    hass: HomeAssistant, hostname: str, macaddress: str
) -> None:
    core_matchers = async_index_integration_matchers(
        [
            {"domain": str(index), **matcher}
            for index, matcher in enumerate(DHCP_PARITY_MATCHERS)
        ]
    )
    watcher = WatcherBase(hass, DHCPData(integration_matchers=core_matchers))
    with patch(
        "homeassistant.components.dhcp.discovery_flow.async_create_flow"
    ) as create_flow:
        watcher.async_process_client("192.168.1.30", hostname, macaddress)
    core_domains = {call.args[1] for call in create_flow.mock_calls}

    integrations = {
        str(index): {"dhcp": [matcher]}
        for index, matcher in enumerate(DHCP_PARITY_MATCHERS)
    }
    info = dhcp_info(hostname.lower(), macaddress)
    ours = MarketplaceMatchers(integrations).match_dhcp([info])
    assert {match.repository_id for match in ours} == core_domains


@pytest.mark.parametrize(
    ("matcher", "info", "expected"),
    [
        (
            {"manufacturer": "Acme"},
            ssdp_info(upnp={"manufacturer": "Acme", "friendlyName": "Lamp"}),
            True,
        ),
        ({"manufacturer": "acme"}, ssdp_info(upnp={"manufacturer": "Acme"}), False),
        (
            {"manufacturer": "Acme*"},
            ssdp_info(upnp={"manufacturer": "Acme Inc"}),
            False,
        ),
        ({"manufacturer": "*"}, ssdp_info(upnp={"manufacturer": "Acme"}), False),
        ({"manufacturer": "*"}, ssdp_info(upnp={"manufacturer": "*"}), True),
        (
            {"st": "urn:schemas-upnp-org:device:MediaRenderer:1"},
            ssdp_info(headers={"st": "urn:schemas-upnp-org:device:MediaRenderer:1"}),
            True,
        ),
        (
            {"ST": "urn:schemas-upnp-org:device:MediaRenderer:1"},
            ssdp_info(headers={"st": "urn:schemas-upnp-org:device:MediaRenderer:1"}),
            False,
        ),
        (
            {"st": "urn:schemas-upnp-org:device:MediaRenderer:1"},
            ssdp_info(headers={"ST": "urn:schemas-upnp-org:device:MediaRenderer:1"}),
            True,
        ),
        (
            {"nt": "urn:acme:device:hub:1"},
            ssdp_info(headers={"st": "", "nt": "urn:acme:device:hub:1"}),
            True,
        ),
        (
            {"deviceType": "urn:schemas-upnp-org:device:Basic:1"},
            ssdp_info(upnp={"deviceType": "urn:schemas-upnp-org:device:Basic:1"}),
            True,
        ),
        (
            {"deviceType": "urn:schemas-upnp-org:device:Basic:1"},
            ssdp_info(upnp={"devicetype": "urn:schemas-upnp-org:device:Basic:1"}),
            True,
        ),
        (
            {"manufacturerURL": "http://acme.example"},
            ssdp_info(upnp={"manufacturerURL": "http://acme.example"}),
            True,
        ),
        ({"modelName": "Widget"}, ssdp_info(upnp={"modelName": "Widget"}), False),
        (
            {"manufacturer": "Acme", "modelname": "Widget"},
            ssdp_info(upnp={"manufacturer": "Acme", "modelName": "Widget"}),
            True,
        ),
        (
            {"manufacturer": "Acme", "modelName": "Widget"},
            ssdp_info(upnp={"manufacturer": "Acme", "modelName": "Gadget"}),
            False,
        ),
        (
            {"manufacturer": "Acme", "server": "Linux UPnP/1.0"},
            ssdp_info(
                headers={"server": "Linux UPnP/1.0"}, upnp={"manufacturer": "Acme"}
            ),
            True,
        ),
        (
            {"server": "Linux UPnP/1.0"},
            ssdp_info(headers={"server": "Linux UPnP/1.0"}),
            False,
        ),
    ],
)
def test_ssdp(matcher: dict[str, Any], info: SsdpServiceInfo, expected: bool) -> None:
    results = matchers_for("ssdp", matcher).match_ssdp([info])
    assert matched(results) == ([("1", matcher)] if expected else [])
    if expected:
        assert results[0].device_key == info.ssdp_usn


@pytest.mark.parametrize(
    "matcher", [{}, {"manufacturer": 1}, {"manufacturer": ["Acme"]}, "Acme"]
)
def test_ssdp_skips_unusable_matchers(matcher: Any) -> None:
    matchers = matchers_for("ssdp", matcher)
    assert matchers.skipped == 1
    assert matchers.match_ssdp([ssdp_info(upnp={"manufacturer": "Acme"})]) == []


def test_ssdp_description_key_named_data() -> None:
    matchers = matchers_for("ssdp", {"manufacturer": "Acme"})
    info = ssdp_info(upnp={"manufacturer": "Acme", "data": "x"})
    assert len(matchers.match_ssdp([info])) == 1


SSDP_PARITY_MATCHERS: list[dict[str, str]] = [
    {"manufacturer": "Acme"},
    {"manufacturer": "acme"},
    {"st": "urn:schemas-upnp-org:device:MediaRenderer:1"},
    {"ST": "urn:schemas-upnp-org:device:MediaRenderer:1"},
    {"manufacturer": "Acme", "modelname": "Widget"},
    {"deviceType": "urn:schemas-upnp-org:device:Basic:1", "modelName": "Gadget"},
    {"modelName": "Widget"},
    {"nt": "urn:acme:device:hub:1"},
]


@pytest.mark.parametrize(
    ("headers", "description"),
    [
        (
            {"st": "urn:schemas-upnp-org:device:MediaRenderer:1"},
            {"manufacturer": "Acme", "modelName": "Widget"},
        ),
        (
            {"st": "upnp:rootdevice"},
            {
                "deviceType": "urn:schemas-upnp-org:device:Basic:1",
                "modelName": "Gadget",
            },
        ),
        ({"st": "", "nt": "urn:acme:device:hub:1"}, {}),
        ({"st": "upnp:rootdevice", "Manufacturer": "Acme"}, {"manufacturer": "Other"}),
    ],
)
def test_ssdp_parity_with_core(
    headers: dict[str, str], description: dict[str, str]
) -> None:
    info = ssdp_info(headers=headers, upnp=description)
    core = IntegrationMatchers()
    core.async_setup(
        {str(index): [matcher] for index, matcher in enumerate(SSDP_PARITY_MATCHERS)}
    )
    core_input = CaseInsensitiveDict(info.ssdp_headers.as_dict(), **description)
    integrations = {
        str(index): {"ssdp": [matcher]}
        for index, matcher in enumerate(SSDP_PARITY_MATCHERS)
    }
    ours = MarketplaceMatchers(integrations).match_ssdp([info])
    assert {match.repository_id for match in ours} == core.async_matching_domains(
        core_input
    )


def test_malformed_integrations_are_ignored() -> None:
    matchers = MarketplaceMatchers(
        {
            "1": "not a mapping",
            "2": {"dhcp": "acme-*"},
            "3": {"dhcp": [{"hostname": "acme-*"}]},
        }
    )
    results = matchers.match_dhcp([dhcp_info("acme-plug", "aabbccddeeff")])
    assert matched(results) == [("3", {"hostname": "acme-*"})]


def test_matcher_is_the_dataset_object() -> None:
    matcher = {"manufacturer_id": 76}
    matchers = MarketplaceMatchers({"1": {"bluetooth": [matcher]}})
    info = bluetooth_info(manufacturer_data={76: b"\x01"})
    assert matchers.match_bluetooth([info])[0].matcher is matcher
