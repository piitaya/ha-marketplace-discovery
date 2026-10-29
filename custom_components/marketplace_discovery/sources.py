import asyncio
from collections.abc import Awaitable
import logging
from typing import Any, cast

from zeroconf import BadTypeInNameException, DNSPointer, service_type_name
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo

from homeassistant.components import bluetooth, dhcp, ssdp, zeroconf
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.loader import async_get_zeroconf

from .const import REFRESH_SECONDS, ZEROCONF_REQUEST_TIMEOUT_MS
from .matching import SOURCES, Source

_LOGGER = logging.getLogger(__name__)

TYPE_PTR = 12
CLASS_IN = 1

CORE_EXTRA_ZEROCONF_TYPES = {
    "_home-assistant._tcp.local.",
    "_hap._tcp.local.",
    "_hap._udp.local.",
}


@callback
def async_loaded_sources(hass: HomeAssistant) -> dict[Source, bool]:
    return {source: source in hass.config.components for source in SOURCES}


@callback
def async_collect_bluetooth(
    hass: HomeAssistant,
) -> list[bluetooth.BluetoothServiceInfoBleak]:
    if "bluetooth" not in hass.config.components:
        return []
    connectable = {
        info.address: info
        for info in bluetooth.async_discovered_service_info(hass, connectable=True)
    }
    infos = list(connectable.values())
    infos.extend(
        info
        for info in bluetooth.async_discovered_service_info(hass, connectable=False)
        if connectable.get(info.address) is not info
    )
    return infos


async def async_collect_zeroconf(
    hass: HomeAssistant, service_types: set[str]
) -> list[ZeroconfServiceInfo]:
    if "zeroconf" not in hass.config.components or not service_types:
        return []
    aiozc = await zeroconf.async_get_async_instance(hass)
    zc = aiozc.zeroconf
    loaded: dict[str, AsyncServiceInfo] = {}
    pending: dict[str, AsyncServiceInfo] = {}
    for service_type in sorted(service_types):
        for record in zc.cache.async_all_by_details(service_type, TYPE_PTR, CLASS_IN):
            if record.name != service_type:
                continue
            alias = cast(DNSPointer, record).alias
            if alias in loaded or alias in pending:
                continue
            try:
                info = AsyncServiceInfo(service_type, alias)
            except BadTypeInNameException:
                continue
            if info.load_from_cache(zc):
                loaded[alias] = info
            else:
                pending[alias] = info
    if pending:
        await asyncio.gather(
            *(
                info.async_request(zc, ZEROCONF_REQUEST_TIMEOUT_MS)
                for info in pending.values()
            )
        )
        loaded.update(pending)
    return [
        service_info
        for info in loaded.values()
        if (service_info := zeroconf.info_from_service(info))
    ]


@callback
def async_collect_dhcp(hass: HomeAssistant) -> list[DhcpServiceInfo]:
    if "dhcp" not in hass.config.components:
        return []
    return dhcp.async_discovered_service_info(hass)


async def async_collect_ssdp(hass: HomeAssistant) -> list[SsdpServiceInfo]:
    if "ssdp" not in hass.config.components:
        return []
    infos: list[SsdpServiceInfo] = []

    @callback
    def _async_collect(info: SsdpServiceInfo, _change: ssdp.SsdpChange) -> None:
        infos.append(info)

    unsubscribe = await ssdp.async_register_callback(hass, _async_collect, None)
    unsubscribe()
    return infos


def _ignore_state_change(**kwargs: Any) -> None:
    pass


def _valid_service_type(service_type: str) -> bool:
    try:
        service_type_name(service_type, strict=False)
    except BadTypeInNameException:
        return False
    return True


class ZeroconfBrowser:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._browser: AsyncServiceBrowser | None = None
        self._requested: set[str] = set()
        self.browsed_types: list[str] = []
        self._lock = asyncio.Lock()
        self._stopped = False

    async def async_start(self, service_types: set[str]) -> None:
        async with self._lock:
            if self._stopped:
                return
            self._requested = set(service_types)
            await self._async_cancel()
            if "zeroconf" not in self.hass.config.components:
                return
            core_types = set(await async_get_zeroconf(self.hass))
            types = sorted(
                service_type
                for service_type in self._requested
                - core_types
                - CORE_EXTRA_ZEROCONF_TYPES
                if _valid_service_type(service_type)
            )
            if not types:
                return
            aiozc = await zeroconf.async_get_async_instance(self.hass)
            self._browser = AsyncServiceBrowser(
                aiozc.zeroconf, types, handlers=[_ignore_state_change]
            )
            self.browsed_types = types
            _LOGGER.debug("Browsing %s zeroconf types", len(types))

    async def async_restart(self) -> None:
        await self.async_start(self._requested)

    async def async_stop(self) -> None:
        async with self._lock:
            self._stopped = True
            await self._async_cancel()

    async def _async_cancel(self) -> None:
        if self._browser is None:
            return
        browser = self._browser
        self._browser = None
        self.browsed_types = []
        await browser.async_cancel()


async def _async_ssdp_scan(hass: HomeAssistant) -> None:
    try:
        scan = hass.data["ssdp"]["scanner"].async_scan
    except KeyError, AttributeError, TypeError:
        _LOGGER.debug("SSDP scan is not available")
        return
    await scan()


async def async_refresh(hass: HomeAssistant, browser: ZeroconfBrowser) -> None:
    loop = asyncio.get_running_loop()
    start = loop.time()
    tasks: dict[str, Awaitable[None]] = {}
    if "bluetooth" in hass.config.components:
        tasks["bluetooth"] = bluetooth.async_request_active_scan(hass, REFRESH_SECONDS)
    if "zeroconf" in hass.config.components:
        tasks["zeroconf"] = browser.async_restart()
    if "ssdp" in hass.config.components:
        tasks["ssdp"] = _async_ssdp_scan(hass)
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for name, result in zip(tasks, results, strict=True):
        if isinstance(result, Exception):
            _LOGGER.debug("Refreshing %s failed: %s", name, result)
    if (remaining := REFRESH_SECONDS - (loop.time() - start)) > 0:
        await asyncio.sleep(remaining)
