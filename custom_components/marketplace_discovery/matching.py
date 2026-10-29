from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fnmatch import translate
from functools import lru_cache
import itertools
import logging
import re
from typing import Any, Literal

from async_upnp_client.utils import CaseInsensitiveDict

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.match import BluetoothMatcherIndex
from homeassistant.components.dhcp import async_index_integration_matchers
from homeassistant.components.ssdp.scanner import IntegrationMatchers
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

_LOGGER = logging.getLogger(__name__)

Source = Literal["bluetooth", "zeroconf", "dhcp", "ssdp"]
SOURCES: tuple[Source, ...] = ("bluetooth", "zeroconf", "dhcp", "ssdp")

BLUETOOTH_KEYS: dict[str, type] = {
    "local_name": str,
    "service_uuid": str,
    "service_data_uuid": str,
    "manufacturer_id": int,
    "manufacturer_data_start": list,
    "connectable": bool,
}
DHCP_KEYS: dict[str, type] = {"hostname": str, "macaddress": str}
ZEROCONF_KEYS = {"type", "name", "properties"}
HOMEKIT_TYPES = {"_hap._tcp.local.", "_hap._udp.local."}


@dataclass(frozen=True, slots=True)
class Match:
    repository_id: str
    source: Source
    matcher: dict[str, Any]
    device_key: str


def device_key(source: Source, info: Any) -> str:
    if source == "bluetooth":
        return info.address
    if source == "zeroconf":
        return info.name
    if source == "dhcp":
        return info.macaddress
    return info.ssdp_usn or f"{info.ssdp_st}|{info.ssdp_location}"


@lru_cache(maxsize=4096, typed=True)
def _compile_fnmatch(pattern: str) -> re.Pattern:
    return re.compile(translate(pattern))


@lru_cache(maxsize=1024, typed=True)
def _memorized_fnmatch(name: str, pattern: str) -> bool:
    return bool(_compile_fnmatch(pattern).match(name))


def _match_against_props(matcher: dict[str, str], props: Mapping[str, Any]) -> bool:
    for key, value in matcher.items():
        prop_val = props.get(key)
        if prop_val is None or not _memorized_fnmatch(prop_val.lower(), value):
            return False
    return True


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_bluetooth(matcher: Any) -> bool:
    if not isinstance(matcher, dict) or not matcher.keys() <= BLUETOOTH_KEYS.keys():
        return False
    for key, value in matcher.items():
        expected = BLUETOOTH_KEYS[key]
        if expected is int:
            if not _is_int(value):
                return False
        elif not isinstance(value, expected):
            return False
    start = matcher.get("manufacturer_data_start")
    return start is None or all(_is_int(byte) and 0 <= byte <= 255 for byte in start)


def _valid_zeroconf(matcher: Any) -> bool:
    if not isinstance(matcher, dict) or not matcher.keys() <= ZEROCONF_KEYS:
        return False
    if not isinstance(service_type := matcher.get("type"), str):
        return False
    if service_type in HOMEKIT_TYPES:
        return False
    if "name" in matcher and not isinstance(matcher["name"], str):
        return False
    properties = matcher.get("properties", {})
    return isinstance(properties, dict) and all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in properties.items()
    )


def _valid_dhcp(matcher: Any) -> bool:
    return (
        isinstance(matcher, dict)
        and bool(matcher)
        and matcher.keys() <= DHCP_KEYS.keys()
        and all(isinstance(value, str) for value in matcher.values())
    )


def _valid_ssdp(matcher: Any) -> bool:
    return (
        isinstance(matcher, dict)
        and bool(matcher)
        and all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in matcher.items()
        )
    )


def _entries(
    integrations: Mapping[str, Mapping[str, Any]], source: Source
) -> Iterable[tuple[str, Any]]:
    for repository_id, integration in integrations.items():
        if not isinstance(integration, Mapping):
            continue
        matchers = integration.get(source)
        if not isinstance(matchers, list):
            continue
        for matcher in matchers:
            yield repository_id, matcher


class MarketplaceMatchers:
    def __init__(self, integrations: Mapping[str, Mapping[str, Any]]) -> None:
        self._bluetooth_index = BluetoothMatcherIndex()
        self._bluetooth_origin: dict[int, tuple[str, dict[str, Any]]] = {}
        self._zeroconf: dict[str, list[tuple[str, dict[str, Any], dict[str, Any]]]] = {}
        self._dhcp_origin: dict[int, tuple[str, dict[str, Any]]] = {}
        self._ssdp = IntegrationMatchers()
        self._ssdp_origin: dict[str, tuple[str, dict[str, Any]]] = {}
        self.skipped = 0

        self._setup_bluetooth(integrations)
        self._setup_zeroconf(integrations)
        self._setup_dhcp(integrations)
        self._setup_ssdp(integrations)
        if self.skipped:
            _LOGGER.debug("Skipped %s malformed matchers", self.skipped)

    @property
    def zeroconf_types(self) -> set[str]:
        return set(self._zeroconf)

    def _setup_bluetooth(self, integrations: Mapping[str, Mapping[str, Any]]) -> None:
        for repository_id, matcher in _entries(integrations, "bluetooth"):
            if not _valid_bluetooth(matcher):
                self.skipped += 1
                continue
            indexed = {**matcher, "domain": repository_id}
            try:
                added = self._bluetooth_index.add(indexed)
            except ValueError:
                added = False
            if not added:
                self.skipped += 1
                continue
            self._bluetooth_origin[id(indexed)] = (repository_id, matcher)
        self._bluetooth_index.build()

    def _setup_zeroconf(self, integrations: Mapping[str, Mapping[str, Any]]) -> None:
        for repository_id, matcher in _entries(integrations, "zeroconf"):
            if not _valid_zeroconf(matcher):
                self.skipped += 1
                continue
            core_matcher = {"domain": repository_id}
            core_matcher.update(
                (key, value) for key, value in matcher.items() if key != "type"
            )
            self._zeroconf.setdefault(matcher["type"], []).append(
                (repository_id, core_matcher, matcher)
            )

    def _setup_dhcp(self, integrations: Mapping[str, Mapping[str, Any]]) -> None:
        indexed_matchers: list[Any] = []
        for repository_id, matcher in _entries(integrations, "dhcp"):
            if not _valid_dhcp(matcher):
                self.skipped += 1
                continue
            indexed = {"domain": repository_id, **matcher}
            indexed_matchers.append(indexed)
            self._dhcp_origin[id(indexed)] = (repository_id, matcher)
        self._dhcp = async_index_integration_matchers(indexed_matchers)

    def _setup_ssdp(self, integrations: Mapping[str, Mapping[str, Any]]) -> None:
        by_key: dict[str, list[dict[str, str]]] = {}
        for repository_id, matcher in _entries(integrations, "ssdp"):
            if not _valid_ssdp(matcher):
                self.skipped += 1
                continue
            key = str(len(by_key))
            by_key[key] = [matcher]
            self._ssdp_origin[key] = (repository_id, matcher)
        self._ssdp.async_setup(by_key)

    def match_bluetooth(
        self, infos: Iterable[BluetoothServiceInfoBleak]
    ) -> list[Match]:
        results: list[Match] = []
        for info in infos:
            key = device_key("bluetooth", info)
            for indexed in self._bluetooth_index.match(info):
                repository_id, matcher = self._bluetooth_origin[id(indexed)]
                results.append(Match(repository_id, "bluetooth", matcher, key))
        return results

    def match_zeroconf(self, infos: Iterable[ZeroconfServiceInfo]) -> list[Match]:
        results: list[Match] = []
        for info in infos:
            if not (entries := self._zeroconf.get(info.type)):
                continue
            key = device_key("zeroconf", info)
            for repository_id, core_matcher, matcher in entries:
                if len(core_matcher) > 1:
                    if "name" in core_matcher and not _memorized_fnmatch(
                        info.name.lower(), core_matcher["name"]
                    ):
                        continue
                    if "properties" in core_matcher and not _match_against_props(
                        core_matcher["properties"], info.properties
                    ):
                        continue
                results.append(Match(repository_id, "zeroconf", matcher, key))
        return results

    def match_dhcp(self, infos: Iterable[DhcpServiceInfo]) -> list[Match]:
        results: list[Match] = []
        for info in infos:
            lowercase_hostname = info.hostname.lower()
            oui = info.macaddress.upper()[:6]
            first_char = lowercase_hostname[0] if lowercase_hostname else ""
            key = device_key("dhcp", info)
            for indexed in itertools.chain(
                self._dhcp.no_oui_matchers.get(first_char, ()),
                self._dhcp.oui_matchers.get(oui, ()),
            ):
                if (
                    hostname := indexed.get("hostname")
                ) is not None and not _memorized_fnmatch(lowercase_hostname, hostname):
                    continue
                repository_id, matcher = self._dhcp_origin[id(indexed)]
                results.append(Match(repository_id, "dhcp", matcher, key))
        return results

    def match_ssdp(self, infos: Iterable[SsdpServiceInfo]) -> list[Match]:
        results: list[Match] = []
        for info in infos:
            headers = info.ssdp_headers
            if isinstance(headers, CaseInsensitiveDict):
                headers = headers.as_dict()
            combined = CaseInsensitiveDict({**headers, **info.upnp})
            key = device_key("ssdp", info)
            for matched in sorted(self._ssdp.async_matching_domains(combined), key=int):
                repository_id, matcher = self._ssdp_origin[matched]
                results.append(Match(repository_id, "ssdp", matcher, key))
        return results
