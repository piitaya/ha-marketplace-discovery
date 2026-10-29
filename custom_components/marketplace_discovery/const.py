from datetime import timedelta
from typing import Final

DOMAIN: Final = "marketplace_discovery"

DATASET_URL: Final = "https://piitaya.github.io/ha-marketplace-discovery/matchers.json"
DATASET_VERSION: Final = 1
UPDATE_INTERVAL: Final = timedelta(hours=24)
STORAGE_KEY: Final = f"{DOMAIN}.dataset"
STORAGE_VERSION: Final = 1
IGNORED_STORAGE_KEY: Final = f"{DOMAIN}.ignored"
IGNORED_STORAGE_VERSION: Final = 1

REFRESH_SECONDS: Final = 10
ZEROCONF_REQUEST_TIMEOUT_MS: Final = 3000

PANEL_URL_PATH: Final = "marketplace-discovery"
PANEL_COMPONENT: Final = "marketplace-discovery-panel"
PANEL_STATIC_URL: Final = "/marketplace_discovery_static"
PANEL_TITLE: Final = "Marketplace discovery"
PANEL_ICON: Final = "mdi:store-search"
