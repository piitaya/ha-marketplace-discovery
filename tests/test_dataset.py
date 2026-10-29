import asyncio
from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.marketplace_discovery.const import (
    DATASET_CUSTOM_URL,
    DATASET_URL,
    STORAGE_KEY,
    UPDATE_INTERVAL,
)
from custom_components.marketplace_discovery.dataset import Dataset
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


def store_dataset(
    hass_storage: dict[str, Any],
    data: dict[str, Any],
    age: timedelta,
    etag: str | None = None,
) -> None:
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {
            "fetched_at": (dt_util.utcnow() - age).isoformat(),
            "data": data,
            "etag": etag,
        },
    }


async def setup_dataset(hass: HomeAssistant) -> Dataset:
    dataset = Dataset(hass)
    await dataset.async_setup()
    return dataset


async def test_fetch_and_cache(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    dataset = await setup_dataset(hass)

    assert aioclient_mock.call_count == 1
    assert dataset.data == dataset_payload
    assert dataset.matchers.zeroconf_types == {"_zed._tcp.local."}
    assert dataset.meta == {
        "generated_at": "2026-10-29T03:00:00+00:00",
        "fetched_at": dataset.fetched_at.isoformat(),
        "integrations": 3,
        "custom_integrations": 0,
    }
    assert hass_storage[STORAGE_KEY]["data"]["data"] == dataset_payload
    dataset.async_shutdown()


async def test_fresh_cache_is_checked_with_etag(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    store_dataset(hass_storage, dataset_payload, timedelta(hours=1), etag='"abc"')
    aioclient_mock.get(DATASET_URL, status=HTTPStatus.NOT_MODIFIED)
    listener = MagicMock()
    dataset = Dataset(hass)
    dataset.async_add_listener(listener)
    await dataset.async_setup()
    assert dataset.data == dataset_payload
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][3] == {"If-None-Match": '"abc"'}
    assert dataset.data == dataset_payload
    assert dataset.etag == '"abc"'
    assert dt_util.utcnow() - dataset.fetched_at < timedelta(minutes=1)
    assert hass_storage[STORAGE_KEY]["data"]["etag"] == '"abc"'
    listener.assert_not_called()
    dataset.async_shutdown()


async def test_etag_is_stored_after_download(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    aioclient_mock.get(DATASET_URL, json=dataset_payload, headers={"ETag": '"v2"'})
    dataset = await setup_dataset(hass)

    assert aioclient_mock.mock_calls[0][3] == {}
    assert dataset.etag == '"v2"'
    assert hass_storage[STORAGE_KEY]["data"]["etag"] == '"v2"'
    dataset.async_shutdown()


async def test_update_if_older(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    dataset = await setup_dataset(hass)
    assert aioclient_mock.call_count == 1

    await dataset.async_update_if_older(timedelta(hours=1))
    assert aioclient_mock.call_count == 1

    dataset.fetched_at = dt_util.utcnow() - timedelta(hours=2)
    await dataset.async_update_if_older(timedelta(hours=1))
    assert aioclient_mock.call_count == 2
    dataset.async_shutdown()


async def test_stale_cache_is_refreshed(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    old = {**dataset_payload, "generated_at": "2026-10-01T03:00:00+00:00"}
    store_dataset(hass_storage, old, UPDATE_INTERVAL + timedelta(minutes=1))
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    dataset = await setup_dataset(hass)
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 1
    assert dataset.data == dataset_payload
    dataset.async_shutdown()


async def test_stale_cache_does_not_wait_for_download(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    dataset_payload: dict[str, Any],
) -> None:
    old = {**dataset_payload, "generated_at": "2026-10-01T03:00:00+00:00"}
    store_dataset(hass_storage, old, UPDATE_INTERVAL + timedelta(minutes=1))
    release = asyncio.Event()

    async def fetch() -> tuple[dict[str, Any], None]:
        await release.wait()
        return dataset_payload, None

    with patch.object(Dataset, "_async_fetch", side_effect=fetch):
        dataset = await setup_dataset(hass)
        assert dataset.data == old
        release.set()
        await hass.async_block_till_done()
    assert dataset.data == dataset_payload
    dataset.async_shutdown()


async def test_shutdown_cancels_pending_download(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    dataset_payload: dict[str, Any],
) -> None:
    store_dataset(hass_storage, dataset_payload, UPDATE_INTERVAL * 2)
    cancelled = asyncio.Event()

    async def fetch() -> tuple[dict[str, Any], None]:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        return dataset_payload, None

    with patch.object(Dataset, "_async_fetch", side_effect=fetch):
        dataset = await setup_dataset(hass)
        dataset.async_shutdown()
        await hass.async_block_till_done()
    assert cancelled.is_set()


@pytest.mark.parametrize(
    "mock_kwargs",
    [
        {"exc": aiohttp.ClientError()},
        {"exc": TimeoutError()},
        {"status": 500},
        {"text": "not json"},
    ],
)
async def test_offline_uses_cache(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    mock_kwargs: dict[str, Any],
) -> None:
    store_dataset(hass_storage, dataset_payload, UPDATE_INTERVAL * 2)
    aioclient_mock.get(DATASET_URL, **mock_kwargs)
    dataset = await setup_dataset(hass)
    await hass.async_block_till_done()

    assert dataset.data == dataset_payload
    assert "using the cached copy" in caplog.text
    dataset.async_shutdown()


async def test_offline_without_cache(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    aioclient_mock.get(DATASET_URL, exc=aiohttp.ClientError())
    dataset = await setup_dataset(hass)

    assert dataset.data is None
    assert dataset.meta is None
    assert dataset.integrations == {}
    assert dataset.matchers.zeroconf_types == set()
    assert "Unable to download the matcher dataset" in caplog.text
    dataset.async_shutdown()


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 2, "integrations": {}},
        {"integrations": {}},
        {"version": 1, "integrations": []},
        ["not", "an", "object"],
    ],
)
async def test_invalid_dataset_is_rejected(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    payload: Any,
) -> None:
    store_dataset(hass_storage, dataset_payload, UPDATE_INTERVAL * 2)
    aioclient_mock.get(DATASET_URL, json=payload)
    dataset = await setup_dataset(hass)
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 1
    assert dataset.data == dataset_payload
    dataset.async_shutdown()


async def test_invalid_cache_is_ignored(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    store_dataset(hass_storage, {"version": 99}, timedelta(hours=1))
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    dataset = await setup_dataset(hass)

    assert aioclient_mock.call_count == 1
    assert dataset.data == dataset_payload
    dataset.async_shutdown()


async def test_refresh_every_interval(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    dataset = await setup_dataset(hass)
    listener = MagicMock()
    unsubscribe = dataset.async_add_listener(listener)
    assert aioclient_mock.call_count == 1

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2
    listener.assert_not_called()

    updated = {**dataset_payload, "generated_at": "2026-10-30T03:00:00+00:00"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(DATASET_URL, json=updated)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert dataset.data == updated
    listener.assert_called_once()

    unsubscribe()
    dataset.async_shutdown()
    aioclient_mock.clear_requests()
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 0


async def test_custom_url(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    aioclient_mock.get(DATASET_CUSTOM_URL, json=dataset_payload)
    dataset = Dataset(hass, DATASET_CUSTOM_URL)
    await dataset.async_setup()

    assert aioclient_mock.call_count == 1
    assert dataset.data == dataset_payload
    assert hass_storage[STORAGE_KEY]["data"]["url"] == DATASET_CUSTOM_URL
    dataset.async_shutdown()


async def test_cache_from_other_url_is_ignored(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    store_dataset(hass_storage, dataset_payload, timedelta(hours=1), etag='"abc"')
    aioclient_mock.get(DATASET_CUSTOM_URL, exc=aiohttp.ClientError())
    dataset = Dataset(hass, DATASET_CUSTOM_URL)
    await dataset.async_setup()

    assert dataset.data is None
    assert aioclient_mock.mock_calls[0][3] == {}
    dataset.async_shutdown()


async def test_meta_counts_custom_repositories(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    dataset_payload["integrations"]["200"]["marketplace"] = False
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    dataset = await setup_dataset(hass)

    assert dataset.meta["integrations"] == 2
    assert dataset.meta["custom_integrations"] == 1
    dataset.async_shutdown()


async def test_shut_down_dataset_does_not_save(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
) -> None:
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    dataset = Dataset(hass)
    dataset.async_shutdown()

    assert not await dataset.async_update()
    assert STORAGE_KEY not in hass_storage
    assert dataset.data is None
