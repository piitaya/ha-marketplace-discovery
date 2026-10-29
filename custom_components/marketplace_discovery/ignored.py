from collections.abc import Iterable
from typing import TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import IGNORED_STORAGE_KEY, IGNORED_STORAGE_VERSION


class StoredIgnored(TypedDict):
    repository_ids: list[str]


def _store(hass: HomeAssistant) -> Store[StoredIgnored]:
    return Store(hass, IGNORED_STORAGE_VERSION, IGNORED_STORAGE_KEY)


async def async_remove_ignored(hass: HomeAssistant) -> None:
    await _store(hass).async_remove()


class IgnoredRepositories:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = _store(hass)
        self.repository_ids: set[str] = set()

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return
        repository_ids = stored.get("repository_ids")
        if isinstance(repository_ids, list):
            self.repository_ids = {
                repository_id
                for repository_id in repository_ids
                if isinstance(repository_id, str)
            }

    @property
    def sorted_ids(self) -> list[str]:
        return sorted(self.repository_ids)

    async def async_add(self, repository_ids: Iterable[str]) -> None:
        self.repository_ids.update(repository_ids)
        await self._async_save()

    async def async_remove(self, repository_ids: Iterable[str]) -> None:
        self.repository_ids.difference_update(repository_ids)
        await self._async_save()

    async def _async_save(self) -> None:
        await self._store.async_save({"repository_ids": self.sorted_ids})
