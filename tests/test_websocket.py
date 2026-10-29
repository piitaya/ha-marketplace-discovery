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
from custom_components.marketplace_discovery.const import (
    DATASET_URL,
    DOMAIN,
    IGNORED_STORAGE_KEY,
)
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


async def send_command(
    hass_ws_client: WebSocketGenerator, hass: HomeAssistant, command: str, **kwargs: Any
) -> dict[str, Any]:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": f"marketplace_discovery/{command}", **kwargs}
    )
    return await client.receive_json()


async def send(
    hass_ws_client: WebSocketGenerator, hass: HomeAssistant, **kwargs: Any
) -> dict[str, Any]:
    return await send_command(hass_ws_client, hass, "matches", **kwargs)


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
        "stars": 2108,
        "last_updated": "2026-10-20T08:00:00Z",
        "description": "Control Acme lights locally.",
        "installed": False,
        "ignored": False,
        "marketplace": True,
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
    assert zeroconf["stars"] is None
    assert zeroconf["last_updated"] is None
    assert zeroconf["description"] is None
    assert result["ignored"] == []


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


def stored(repository_ids: Any) -> dict[str, Any]:
    return {
        "version": 1,
        "minor_version": 1,
        "key": IGNORED_STORAGE_KEY,
        "data": {"repository_ids": repository_ids},
    }


@pytest.mark.usefixtures("config_entry")
async def test_ignore_and_unignore(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    collectors: dict[str, MagicMock],
) -> None:
    with patch.object(sources, "async_refresh", AsyncMock()) as refresh:
        msg = await send_command(
            hass_ws_client, hass, "ignore", repository_ids=["300", "200", "300"]
        )
        assert msg["success"]
        assert msg["result"] == {"ignored": ["200", "300"]}
        assert hass_storage[IGNORED_STORAGE_KEY]["data"] == {
            "repository_ids": ["200", "300"]
        }

        msg = await send_command(
            hass_ws_client, hass, "unignore", repository_ids=["300", "999"]
        )
        assert msg["success"]
        assert msg["result"] == {"ignored": ["200"]}
        assert hass_storage[IGNORED_STORAGE_KEY]["data"] == {"repository_ids": ["200"]}

    refresh.assert_not_awaited()
    for collector in collectors.values():
        collector.assert_not_called()


async def test_ignored_survives_reload(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_entry: MockConfigEntry,
) -> None:
    msg = await send_command(hass_ws_client, hass, "ignore", repository_ids=["200"])
    assert msg["success"]

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.ignored.repository_ids == {"200"}


@pytest.mark.usefixtures("collectors")
async def test_matches_with_stored_ignore_list(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    hass_storage[IGNORED_STORAGE_KEY] = stored(["999", "200"])
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    MockConfigEntry(domain="already_here").add_to_hass(hass)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    msg = await send(hass_ws_client, hass)
    assert msg["success"]
    result = msg["result"]
    assert result["ignored"] == ["200", "999"]
    assert [
        (r["repository_id"], r["source"], r["installed"], r["ignored"])
        for r in result["results"]
    ] == [
        ("100", "bluetooth", False, False),
        ("100", "dhcp", False, False),
        ("300", "dhcp", True, False),
        ("200", "ssdp", False, True),
        ("200", "zeroconf", False, True),
    ]


@pytest.mark.parametrize(
    "repository_ids", [None, "200", ["200", 5], {"200": True}], ids=repr
)
async def test_invalid_stored_ignore_list(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    repository_ids: Any,
) -> None:
    hass_storage[IGNORED_STORAGE_KEY] = stored(repository_ids)
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    expected = {"200"} if isinstance(repository_ids, list) else set()
    assert entry.runtime_data.ignored.repository_ids == expected


@pytest.mark.usefixtures("collectors")
async def test_matches_ignores_malformed_dataset_fields(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    dataset_payload["integrations"]["100"] |= {
        "stars": True,
        "last_updated": 1792686716,
        "description": ["not", "text"],
    }
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    msg = await send(hass_ws_client, hass)
    result = next(r for r in msg["result"]["results"] if r["repository_id"] == "100")
    assert result["stars"] is None
    assert result["last_updated"] is None
    assert result["description"] is None


@pytest.mark.usefixtures("config_entry")
@pytest.mark.parametrize("command", ["ignore", "unignore"])
async def test_ignore_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    hass_storage: dict[str, Any],
    command: str,
) -> None:
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id(
        {"type": f"marketplace_discovery/{command}", "repository_ids": ["200"]}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"
    assert IGNORED_STORAGE_KEY not in hass_storage


@pytest.mark.parametrize("command", ["ignore", "unignore"])
async def test_ignore_not_loaded(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, command: str
) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    msg = await send_command(hass_ws_client, hass, command, repository_ids=["200"])
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


@pytest.mark.usefixtures("config_entry")
@pytest.mark.parametrize("repository_ids", ["200", [200], None])
async def test_ignore_invalid_request(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, repository_ids: Any
) -> None:
    msg = await send_command(
        hass_ws_client, hass, "ignore", repository_ids=repository_ids
    )
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"


async def test_matches_marks_custom_repositories(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    collectors: dict[str, MagicMock],
) -> None:
    dataset_payload["integrations"]["200"]["marketplace"] = False
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    msg = await send(hass_ws_client, hass)
    assert msg["result"]["dataset"]["integrations"] == 2
    assert msg["result"]["dataset"]["custom_integrations"] == 1
    marketplace = {
        r["repository_id"]: r["marketplace"] for r in msg["result"]["results"]
    }
    assert marketplace == {"100": True, "200": False, "300": True}
