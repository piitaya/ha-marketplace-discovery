#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import UTC, datetime
import http.client
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

DATASET_VERSION = 1
CACHE_VERSION = 1
DATA_URL = "https://data-v2.hacs.xyz/integration/data.json"
RAW_URL = "https://raw.githubusercontent.com/{full_name}/{ref}/{path}"
TREE_URL = "https://api.github.com/repos/{full_name}/git/trees/{ref}?recursive=1"
USER_AGENT = "marketplace-discovery-matchers"
SKIPPED_REPOSITORIES = {"hacs/integration"}
SOURCES = ("bluetooth", "zeroconf", "dhcp", "ssdp")

ATTEMPTS = 4
TIMEOUT = 30
MAX_RETRY_WAIT = 60
DATA_SIZE_LIMIT = 64_000_000
TREE_SIZE_LIMIT = 32_000_000
MANIFEST_SIZE_LIMIT = 1_000_000
MAX_TREE_CANDIDATES = 10
MAX_FETCH_ERROR_RATIO = 0.05

FULL_NAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")

BLUETOOTH_KEYS = {
    "local_name": str,
    "service_uuid": str,
    "service_data_uuid": str,
    "manufacturer_id": int,
    "manufacturer_data_start": list,
    "connectable": bool,
}
BLUETOOTH_INDEX_KEYS = (
    "local_name",
    "manufacturer_id",
    "service_uuid",
    "service_data_uuid",
)
BLUETOOTH_LOCAL_NAME_MIN_LENGTH = 3
ZEROCONF_KEYS = {
    "type": str,
    "name": str,
    "properties": dict,
    "macaddress": str,
    "manufacturer": str,
    "model": str,
}
ZEROCONF_MOVED_PROPERTIES = ("macaddress", "model", "manufacturer")
HOMEKIT_ZEROCONF_TYPES = {"_hap._tcp.local.", "_hap._udp.local."}
DHCP_KEYS = {"macaddress": str, "hostname": str}
SSDP_PRIMARY_KEYS = ("manufacturer", "st", "deviceType", "nt", "manufacturerURL")

DROP_REASONS = (
    "repository_invalid",
    "manifest_not_found",
    "manifest_invalid",
    "manifest_fetch_error",
    "bluetooth_not_list",
    "bluetooth_invalid",
    "bluetooth_not_indexable",
    "bluetooth_wildcard_prefix",
    "zeroconf_not_list",
    "zeroconf_invalid",
    "zeroconf_homekit",
    "dhcp_not_list",
    "dhcp_invalid",
    "dhcp_registered_devices",
    "dhcp_no_key",
    "ssdp_not_list",
    "ssdp_invalid",
    "ssdp_no_primary_key",
)


class FetchError(Exception):
    pass


def log(message: str) -> None:
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def http_get(
    url: str, limit: int, headers: dict[str, str] | None = None
) -> bytes | None:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, **(headers or {})}
    )
    error: Exception | None = None
    for attempt in range(ATTEMPTS):
        wait = 2**attempt
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                body = response.read(limit + 1)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            if err.code not in (403, 429) and err.code < 500:
                raise FetchError(f"HTTP {err.code} for {url}") from err
            if (retry_after := err.headers.get("Retry-After", "")).isdigit():
                wait = min(int(retry_after), MAX_RETRY_WAIT)
            error = err
        except (OSError, http.client.HTTPException) as err:
            error = err
        else:
            if len(body) > limit:
                raise FetchError(f"Response larger than {limit} bytes for {url}")
            return body
        if attempt < ATTEMPTS - 1:
            time.sleep(wait)
    raise FetchError(f"{error} for {url}")


def parse_json(body: bytes) -> Any:
    try:
        return json.loads(body)
    except ValueError, RecursionError:
        return None


def raw_url(full_name: str, ref: str, path: str) -> str:
    return RAW_URL.format(
        full_name=full_name, ref=urllib.parse.quote(ref, safe=""), path=path
    )


def fetch_raw_manifest(full_name: str, ref: str, path: str) -> tuple[bool, Any]:
    body = http_get(raw_url(full_name, ref, path), MANIFEST_SIZE_LIMIT)
    if body is None:
        return False, None
    return True, parse_json(body)


def manifest_domain(manifest: Any) -> Any:
    return manifest.get("domain") if isinstance(manifest, dict) else None


def tree_manifest_paths(full_name: str, ref: str, token: str | None) -> list[str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = TREE_URL.format(full_name=full_name, ref=urllib.parse.quote(ref, safe=""))
    body = http_get(url, TREE_SIZE_LIMIT, headers)
    tree = parse_json(body) if body is not None else None
    if not isinstance(tree, dict) or not isinstance(tree.get("tree"), list):
        return []
    files = {
        item.get("path")
        for item in tree["tree"]
        if isinstance(item, dict) and item.get("type") == "blob"
    }
    paths = []
    for item in tree["tree"]:
        if not isinstance(item, dict) or item.get("type") != "tree":
            continue
        parts = str(item.get("path", "")).split("/")
        if len(parts) != 2 or parts[0] != "custom_components":
            continue
        if (path := f"{item['path']}/manifest.json") in files:
            paths.append(path)
    return paths[:MAX_TREE_CANDIDATES]


def fetch_manifest(
    full_name: str, domain: str, ref: str, token: str | None
) -> tuple[str, Any]:
    quoted_domain = urllib.parse.quote(domain, safe="")
    found_invalid = False
    for path in (f"custom_components/{quoted_domain}/manifest.json", "manifest.json"):
        found, manifest = fetch_raw_manifest(full_name, ref, path)
        if manifest_domain(manifest) == domain:
            return "ok", manifest
        found_invalid |= found and not isinstance(manifest, dict)

    first: list[Any] = []
    for path in tree_manifest_paths(full_name, ref, token):
        found, manifest = fetch_raw_manifest(full_name, ref, path)
        if manifest_domain(manifest) == domain:
            return "ok", manifest
        if found and not first:
            first.append(manifest)
    if first and isinstance(first[0], dict):
        return "ok", first[0]
    if first or found_invalid:
        return "invalid", None
    return "not_found", None


def manifest_subset(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = ("domain", "name", *SOURCES)
    return {key: manifest[key] for key in keys if key in manifest}


def load_cache(cache_dir: Path, repository_id: str) -> dict[str, Any] | None:
    try:
        record = json.loads((cache_dir / f"{repository_id}.json").read_text())
    except OSError, ValueError:
        return None
    return record if isinstance(record, dict) else None


def save_cache(cache_dir: Path, repository_id: str, record: dict[str, Any]) -> None:
    path = cache_dir / f"{repository_id}.json"
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(record, sort_keys=True))
    temp_path.replace(path)


def resolve_repository(
    repository_id: str,
    entry: dict[str, Any],
    cache_dir: Path,
    token: str | None,
) -> dict[str, Any]:
    full_name = entry["full_name"]
    domain = entry["domain"]
    ref = entry["ref"]
    cacheable = ref != "HEAD"
    if cacheable:
        cached = load_cache(cache_dir, repository_id)
        if (
            cached
            and cached.get("cache_version") == CACHE_VERSION
            and cached.get("ref") == ref
            and cached.get("domain") == domain
        ):
            return cached | {"cached": True}
    try:
        status, manifest = fetch_manifest(full_name, domain, ref, token)
    except FetchError as err:
        log(f"Fetch error for {full_name}: {err}")
        return {"status": "fetch_error"}
    except Exception as err:  # noqa: BLE001
        log(f"Unexpected error for {full_name}: {err!r}")
        return {"status": "fetch_error"}
    record = {
        "cache_version": CACHE_VERSION,
        "ref": ref,
        "domain": domain,
        "status": status,
        "manifest": manifest_subset(manifest) if status == "ok" else None,
    }
    if cacheable:
        try:
            save_cache(cache_dir, repository_id, record)
        except OSError as err:
            log(f"Could not write cache for {full_name}: {err}")
    return record | {"cached": False}


def is_byte(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 255


def has_valid_types(entry: dict[str, Any], schema: dict[str, type]) -> bool:
    for key, value in entry.items():
        expected = schema.get(key)
        if expected is None:
            return False
        if expected is int:
            if type(value) is not int:
                return False
        elif not isinstance(value, expected):
            return False
    return True


def normalize_bluetooth(entry: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(entry, dict) or not has_valid_types(entry, BLUETOOTH_KEYS):
        return None, "bluetooth_invalid"
    if not all(is_byte(value) for value in entry.get("manufacturer_data_start", [])):
        return None, "bluetooth_invalid"
    if not any(key in entry for key in BLUETOOTH_INDEX_KEYS):
        return None, "bluetooth_not_indexable"
    if "local_name" in entry:
        prefix = entry["local_name"][:BLUETOOTH_LOCAL_NAME_MIN_LENGTH]
        if "*" in prefix or "[" in prefix:
            return None, "bluetooth_wildcard_prefix"
    return copy.deepcopy(entry), None


def normalize_zeroconf(entry: Any) -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(entry, str):
        entry = {"type": entry}
    if not isinstance(entry, dict) or not has_valid_types(entry, ZEROCONF_KEYS):
        return None, "zeroconf_invalid"
    if not entry.get("type"):
        return None, "zeroconf_invalid"
    properties = entry.get("properties", {})
    if not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in properties.items()
    ):
        return None, "zeroconf_invalid"
    if entry["type"] in HOMEKIT_ZEROCONF_TYPES:
        return None, "zeroconf_homekit"
    matcher = copy.deepcopy(entry)
    for key in ZEROCONF_MOVED_PROPERTIES:
        if value := matcher.pop(key, None):
            matcher.setdefault("properties", {})[key] = value.lower()
    return matcher, None


def normalize_dhcp(entry: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(entry, dict):
        return None, "dhcp_invalid"
    if "registered_devices" in entry:
        return None, "dhcp_registered_devices"
    if not has_valid_types(entry, DHCP_KEYS):
        return None, "dhcp_invalid"
    if not entry.get("macaddress") and not entry.get("hostname"):
        return None, "dhcp_no_key"
    return copy.deepcopy(entry), None


def normalize_ssdp(entry: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(entry, dict) or not entry:
        return None, "ssdp_invalid"
    if not all(
        isinstance(key, str) and isinstance(value, str) for key, value in entry.items()
    ):
        return None, "ssdp_invalid"
    if not any(entry.get(key) for key in SSDP_PRIMARY_KEYS):
        return None, "ssdp_no_primary_key"
    return dict(entry), None


NORMALIZERS = {
    "bluetooth": normalize_bluetooth,
    "zeroconf": normalize_zeroconf,
    "dhcp": normalize_dhcp,
    "ssdp": normalize_ssdp,
}


def build_matchers(
    manifest: dict[str, Any], dropped: Counter[str]
) -> dict[str, list[dict[str, Any]]]:
    matchers: dict[str, list[dict[str, Any]]] = {}
    for source in SOURCES:
        if source not in manifest:
            continue
        entries = manifest[source]
        if not isinstance(entries, list):
            dropped[f"{source}_not_list"] += 1
            continue
        kept = []
        for entry in entries:
            matcher, reason = NORMALIZERS[source](entry)
            if reason:
                dropped[reason] += 1
            else:
                kept.append(matcher)
        if kept:
            matchers[source] = kept
    return matchers


def catalog_entries(data: Any, dropped: Counter[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        raise SystemExit("Catalog data is not a JSON object")
    entries = {}
    for repository_id, item in data.items():
        if not isinstance(item, dict):
            dropped["repository_invalid"] += 1
            continue
        if item.get("full_name") in SKIPPED_REPOSITORIES:
            continue
        full_name = item.get("full_name")
        domain = item.get("domain")
        ref = item.get("last_version") or item.get("last_commit") or "HEAD"
        if (
            not repository_id.isdigit()
            or not isinstance(full_name, str)
            or not FULL_NAME_PATTERN.fullmatch(full_name)
            or not isinstance(domain, str)
            or not domain
            or not isinstance(ref, str)
        ):
            dropped["repository_invalid"] += 1
            continue
        manifest_name = item.get("manifest_name")
        entries[repository_id] = {
            "full_name": full_name,
            "domain": domain,
            "ref": ref,
            "manifest_name": manifest_name if isinstance(manifest_name, str) else None,
        }
    return entries


def prune_cache(cache_dir: Path, keep: set[str]) -> int:
    removed = 0
    for path in cache_dir.glob("*.json"):
        if path.stem.isdigit() and path.stem not in keep:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def write_output(path: Path, dataset: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(dataset, sort_keys=True) + "\n")
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the marketplace discovery matcher dataset."
    )
    parser.add_argument("--output", type=Path, default=Path("dist/matchers.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/manifests"))
    parser.add_argument("--concurrency", type=int, default=12)
    args = parser.parse_args()

    started = time.monotonic()
    token = os.environ.get("GITHUB_TOKEN") or None
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    log(f"Downloading {DATA_URL}")
    body = http_get(DATA_URL, DATA_SIZE_LIMIT)
    if body is None:
        raise SystemExit(f"{DATA_URL} returned 404")
    dropped: Counter[str] = Counter(dict.fromkeys(DROP_REASONS, 0))
    entries = catalog_entries(parse_json(body), dropped)
    log(f"{len(entries)} repositories in the catalog")

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        records = dict(
            zip(
                entries,
                executor.map(
                    lambda item: resolve_repository(
                        item[0], item[1], args.cache_dir, token
                    ),
                    entries.items(),
                ),
                strict=True,
            )
        )

    integrations: dict[str, dict[str, Any]] = {}
    manifests = 0
    cached = 0
    for repository_id, record in records.items():
        entry = entries[repository_id]
        cached += bool(record.get("cached"))
        status = record.get("status")
        if status != "ok":
            reason = {
                "not_found": "manifest_not_found",
                "invalid": "manifest_invalid",
            }.get(status, "manifest_fetch_error")
            dropped[reason] += 1
            if status != "fetch_error":
                log(
                    f"No manifest for {entry['full_name']} at {entry['ref']} ({status})"
                )
            continue
        manifests += 1
        manifest = record["manifest"]
        matchers = build_matchers(manifest, dropped)
        if not matchers:
            continue
        domain = manifest.get("domain")
        name = manifest.get("name")
        integrations[repository_id] = {
            "full_name": entry["full_name"],
            "domain": domain if isinstance(domain, str) and domain else entry["domain"],
            "name": name
            if isinstance(name, str) and name
            else entry["manifest_name"] or entry["domain"],
            "ref": entry["ref"],
            **matchers,
        }

    pruned = prune_cache(args.cache_dir, set(entries))
    fetch_errors = dropped["manifest_fetch_error"]
    source_counts = {
        source: sum(source in item for item in integrations.values())
        for source in SOURCES
    }
    log(
        f"{manifests} manifests ({cached} from cache, {pruned} cache files pruned), "
        f"{len(integrations)} with matchers {source_counts}, {fetch_errors} fetch errors, "
        f"{time.monotonic() - started:.1f} s"
    )
    if not integrations:
        raise SystemExit("No integration with matchers, refusing to write the dataset")
    if fetch_errors > len(entries) * MAX_FETCH_ERROR_RATIO:
        raise SystemExit(f"{fetch_errors} fetch errors, refusing to write the dataset")

    write_output(
        args.output,
        {
            "version": DATASET_VERSION,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "stats": {
                "repositories": len(entries),
                "manifests": manifests,
                "with_matchers": len(integrations),
                "dropped": dict(dropped),
            },
            "integrations": integrations,
        },
    )
    log(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
