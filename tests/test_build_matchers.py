from collections import Counter
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "build_matchers.py"


@pytest.fixture(scope="module")
def builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_matchers", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CATALOG_ITEM: dict[str, Any] = {
    "description": "Home Assistant integration for Bermuda BLE trilateration. ",
    "domain": "bermuda",
    "downloads": 1,
    "full_name": "agittins/bermuda",
    "last_commit": "1a2b3c4",
    "last_updated": "2026-10-20T08:12:00Z",
    "last_version": "v0.8.0",
    "manifest_name": "Bermuda BLE Trilateration",
    "stargazers_count": 2108,
    "topics": ["bluetooth"],
}
MANIFEST = {
    "domain": "bermuda",
    "name": "Bermuda BLE Trilateration",
    "bluetooth": [{"connectable": False, "manufacturer_id": 76}, {"bad": 1}],
}


def test_build_integration(builder: ModuleType) -> None:
    dropped: Counter[str] = Counter()
    entries = builder.catalog_entries({"123": CATALOG_ITEM}, dropped)
    integration = builder.build_integration(entries["123"], MANIFEST, dropped)
    assert integration == {
        "full_name": "agittins/bermuda",
        "domain": "bermuda",
        "name": "Bermuda BLE Trilateration",
        "ref": "v0.8.0",
        "stars": 2108,
        "last_updated": "2026-10-20T08:12:00Z",
        "description": "Home Assistant integration for Bermuda BLE trilateration.",
        "bluetooth": [{"connectable": False, "manufacturer_id": 76}],
    }
    assert dropped == {"bluetooth_invalid": 1}


@pytest.mark.parametrize(
    "missing",
    [
        {},
        {"stargazers_count": None, "last_updated": None, "description": None},
        {"stargazers_count": "12", "last_updated": 5, "description": "  "},
        {"stargazers_count": True, "last_updated": "", "description": ["x"]},
        {"stargazers_count": -1},
    ],
)
def test_build_integration_without_metadata(
    builder: ModuleType, missing: dict[str, Any]
) -> None:
    item = {
        key: value
        for key, value in CATALOG_ITEM.items()
        if key not in ("stargazers_count", "last_updated", "description")
    } | missing
    dropped: Counter[str] = Counter()
    entries = builder.catalog_entries({"123": item}, dropped)
    integration = builder.build_integration(entries["123"], MANIFEST, dropped)
    assert integration["stars"] is None
    assert integration["last_updated"] is None
    assert integration["description"] is None


def test_build_integration_without_matchers(builder: ModuleType) -> None:
    dropped: Counter[str] = Counter()
    entries = builder.catalog_entries({"123": CATALOG_ITEM}, dropped)
    manifest = {"domain": "bermuda", "name": "Bermuda", "bluetooth": [{"bad": 1}]}
    assert builder.build_integration(entries["123"], manifest, dropped) is None


def test_custom_integrations(builder: ModuleType) -> None:
    data = {
        "repositories": {
            "1": {
                "full_name": "acme/acme-ble",
                "ref": "abc123",
                "stars": 4,
                "last_updated": "2026-10-01T00:00:00Z",
                "description": " Acme BLE ",
                "manifest": {
                    "domain": "acme_ble",
                    "name": "Acme BLE",
                    "bluetooth": [{"local_name": "Acme*"}],
                },
            },
            "2": {
                "full_name": "agittins/bermuda",
                "manifest": {
                    "domain": "bermuda",
                    "bluetooth": [{"manufacturer_id": 76}],
                },
            },
            "3": {"full_name": "bad name", "manifest": {"domain": "x"}},
            "5": {
                "full_name": "other/bermuda-fork",
                "manifest": {
                    "domain": "bermuda",
                    "bluetooth": [{"manufacturer_id": 76}],
                },
            },
            "4": {
                "full_name": "acme/no-matchers",
                "manifest": {"domain": "nothing", "bluetooth": [{"bad": 1}]},
            },
        }
    }
    dropped: Counter[str] = Counter()
    catalog = builder.catalog_entries({"2": CATALOG_ITEM}, Counter())
    integrations = builder.custom_integrations(data, catalog, dropped)
    assert integrations == {
        "1": {
            "full_name": "acme/acme-ble",
            "domain": "acme_ble",
            "name": "Acme BLE",
            "ref": "abc123",
            "stars": 4,
            "last_updated": "2026-10-01T00:00:00Z",
            "description": "Acme BLE",
            "bluetooth": [{"local_name": "Acme*"}],
            "marketplace": False,
        }
    }
    assert dropped == {
        "repository_invalid": 1,
        "marketplace_domain": 1,
        "bluetooth_invalid": 1,
    }


def test_custom_integrations_requires_repositories(builder: ModuleType) -> None:
    with pytest.raises(SystemExit):
        builder.custom_integrations({}, {}, Counter())


def test_custom_integrations_keeps_one_repo_per_domain(builder: ModuleType) -> None:
    def repo(name: str, stars: int, updated: str) -> dict[str, Any]:
        return {
            "full_name": f"{name}/govee",
            "stars": stars,
            "last_updated": updated,
            "manifest": {
                "domain": "govee_ble",
                "bluetooth": [{"local_name": "Govee*"}],
            },
        }

    data = {
        "repositories": {
            "10": repo("small", 1, "2026-10-01T00:00:00Z"),
            "11": repo("popular", 136, "2025-01-01T00:00:00Z"),
            "12": repo("recent", 1, "2026-10-20T00:00:00Z"),
        }
    }
    dropped: Counter[str] = Counter()
    integrations = builder.custom_integrations(data, {}, dropped)
    assert list(integrations) == ["11"]
    assert dropped == {"duplicate_domain": 2}

    data["repositories"]["11"]["stars"] = 1
    assert list(builder.custom_integrations(data, {}, Counter())) == ["12"]
