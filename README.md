# Marketplace Discovery

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/piitaya/ha-marketplace-discovery)](https://github.com/piitaya/ha-marketplace-discovery/releases)

Exploration: find Marketplace (HACS) integrations that support devices Home Assistant has already discovered on your network (Bluetooth, zeroconf, DHCP, SSDP).

## Installation

### Marketplace (recommended)

Requires Home Assistant 2026.11 or later.

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=piitaya&repository=ha-marketplace-discovery&category=integration)

Or manually:

1. Open the **Marketplace** and add `https://github.com/piitaya/ha-marketplace-discovery` as a custom repository with the **Integration** type.
2. Download **Marketplace Discovery**.
3. Restart Home Assistant.

### Manual

1. Copy `custom_components/marketplace_discovery` into the `custom_components` folder of your Home Assistant configuration.
2. Restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up Marketplace Discovery.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=marketplace_discovery)

Or go to **Settings** > **Devices & services** > **Add integration** and search for **Marketplace Discovery**.

## Usage

Open **Marketplace discovery** in the sidebar (administrators only) and select **Search**. **Search with refresh** scans the network again for a few seconds first.

Each result shows the integration, the matched device and the discovery rule that fired, with a link to the integration in the Marketplace. If a result is wrong, use **Report false positive**.

## Known limitations

- Only integrations that declare Bluetooth, zeroconf, DHCP or SSDP discovery can be found (about 10% of the catalog). USB, MQTT and HomeKit are not supported.
- DHCP only sees devices that were active since the last restart.
- Broad discovery rules, for example any device with a web interface, can give false positives.
- An integration is shown as installed when an integration with the same domain is installed.
- Refreshing SSDP relies on a private Home Assistant API and is skipped if that API changes.
