from collections.abc import Callable, Sequence
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import probatio

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.loader import async_get_custom_components

from . import sources
from .const import DOMAIN
from .matching import SOURCES, MarketplaceMatchers, Match, Source

if TYPE_CHECKING:
    from . import MarketplaceDiscoveryData

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_matches)


def _bluetooth_device(info: Any) -> dict[str, Any]:
    return {"name": info.name, "ip": None, "mac": info.address}


def _bluetooth_discovery(info: Any) -> dict[str, Any]:
    return {
        "name": info.name,
        "address": info.address,
        "rssi": info.rssi,
        "source": info.source,
        "connectable": info.connectable,
        "manufacturer_data": {
            str(manufacturer_id): data.hex()
            for manufacturer_id, data in info.manufacturer_data.items()
        },
        "service_data": {uuid: data.hex() for uuid, data in info.service_data.items()},
        "service_uuids": list(info.service_uuids),
    }


def _zeroconf_device(info: Any) -> dict[str, Any]:
    return {
        "name": info.name.removesuffix(f".{info.type}"),
        "ip": str(info.ip_address),
        "mac": None,
    }


def _zeroconf_discovery(info: Any) -> dict[str, Any]:
    return {
        "name": info.name,
        "type": info.type,
        "hostname": info.hostname,
        "ip_address": str(info.ip_address),
        "port": info.port,
        "properties": {
            str(key): value if value is None else str(value)
            for key, value in info.properties.items()
        },
    }


def _dhcp_device(info: Any) -> dict[str, Any]:
    return {"name": info.hostname, "ip": info.ip, "mac": format_mac(info.macaddress)}


def _dhcp_discovery(info: Any) -> dict[str, Any]:
    return {"hostname": info.hostname, "ip": info.ip, "macaddress": info.macaddress}


def _ssdp_device(info: Any) -> dict[str, Any]:
    host = urlparse(info.ssdp_location).hostname if info.ssdp_location else None
    return {"name": info.upnp.get("friendlyName"), "ip": host, "mac": None}


def _ssdp_discovery(info: Any) -> dict[str, Any]:
    return {
        "ssdp_st": info.ssdp_st,
        "ssdp_nt": info.ssdp_nt,
        "ssdp_usn": info.ssdp_usn,
        "ssdp_location": info.ssdp_location,
        "ssdp_server": info.ssdp_server,
        "upnp": {
            key: value for key, value in info.upnp.items() if isinstance(value, str)
        },
    }


SERIALIZERS: dict[
    Source,
    tuple[Callable[[Any], dict[str, Any]], Callable[[Any], dict[str, Any]]],
] = {
    "bluetooth": (_bluetooth_device, _bluetooth_discovery),
    "zeroconf": (_zeroconf_device, _zeroconf_discovery),
    "dhcp": (_dhcp_device, _dhcp_discovery),
    "ssdp": (_ssdp_device, _ssdp_discovery),
}


async def _async_collect_source(
    hass: HomeAssistant, source: Source, matchers: MarketplaceMatchers
) -> list[Any]:
    if source == "bluetooth":
        return sources.async_collect_bluetooth(hass)
    if source == "zeroconf":
        return await sources.async_collect_zeroconf(hass, matchers.zeroconf_types)
    if source == "dhcp":
        return sources.async_collect_dhcp(hass)
    return await sources.async_collect_ssdp(hass)


async def _async_collect(
    hass: HomeAssistant, matchers: MarketplaceMatchers
) -> dict[Source, list[Any]]:
    collected: dict[Source, list[Any]] = {}
    for source in SOURCES:
        try:
            collected[source] = await _async_collect_source(hass, source, matchers)
        except Exception:
            _LOGGER.exception("Unable to read %s discovery data", source)
            collected[source] = []
    return collected


def _match(
    matchers: MarketplaceMatchers, source: Source, infos: Sequence[Any]
) -> list[Match]:
    if source == "bluetooth":
        return matchers.match_bluetooth(infos)
    if source == "zeroconf":
        return matchers.match_zeroconf(infos)
    if source == "dhcp":
        return matchers.match_dhcp(infos)
    return matchers.match_ssdp(infos)


async def _async_installed_domains(hass: HomeAssistant) -> set[str]:
    custom = await async_get_custom_components(hass)
    return set(custom) | set(hass.config_entries.async_domains())


def _sort_key(result: dict[str, Any]) -> tuple[bool, str, str]:
    return (
        result["installed"],
        (result["name"] or "").casefold(),
        (result["device"]["name"] or "").casefold(),
    )


async def async_build_results(
    hass: HomeAssistant, data: MarketplaceDiscoveryData
) -> list[dict[str, Any]]:
    dataset = data.dataset
    if dataset.data is None:
        return []
    matchers = dataset.matchers
    integrations = dataset.integrations
    installed_domains = await _async_installed_domains(hass)
    collected = await _async_collect(hass, matchers)

    grouped: dict[tuple[str, Source, str], dict[str, Any]] = {}
    for source, infos in collected.items():
        device, discovery = SERIALIZERS[source]
        for info in infos:
            for match in _match(matchers, source, [info]):
                group_key = (match.repository_id, source, match.device_key)
                if (result := grouped.get(group_key)) is None:
                    integration = integrations[match.repository_id]
                    result = grouped[group_key] = {
                        "repository_id": match.repository_id,
                        "full_name": integration.get("full_name"),
                        "domain": integration.get("domain"),
                        "name": integration.get("name") or integration.get("domain"),
                        "installed": integration.get("domain") in installed_domains,
                        "source": source,
                        "matchers": [],
                        "device": device(info),
                        "discovery": discovery(info),
                    }
                if match.matcher not in result["matchers"]:
                    result["matchers"].append(match.matcher)
    return sorted(grouped.values(), key=_sort_key)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace_discovery/matches",
        probatio.Optional("refresh", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_matches(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    if not (entries := hass.config_entries.async_loaded_entries(DOMAIN)):
        connection.send_error(
            msg["id"], "not_loaded", "Marketplace discovery is not loaded"
        )
        return
    data: MarketplaceDiscoveryData = entries[0].runtime_data
    if data.dataset.data is None:
        await data.dataset.async_update()
    if msg["refresh"]:
        await sources.async_refresh(hass, data.browser)
    connection.send_result(
        msg["id"],
        {
            "dataset": data.dataset.meta,
            "sources": sources.async_loaded_sources(hass),
            "results": await async_build_results(hass, data),
        },
    )
