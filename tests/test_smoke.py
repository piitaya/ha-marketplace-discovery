import json
from pathlib import Path
import socket
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from async_upnp_client.utils import CaseInsensitiveDict
from bleak.backends.device import BLEDevice
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator
from zeroconf import DNSCache
from zeroconf.asyncio import AsyncServiceInfo

from custom_components.marketplace_discovery import sources
from custom_components.marketplace_discovery.const import DATASET_URL, DOMAIN
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

FIXTURE = Path(__file__).parent / "fixtures" / "matchers.json"


def bluetooth(
    address: str, name: str, connectable: bool, manufacturer_id: int | None = None
) -> BluetoothServiceInfoBleak:
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-70,
        manufacturer_data={manufacturer_id: b"\x01"} if manufacturer_id else {},
        service_data={},
        service_uuids=[],
        source="hci0",
        device=BLEDevice(address, name, None),
        advertisement=None,
        connectable=connectable,
        time=0,
        tx_power=None,
    )


def zeroconf_records(service_type: str, instance: str, address: str) -> list:
    info = AsyncServiceInfo(
        service_type,
        f"{instance}.{service_type}",
        addresses=[socket.inet_aton(address)],
        port=80,
        properties={b"id": b"1"},
        server=f"{instance}.local.",
    )
    return [
        info.dns_pointer(),
        info.dns_service(),
        info.dns_text(),
        *info.dns_addresses(),
    ]


def ssdp(usn: str, st: str, upnp: dict[str, Any]) -> SsdpServiceInfo:
    location = "http://192.168.1.60/description.xml"
    return SsdpServiceInfo(
        ssdp_usn=usn,
        ssdp_st=st,
        ssdp_location=location,
        ssdp_headers=CaseInsensitiveDict({"st": st, "usn": usn, "location": location}),
        upnp=upnp,
    )


BLUETOOTH = {
    True: [
        bluetooth("AA:00:00:00:00:02", "Desky 1234", True),
        bluetooth("AA:00:00:00:00:04", "Other", True),
    ],
    False: [
        bluetooth("AA:00:00:00:00:01", "Blinds", False, 2407),
        bluetooth("AA:00:00:00:00:03", "Display", False, 9286),
    ],
}
DHCP = [
    DhcpServiceInfo(ip="192.168.1.30", hostname="TM-m30", macaddress="aabbccddeeff"),
    DhcpServiceInfo(ip="192.168.1.31", hostname="panel", macaddress="3c3178112233"),
    DhcpServiceInfo(
        ip="192.168.1.32", hostname="sunriser-1", macaddress="001122334455"
    ),
    DhcpServiceInfo(ip="192.168.1.33", hostname="printer", macaddress="001122334466"),
]
SSDP = [
    ssdp("uuid:fritz", "urn:schemas-upnp-org:device:fritzbox:1", {}),
    ssdp(
        "uuid:2n::upnp:rootdevice",
        "upnp:rootdevice",
        {"manufacturer": "2N, part of Axis group", "friendlyName": "Door"},
    ),
    ssdp(
        "uuid:isg::upnp:rootdevice",
        "upnp:rootdevice",
        {"manufacturer": "STIEBEL ELTRON", "modelURL": "http://example.com/"},
    ),
]


def zeroconf_cache() -> DNSCache:
    cache = DNSCache()
    for service_type, instance, address in (
        ("_keba-device._tcp.local.", "ap440-1", "192.168.1.40"),
        ("_mass._tcp.local.", "mass", "192.168.1.41"),
        ("_amzn-alexa._tcp.local.", "Roomba-ABC", "192.168.1.42"),
        ("_amzn-alexa._tcp.local.", "echo-1", "192.168.1.43"),
        ("_workstation._tcp.local.", "nas", "192.168.1.44"),
    ):
        cache.async_add_records(zeroconf_records(service_type, instance, address))
    return cache


async def test_real_dataset_end_to_end(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    payload = json.loads(FIXTURE.read_text())
    aioclient_mock.get(DATASET_URL, json=payload)
    MockConfigEntry(domain="sunriser").add_to_hass(hass)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.dataset.matchers.skipped == 0

    hass.config.components.update({"bluetooth", "zeroconf", "dhcp", "ssdp"})
    aiozc = SimpleNamespace(zeroconf=SimpleNamespace(cache=zeroconf_cache()))

    async def register(_hass: HomeAssistant, callback: Any, _match: Any) -> Any:
        for info in SSDP:
            callback(info, sources.ssdp.SsdpChange.ALIVE)
        return MagicMock()

    with (
        patch.object(
            sources.bluetooth,
            "async_discovered_service_info",
            side_effect=lambda _hass, connectable: BLUETOOTH[connectable],
        ),
        patch.object(sources.dhcp, "async_discovered_service_info", return_value=DHCP),
        patch.object(sources.ssdp, "async_register_callback", side_effect=register),
        patch.object(
            sources.zeroconf, "async_get_async_instance", AsyncMock(return_value=aiozc)
        ),
    ):
        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": "marketplace_discovery/matches"})
        msg = await client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["dataset"]["integrations"] == 20
    assert result["sources"] == {
        "bluetooth": True,
        "zeroconf": True,
        "dhcp": True,
        "ssdp": True,
    }
    assert [
        (r["name"], r["source"], r["device"]["name"], r["installed"])
        for r in result["results"]
    ] == [
        ("2N Intercom", "ssdp", "Door", False),
        ("Desky Standing Desk", "bluetooth", "Desky 1234", False),
        ("ESC/POS Thermal Printer", "dhcp", "TM-m30", False),
        ("Fritz!Box VPN", "ssdp", None, False),
        ("KEBA KeEnergy", "zeroconf", "ap440-1", False),
        ("Music Assistant Queue Actions", "zeroconf", "mass", False),
        ("Neo Smart Blinds Blue", "bluetooth", "Blinds", False),
        ("Qolsys Panel", "dhcp", "panel", False),
        ("Roomba (Rest980)", "zeroconf", "Roomba-ABC", False),
        ("SunRiser", "dhcp", "sunriser-1", True),
    ]
    roomba = result["results"][8]
    assert roomba["repository_id"] == "1020452819"
    assert roomba["matchers"] == [
        {"name": "roomba-*", "type": "_amzn-alexa._tcp.local."}
    ]
    assert roomba["device"]["ip"] == "192.168.1.42"
