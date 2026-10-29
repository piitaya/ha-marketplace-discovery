import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import Any, NotRequired, TypedDict

import aiohttp

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DATASET_URL,
    DATASET_VERSION,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)
from .matching import MarketplaceMatchers

_LOGGER = logging.getLogger(__name__)

FETCH_TIMEOUT = aiohttp.ClientTimeout(total=60)


class StoredDataset(TypedDict):
    fetched_at: str
    data: dict[str, Any]
    etag: NotRequired[str | None]


class DatasetError(Exception):
    pass


def validate_dataset(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise DatasetError("Dataset is not an object")
    if data.get("version") != DATASET_VERSION:
        raise DatasetError(f"Unsupported dataset version: {data.get('version')}")
    integrations = data.get("integrations")
    if not isinstance(integrations, dict):
        raise DatasetError("Dataset has no integrations")
    return data


async def async_remove_cache(hass: HomeAssistant) -> None:
    await Store(hass, STORAGE_VERSION, STORAGE_KEY).async_remove()


class Dataset:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[StoredDataset] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] | None = None
        self.fetched_at: datetime | None = None
        self.etag: str | None = None
        self.matchers = MarketplaceMatchers({})
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsub_interval: CALLBACK_TYPE | None = None
        self._update_task: asyncio.Task[bool] | None = None

    @property
    def integrations(self) -> dict[str, Any]:
        if self.data is None:
            return {}
        return self.data["integrations"]

    @property
    def meta(self) -> dict[str, Any] | None:
        if self.data is None or self.fetched_at is None:
            return None
        return {
            "generated_at": self.data.get("generated_at"),
            "fetched_at": self.fetched_at.isoformat(),
            "integrations": len(self.integrations),
        }

    async def async_setup(self) -> None:
        await self._async_load_cache()
        if self.fetched_at is None:
            await self.async_update()
        else:
            self._update_task = self.hass.async_create_background_task(
                self.async_update(), "marketplace_discovery dataset update"
            )
        self._unsub_interval = async_track_time_interval(
            self.hass,
            self._async_scheduled_update,
            UPDATE_INTERVAL,
            name="marketplace_discovery dataset update",
        )

    @callback
    def async_shutdown(self) -> None:
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        if self._update_task:
            self._update_task.cancel()
            self._update_task = None

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    async def _async_load_cache(self) -> None:
        stored = await self._store.async_load()
        if not stored:
            return
        try:
            data = validate_dataset(stored.get("data"))
            fetched_at = dt_util.parse_datetime(stored["fetched_at"])
        except (DatasetError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Ignoring cached dataset: %s", err)
            return
        if fetched_at is None:
            return
        etag = stored.get("etag")
        self.etag = etag if isinstance(etag, str) else None
        self._apply(data, fetched_at)

    async def _async_scheduled_update(self, _now: datetime) -> None:
        await self.async_update()

    async def async_update_if_older(self, max_age: timedelta) -> None:
        if self.fetched_at is None or dt_util.utcnow() - self.fetched_at >= max_age:
            await self.async_update()

    async def async_update(self) -> bool:
        try:
            data, etag = await self._async_fetch()
        except DatasetError as err:
            if self.data is None:
                _LOGGER.warning("Unable to download the matcher dataset: %s", err)
            else:
                _LOGGER.warning(
                    "Unable to download the matcher dataset, using the cached copy: %s",
                    err,
                )
            return False
        fetched_at = dt_util.utcnow()
        if data is None:
            data = self.data
            etag = self.etag
        await self._store.async_save(
            {"fetched_at": fetched_at.isoformat(), "data": data, "etag": etag}
        )
        changed = data != self.data
        self.etag = etag
        self._apply(data, fetched_at)
        if changed:
            for listener in list(self._listeners):
                listener()
        return True

    async def _async_fetch(self) -> tuple[dict[str, Any] | None, str | None]:
        session = async_get_clientsession(self.hass)
        headers = (
            {"If-None-Match": self.etag} if self.etag and self.data is not None else {}
        )
        try:
            async with session.get(
                DATASET_URL, headers=headers, timeout=FETCH_TIMEOUT
            ) as response:
                if response.status == HTTPStatus.NOT_MODIFIED:
                    return None, self.etag
                response.raise_for_status()
                data = await response.json(content_type=None)
                etag = response.headers.get("ETag")
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise DatasetError(str(err) or type(err).__name__) from err
        return validate_dataset(data), etag

    def _apply(self, data: dict[str, Any], fetched_at: datetime) -> None:
        self.data = data
        self.fetched_at = fetched_at
        self.matchers = MarketplaceMatchers(data["integrations"])
