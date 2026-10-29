from collections.abc import Generator
import copy
from typing import Any
from unittest.mock import patch

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]

DATASET: dict[str, Any] = {
    "version": 1,
    "generated_at": "2026-10-29T03:00:00+00:00",
    "stats": {"repositories": 3, "manifests": 3, "with_matchers": 3},
    "integrations": {
        "100": {
            "full_name": "acme/acme-lights",
            "domain": "acme_lights",
            "name": "Acme Lights",
            "ref": "v1.0.0",
            "stars": 2108,
            "last_updated": "2026-10-20T08:00:00Z",
            "description": "Control Acme lights locally.",
            "bluetooth": [{"manufacturer_id": 1234, "manufacturer_data_start": [1, 2]}],
            "dhcp": [{"hostname": "acme-*"}],
        },
        "200": {
            "full_name": "zed/zed-purifier",
            "domain": "zed_purifier",
            "name": "Zed Purifier",
            "ref": "v2.0.0",
            "zeroconf": [{"type": "_zed._tcp.local."}],
            "ssdp": [{"manufacturer": "Zed Inc."}],
        },
        "300": {
            "full_name": "other/already-here",
            "domain": "already_here",
            "name": "already here",
            "ref": "v0.1.0",
            "dhcp": [{"hostname": "acme-*"}],
        },
    },
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    return


@pytest.fixture
def dataset_payload() -> dict[str, Any]:
    return copy.deepcopy(DATASET)


@pytest.fixture
def no_refresh_wait() -> Generator[None]:
    with patch("custom_components.marketplace_discovery.sources.REFRESH_SECONDS", 0):
        yield
