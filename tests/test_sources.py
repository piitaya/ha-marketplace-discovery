import socket
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
import pytest
from zeroconf import DNSCache
from zeroconf.asyncio import AsyncServiceInfo

from custom_components.marketplace_discovery import sources
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo


def bluetooth_info(address: str, connectable: bool) -> BluetoothServiceInfoBleak:
    return BluetoothServiceInfoBleak(
        name="Device",
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source="hci0",
        device=BLEDevice(address, "Device", None),
        advertisement=None,
        connectable=connectable,
        time=0,
        tx_power=None,
    )


def zeroconf_records(
    service_type: str, instance: str, address: str | None, text: bool = True
) -> list:
    info = AsyncServiceInfo(
        service_type,
        f"{instance}.{service_type}",
        addresses=[socket.inet_aton(address)] if address else [],
        port=80,
        properties={b"md": b"X1"},
        server=f"{instance}.local.",
    )
    records = [info.dns_pointer(), info.dns_service()]
    if text:
        records.append(info.dns_text())
    records.extend(info.dns_addresses())
    return records


async def test_collectors_skip_unloaded_components(hass: HomeAssistant) -> None:
    assert sources.async_collect_bluetooth(hass) == []
    assert await sources.async_collect_zeroconf(hass, {"_x._tcp.local."}) == []
    assert sources.async_collect_dhcp(hass) == []
    assert await sources.async_collect_ssdp(hass) == []
    assert sources.async_loaded_sources(hass) == {
        "bluetooth": False,
        "zeroconf": False,
        "dhcp": False,
        "ssdp": False,
    }


async def test_collect_bluetooth_keeps_both_histories(hass: HomeAssistant) -> None:
    hass.config.components.add("bluetooth")
    passive = bluetooth_info("AA:AA:AA:AA:AA:01", False)
    other = bluetooth_info("AA:AA:AA:AA:AA:02", False)
    active = bluetooth_info("AA:AA:AA:AA:AA:01", True)
    shared = bluetooth_info("AA:AA:AA:AA:AA:03", True)

    def discovered(_hass: HomeAssistant, connectable: bool) -> Any:
        if connectable:
            return {"a": active, "c": shared}.values()
        return {"a": passive, "b": other, "c": shared}.values()

    with patch.object(
        sources.bluetooth, "async_discovered_service_info", side_effect=discovered
    ):
        result = sources.async_collect_bluetooth(hass)
    assert result == [active, shared, passive, other]


async def test_collect_dhcp(hass: HomeAssistant) -> None:
    hass.config.components.add("dhcp")
    info = DhcpServiceInfo(ip="192.168.1.2", hostname="plug", macaddress="aabbccddeeff")
    with patch.object(
        sources.dhcp, "async_discovered_service_info", return_value=[info]
    ):
        assert sources.async_collect_dhcp(hass) == [info]


async def test_collect_ssdp_replays_and_unsubscribes(hass: HomeAssistant) -> None:
    hass.config.components.add("ssdp")
    info = SsdpServiceInfo(ssdp_usn="uuid:1", ssdp_st="upnp:rootdevice", upnp={})
    unsubscribe = MagicMock()

    async def register(_hass: HomeAssistant, callback: Any, match_dict: Any) -> Any:
        assert match_dict is None
        callback(info, sources.ssdp.SsdpChange.ALIVE)
        return unsubscribe

    with patch.object(sources.ssdp, "async_register_callback", side_effect=register):
        assert await sources.async_collect_ssdp(hass) == [info]
    unsubscribe.assert_called_once()


async def test_collect_zeroconf_from_cache(hass: HomeAssistant) -> None:
    hass.config.components.add("zeroconf")
    cache = DNSCache()
    cache.async_add_records(
        zeroconf_records("_zed._tcp.local.", "zed-1", "192.168.1.20")
    )
    cache.async_add_records(
        zeroconf_records("_zed._tcp.local.", "zed-ll", "169.254.1.1")
    )
    cache.async_add_records(
        zeroconf_records("_Zed._tcp.local.", "zed-2", "192.168.1.21")
    )
    cache.async_add_records(
        zeroconf_records("_other._tcp.local.", "other", "192.168.1.22")
    )
    incomplete = zeroconf_records("_zed._tcp.local.", "zed-3", "192.168.1.23")[:1]
    cache.async_add_records(incomplete)
    cache.async_add_records(
        zeroconf_records("_zed._tcp.local.", "zed-4", "192.168.1.24", text=False)
    )
    aiozc = SimpleNamespace(zeroconf=SimpleNamespace(cache=cache))

    with (
        patch.object(
            sources.zeroconf, "async_get_async_instance", AsyncMock(return_value=aiozc)
        ),
        patch.object(
            AsyncServiceInfo, "async_request", AsyncMock(return_value=False)
        ) as request,
    ):
        result = await sources.async_collect_zeroconf(hass, {"_zed._tcp.local."})

    assert [info.name for info in result] == [
        "zed-1._zed._tcp.local.",
        "zed-4._zed._tcp.local.",
    ]
    assert result[0].type == "_zed._tcp.local."
    assert str(result[0].ip_address) == "192.168.1.20"
    assert result[0].properties == {"md": "X1"}
    assert str(result[1].ip_address) == "192.168.1.24"
    assert result[1].properties == {}
    assert request.await_count == 2


async def test_browser_lifecycle(hass: HomeAssistant) -> None:
    aiozc = MagicMock()
    browser_cls = MagicMock()
    browser_cls.return_value.async_cancel = AsyncMock()
    browser = sources.ZeroconfBrowser(hass)

    with (
        patch.object(
            sources.zeroconf, "async_get_async_instance", AsyncMock(return_value=aiozc)
        ),
        patch.object(
            sources,
            "async_get_zeroconf",
            AsyncMock(return_value={"_core._tcp.local.": []}),
        ),
        patch.object(sources, "AsyncServiceBrowser", browser_cls),
    ):
        await browser.async_start({"_zed._tcp.local."})
        browser_cls.assert_not_called()

        hass.config.components.add("zeroconf")
        types = {
            "_zed._tcp.local.",
            "_core._tcp.local.",
            "_home-assistant._tcp.local.",
            "bad type",
        }
        await browser.async_start(types)
        browser_cls.assert_called_once()
        assert browser_cls.call_args.args == (aiozc.zeroconf, ["_zed._tcp.local."])
        assert browser.browsed_types == ["_zed._tcp.local."]

        await browser.async_restart()
        assert browser_cls.call_count == 2
        browser_cls.return_value.async_cancel.assert_awaited_once()

        await browser.async_start({"_core._tcp.local."})
        assert browser_cls.call_count == 2
        assert browser.browsed_types == []

        await browser.async_start({"_zed._tcp.local."})
        assert browser_cls.call_count == 3

        await browser.async_stop()
        assert browser_cls.return_value.async_cancel.await_count == 3
        assert browser.browsed_types == []

        await browser.async_start({"_zed._tcp.local."})
        await browser.async_restart()
        assert browser_cls.call_count == 3
        assert browser.browsed_types == []


@pytest.mark.usefixtures("no_refresh_wait")
async def test_refresh(hass: HomeAssistant) -> None:
    for component in ("bluetooth", "zeroconf", "ssdp"):
        hass.config.components.add(component)
    scanner = MagicMock(async_scan=AsyncMock())
    hass.data["ssdp"] = {"scanner": scanner}
    browser = MagicMock(async_restart=AsyncMock())

    with patch.object(
        sources.bluetooth, "async_request_active_scan", AsyncMock()
    ) as active_scan:
        await sources.async_refresh(hass, browser)

    active_scan.assert_awaited_once_with(hass, 0)
    browser.async_restart.assert_awaited_once()
    scanner.async_scan.assert_awaited_once()


@pytest.mark.parametrize(
    "ssdp_data",
    [
        None,
        {},
        {"scanner": object()},
        {"scanner": MagicMock(async_scan=AsyncMock(side_effect=OSError))},
    ],
)
@pytest.mark.usefixtures("no_refresh_wait")
async def test_refresh_survives_failures(hass: HomeAssistant, ssdp_data: Any) -> None:
    for component in ("bluetooth", "zeroconf", "ssdp"):
        hass.config.components.add(component)
    if ssdp_data is not None:
        hass.data["ssdp"] = ssdp_data
    browser = MagicMock(async_restart=AsyncMock(side_effect=OSError))

    with patch.object(
        sources.bluetooth,
        "async_request_active_scan",
        AsyncMock(side_effect=RuntimeError),
    ):
        await sources.async_refresh(hass, browser)


async def test_refresh_waits(hass: HomeAssistant) -> None:
    with (
        patch.object(sources, "REFRESH_SECONDS", 5),
        patch.object(sources.asyncio, "sleep", AsyncMock()) as sleep,
    ):
        await sources.async_refresh(hass, MagicMock())
    assert 4 < sleep.await_args.args[0] <= 5
