from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.marketplace_discovery import sources
from custom_components.marketplace_discovery.const import (
    DATASET_URL,
    DOMAIN,
    PANEL_STATIC_URL,
    PANEL_URL_PATH,
    STORAGE_KEY,
)
from homeassistant.components.frontend import DATA_PANELS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Marketplace Discovery")
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_browser(hass: HomeAssistant) -> Generator[MagicMock]:
    hass.config.components.add("zeroconf")
    browser_cls = MagicMock()
    browser_cls.return_value.async_cancel = AsyncMock()
    with (
        patch.object(
            sources.zeroconf,
            "async_get_async_instance",
            AsyncMock(return_value=MagicMock()),
        ),
        patch.object(
            sources,
            "async_get_zeroconf",
            AsyncMock(return_value={"_core._tcp.local.": []}),
        ),
        patch.object(sources, "AsyncServiceBrowser", browser_cls),
    ):
        yield browser_cls


async def test_setup_and_unload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    config_entry: MockConfigEntry,
) -> None:
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    panel = hass.data[DATA_PANELS][PANEL_URL_PATH]
    assert panel.require_admin
    assert panel.sidebar_title == "Marketplace discovery"
    assert panel.sidebar_icon == "mdi:store-search"
    assert panel.config["_panel_custom"]["name"] == "marketplace-discovery-panel"
    assert panel.config["_panel_custom"]["embed_iframe"] is False
    assert panel.config["_panel_custom"]["module_url"] == (
        f"{PANEL_STATIC_URL}/panel.js?v=0.1.0"
    )
    assert config_entry.runtime_data.dataset.data == dataset_payload

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert PANEL_URL_PATH not in hass.data[DATA_PANELS]


async def test_static_path_registered_once(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    config_entry: MockConfigEntry,
) -> None:
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    assert await async_setup_component(hass, "http", {})
    with patch.object(
        hass.http,
        "async_register_static_paths",
        wraps=hass.http.async_register_static_paths,
    ) as register:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert PANEL_URL_PATH in hass.data[DATA_PANELS]
    configs = [
        config
        for call in register.call_args_list
        for config in call.args[0]
        if config.url_path == PANEL_STATIC_URL
    ]
    assert len(configs) == 1
    config = configs[0]
    assert config.url_path == PANEL_STATIC_URL
    assert config.path.endswith("custom_components/marketplace_discovery/frontend")
    assert config.cache_headers is False


async def test_setup_offline_without_cache(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    aioclient_mock.get(DATASET_URL, exc=aiohttp.ClientError())
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.dataset.data is None
    assert PANEL_URL_PATH in hass.data[DATA_PANELS]


async def test_zeroconf_browser_follows_dataset(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    config_entry: MockConfigEntry,
    mock_browser: MagicMock,
) -> None:
    dataset_payload["integrations"]["100"]["zeroconf"] = [{"type": "_core._tcp.local."}]
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_browser.assert_called_once()
    assert mock_browser.call_args.args[1] == ["_zed._tcp.local."]

    dataset_payload["integrations"]["300"]["zeroconf"] = [{"type": "_new._udp.local."}]
    aioclient_mock.clear_requests()
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    assert await config_entry.runtime_data.dataset.async_update()
    await hass.async_block_till_done()

    assert mock_browser.call_count == 2
    assert mock_browser.call_args.args[1] == ["_new._udp.local.", "_zed._tcp.local."]
    mock_browser.return_value.async_cancel.assert_awaited_once()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_browser.return_value.async_cancel.await_count == 2


async def test_failed_setup_stops_browser(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    config_entry: MockConfigEntry,
    mock_browser: MagicMock,
) -> None:
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    with patch(
        "custom_components.marketplace_discovery.panel.async_register_panel",
        side_effect=ValueError("Overwriting panel"),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_browser.assert_called_once()
    mock_browser.return_value.async_cancel.assert_awaited_once()


async def test_remove_entry_deletes_cache(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    dataset_payload: dict[str, Any],
    config_entry: MockConfigEntry,
) -> None:
    aioclient_mock.get(DATASET_URL, json=dataset_payload)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert STORAGE_KEY in hass_storage

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert STORAGE_KEY not in hass_storage
