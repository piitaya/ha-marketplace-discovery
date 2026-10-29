from collections.abc import Generator
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from async_upnp_client.utils import CaseInsensitiveDict
from bleak.backends.device import BLEDevice
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.marketplace_discovery import sources
from custom_components.marketplace_discovery.const import DATASET_URL, DOMAIN
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component

BLUETOOTH = BluetoothServiceInfoBleak(
    name="Acme BLE",
    address="AA:BB:CC:DD:EE:01",
    rssi=-61,
    manufacturer_data={1234: b"\x01\x02\x03"},
    service_data={"0000fcd2-0000-1000-8000-00805f9b34fb": b"\x40"},
    service_uuids=["0000fcd2-0000-1000-8000-00805f9b34fb"],
    source="hci0",
    device=BLEDevice("AA:BB:CC:DD:EE:01", "Acme BLE", None),
    advertisement=None,
    connectable=True,
    time=0,
    tx_power=None,
)
ZEROCONF = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.20"),
    ip_addresses=[ip_address("192.168.1.20")],
    port=54321,
    hostname="zed-1.local.",
    type="_zed._tcp.local.",
    name="zed-1._zed._tcp.local.",
    properties={"md": "z1", "empty": None},
)
DHCP = DhcpServiceInfo(
    ip="192.168.1.30", hostname="acme-plug", macaddress="aabbccddeeff"
)
SSDP = SsdpServiceInfo(
    ssdp_usn="uuid:zed::upnp:rootdevice",
    ssdp_st="upnp:rootdevice",
    ssdp_location="http://192.168.1.40:49152/description.xml",
    ssdp_server="Linux UPnP/1.0",
    ssdp_headers=CaseInsensitiveDict(
        {
            "st": "upnp:rootdevice",
            "usn": "uuid:zed::upnp:rootdevice",
            "location": "http://192.168.1.40:49152/description.xml",
        }
    ),
    upnp={
        "manufacturer": "Zed Inc.",
        "friendlyName": "Zed Purifier 2",
        "serviceList": {"service": []},
    },
)


@pytest.fixture
def collectors() -> Generator[dict[str, MagicMock]]:
    with (
        patch.object(
            sources, "async_collect_bluetooth", return_value=[BLUETOOTH]
        ) as bluetooth,
        patch.object(
            sources, "async_collect_zeroconf", AsyncMock(return_value=[ZEROCONF])
        ) as zeroconf,
        patch.object(sources, "async_collect_dhcp", return_value=[DHCP]) as dhcp,
        patch.object(
            sources, "async_collect_ssdp", AsyncMock(return_value=[SSDP])
        ) as ssdp,
    ):
        yield {"bluetooth": bluetooth, "zeroconf": zeroconf, "dhcp": dhcp, "ssdp": ssdp}


@pytest.fixture
async def config_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> MockConfigEntry:
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    MockConfigEntry(domain="already_here").add_to_hass(hass)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def send(
    hass_ws_client: WebSocketGenerator, hass: HomeAssistant, **kwargs: Any
) -> dict[str, Any]:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "marketplace_discovery/matches", **kwargs})
    return await client.receive_json()


@pytest.mark.usefixtures("config_entry")
async def test_matches(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    collectors: dict[str, MagicMock],
) -> None:
    hass.config.components.add("dhcp")
    msg = await send(hass_ws_client, hass)

    assert msg["success"]
    result = msg["result"]
    assert result["dataset"]["generated_at"] == "2026-10-29T03:00:00+00:00"
    assert result["dataset"]["integrations"] == 3
    assert result["sources"] == {
        "bluetooth": False,
        "zeroconf": False,
        "dhcp": True,
        "ssdp": False,
    }
    collectors["zeroconf"].assert_awaited_once_with(hass, {"_zed._tcp.local."})

    assert [(r["repository_id"], r["source"]) for r in result["results"]] == [
        ("100", "bluetooth"),
        ("100", "dhcp"),
        ("200", "ssdp"),
        ("200", "zeroconf"),
        ("300", "dhcp"),
    ]
    bluetooth, dhcp, ssdp, zeroconf, installed = result["results"]
    assert bluetooth == {
        "repository_id": "100",
        "full_name": "acme/acme-lights",
        "domain": "acme_lights",
        "name": "Acme Lights",
        "installed": False,
        "source": "bluetooth",
        "matchers": [{"manufacturer_id": 1234, "manufacturer_data_start": [1, 2]}],
        "device": {"name": "Acme BLE", "ip": None, "mac": "AA:BB:CC:DD:EE:01"},
        "discovery": {
            "name": "Acme BLE",
            "address": "AA:BB:CC:DD:EE:01",
            "rssi": -61,
            "source": "hci0",
            "connectable": True,
            "manufacturer_data": {"1234": "010203"},
            "service_data": {"0000fcd2-0000-1000-8000-00805f9b34fb": "40"},
            "service_uuids": ["0000fcd2-0000-1000-8000-00805f9b34fb"],
        },
    }
    assert dhcp["device"] == {
        "name": "acme-plug",
        "ip": "192.168.1.30",
        "mac": "aa:bb:cc:dd:ee:ff",
    }
    assert dhcp["discovery"] == {
        "hostname": "acme-plug",
        "ip": "192.168.1.30",
        "macaddress": "aabbccddeeff",
    }
    assert dhcp["matchers"] == [{"hostname": "acme-*"}]
    assert zeroconf["device"] == {"name": "zed-1", "ip": "192.168.1.20", "mac": None}
    assert zeroconf["discovery"] == {
        "name": "zed-1._zed._tcp.local.",
        "type": "_zed._tcp.local.",
        "hostname": "zed-1.local.",
        "ip_address": "192.168.1.20",
        "port": 54321,
        "properties": {"md": "z1", "empty": None},
    }
    assert ssdp["device"] == {
        "name": "Zed Purifier 2",
        "ip": "192.168.1.40",
        "mac": None,
    }
    assert ssdp["discovery"] == {
        "ssdp_st": "upnp:rootdevice",
        "ssdp_nt": None,
        "ssdp_usn": "uuid:zed::upnp:rootdevice",
        "ssdp_location": "http://192.168.1.40:49152/description.xml",
        "ssdp_server": "Linux UPnP/1.0",
        "upnp": {"manufacturer": "Zed Inc.", "friendlyName": "Zed Purifier 2"},
    }
    assert installed["installed"] is True
    assert installed["name"] == "already here"


async def test_matches_groups_matchers_per_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    collectors: dict[str, MagicMock],
) -> None:
    dataset_payload["integrations"]["100"]["dhcp"] = [
        {"hostname": "acme-*"},
        {"macaddress": "AABBCC*"},
        {"hostname": "acme-*", "macaddress": "AABBCC*"},
    ]
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    msg = await send(hass_ws_client, hass)
    results = [
        r
        for r in msg["result"]["results"]
        if r["repository_id"] == "100" and r["source"] == "dhcp"
    ]
    assert len(results) == 1
    assert sorted(map(str, results[0]["matchers"])) == sorted(
        map(str, dataset_payload["integrations"]["100"]["dhcp"])
    )


async def test_matches_both_bluetooth_histories(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    collectors: dict[str, MagicMock],
) -> None:
    passive_only = {
        "manufacturer_id": 1234,
        "manufacturer_data_start": [1, 2],
        "connectable": False,
    }
    dataset_payload["integrations"]["100"]["bluetooth"] = [
        {"manufacturer_id": 76},
        passive_only,
    ]
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    connectable = BluetoothServiceInfoBleak(
        name="Acme BLE",
        address=BLUETOOTH.address,
        rssi=-70,
        manufacturer_data={76: b"\x02"},
        service_data={},
        service_uuids=[],
        source="hci0",
        device=BLEDevice(BLUETOOTH.address, "Acme BLE", None),
        advertisement=None,
        connectable=True,
        time=0,
        tx_power=None,
    )
    passive = BluetoothServiceInfoBleak(
        name="Acme BLE",
        address=BLUETOOTH.address,
        rssi=-50,
        manufacturer_data={1234: b"\x01\x02\x03"},
        service_data={},
        service_uuids=[],
        source="proxy",
        device=BLEDevice(BLUETOOTH.address, "Acme BLE", None),
        advertisement=None,
        connectable=False,
        time=0,
        tx_power=None,
    )
    collectors["bluetooth"].return_value = [connectable, passive]

    msg = await send(hass_ws_client, hass)
    results = [r for r in msg["result"]["results"] if r["source"] == "bluetooth"]
    assert len(results) == 1
    assert results[0]["matchers"] == [{"manufacturer_id": 76}, passive_only]
    assert results[0]["discovery"]["source"] == "hci0"

    collectors["bluetooth"].return_value = [passive]
    msg = await send(hass_ws_client, hass)
    results = [r for r in msg["result"]["results"] if r["source"] == "bluetooth"]
    assert results[0]["matchers"] == [passive_only]
    assert results[0]["discovery"]["source"] == "proxy"


@pytest.mark.usefixtures("config_entry", "collectors")
async def test_installed_custom_component(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    with patch(
        "custom_components.marketplace_discovery.websocket.async_get_custom_components",
        AsyncMock(return_value={"acme_lights": MagicMock()}),
    ):
        msg = await send(hass_ws_client, hass)
    installed = {r["repository_id"]: r["installed"] for r in msg["result"]["results"]}
    assert installed == {"100": True, "200": False, "300": True}
    assert msg["result"]["results"][0]["repository_id"] == "200"


@pytest.mark.usefixtures("config_entry")
async def test_collector_failure_is_isolated(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    collectors: dict[str, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    collectors["zeroconf"].side_effect = OSError("boom")
    msg = await send(hass_ws_client, hass)
    assert msg["success"]
    assert {r["source"] for r in msg["result"]["results"]} == {
        "bluetooth",
        "dhcp",
        "ssdp",
    }
    assert "Unable to read zeroconf discovery data" in caplog.text


@pytest.mark.usefixtures("config_entry", "collectors", "no_refresh_wait")
async def test_refresh(hass: HomeAssistant, hass_ws_client: WebSocketGenerator) -> None:
    for component in ("bluetooth", "zeroconf", "ssdp"):
        hass.config.components.add(component)
    scanner = MagicMock(async_scan=AsyncMock())
    hass.data["ssdp"] = {"scanner": scanner}

    with (
        patch.object(
            sources.bluetooth, "async_request_active_scan", AsyncMock()
        ) as active_scan,
        patch.object(sources.ZeroconfBrowser, "async_restart", AsyncMock()) as restart,
    ):
        msg = await send(hass_ws_client, hass, refresh=True)

    assert msg["success"]
    assert len(msg["result"]["results"]) == 5
    active_scan.assert_awaited_once()
    restart.assert_awaited_once()
    scanner.async_scan.assert_awaited_once()


@pytest.mark.usefixtures("config_entry", "collectors", "no_refresh_wait")
async def test_refresh_without_ssdp_scanner(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    hass.config.components.add("ssdp")
    hass.data.pop("ssdp", None)
    msg = await send(hass_ws_client, hass, refresh=True)
    assert msg["success"]
    assert len(msg["result"]["results"]) == 5


@pytest.mark.usefixtures("config_entry", "collectors")
async def test_no_refresh_by_default(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    with patch.object(sources, "async_refresh", AsyncMock()) as refresh:
        msg = await send(hass_ws_client, hass)
    assert msg["success"]
    refresh.assert_not_awaited()


@pytest.mark.usefixtures("config_entry", "collectors")
async def test_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": "marketplace_discovery/matches"})
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


async def test_not_loaded(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    msg = await send(hass_ws_client, hass)
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_dataset_unavailable_then_downloaded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    collectors: dict[str, MagicMock],
) -> None:
    aioclient_mock.get(DATASET_URL, exc=aiohttp.ClientError())
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    msg = await send(hass_ws_client, hass)
    assert msg["success"]
    assert msg["result"]["dataset"] is None
    assert msg["result"]["results"] == []
    collectors["dhcp"].assert_not_called()

    aioclient_mock.clear_requests()
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    msg = await send(hass_ws_client, hass)
    assert msg["result"]["dataset"]["integrations"] == 3
    assert len(msg["result"]["results"]) == 5
