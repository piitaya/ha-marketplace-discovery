from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import panel, websocket
from .const import DOMAIN
from .dataset import Dataset, async_remove_cache
from .sources import ZeroconfBrowser

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass(slots=True)
class MarketplaceDiscoveryData:
    dataset: Dataset
    browser: ZeroconfBrowser


type MarketplaceDiscoveryConfigEntry = ConfigEntry[MarketplaceDiscoveryData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    websocket.async_setup(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MarketplaceDiscoveryConfigEntry
) -> bool:
    dataset = Dataset(hass)
    await dataset.async_setup()
    entry.async_on_unload(dataset.async_shutdown)

    browser = ZeroconfBrowser(hass)
    entry.async_on_unload(browser.async_stop)
    entry.runtime_data = MarketplaceDiscoveryData(dataset=dataset, browser=browser)
    await browser.async_start(dataset.matchers.zeroconf_types)

    @callback
    def _async_dataset_changed() -> None:
        entry.async_create_background_task(
            hass,
            browser.async_start(dataset.matchers.zeroconf_types),
            "marketplace_discovery zeroconf browser",
        )

    entry.async_on_unload(dataset.async_add_listener(_async_dataset_changed))

    await panel.async_register_panel(hass)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MarketplaceDiscoveryConfigEntry
) -> bool:
    panel.async_unregister_panel(hass)
    return True


async def async_remove_entry(
    hass: HomeAssistant, entry: MarketplaceDiscoveryConfigEntry
) -> None:
    await async_remove_cache(hass)
