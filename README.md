<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/piitaya/ha-marketplace-discovery/main/custom_components/marketplace_discovery/brand/dark_icon@2x.png">
  <img alt="Marketplace Discovery icon" src="https://raw.githubusercontent.com/piitaya/ha-marketplace-discovery/main/custom_components/marketplace_discovery/brand/icon@2x.png" width="96">
</picture>

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

### Custom repositories (experimental)

Select **Configure** on the integration and turn on **Include custom repositories** to also compare your devices with about 1,700 integrations found on GitHub that are not in the Marketplace. They are listed in their own **Custom repositories** section. To install one, open it on GitHub, then use **Add from link** in the Marketplace.

> [!WARNING]
> These integrations come from an automated search of GitHub. Nobody has reviewed them, many are small personal projects and some are no longer maintained. An integration runs with full access to your Home Assistant, so only install one after checking its repository and its author.

## Usage

Open **Marketplace discovery** in the sidebar (administrators only). It lists the integrations that match the devices Home Assistant has already discovered on your network. Home Assistant keeps listening in the background, so the list is up to date when you open it. If you just plugged in a device, select the refresh button in the top right corner to scan the network again (about 10 seconds).

Use the search field to find an integration, device or address, and the protocol chips to narrow the list. Installed and ignored integrations are hidden until you turn on **Installed** or **Ignored**, then they show at the top of the list.

Each card shows the integration with the protocols and number of matched devices, its GitHub stars and when it was last updated. Expand it to read the description and the device list, then select **Open in Marketplace** to install it. Hover a device to see the discovery rule that matched it.

If an integration is not relevant, select **Ignore** on its card. To ignore several at once, enter selection mode with the button next to the search field, pick the cards and select **Ignore selected**. The ignored list is kept across restarts and you can undo it with **Stop ignoring**.

The panel is available in English and French and follows your Home Assistant language.

## Known limitations

- Only integrations that declare Bluetooth, zeroconf, DHCP or SSDP discovery can be found (about 10% of the catalog). USB, MQTT and HomeKit are not supported.
- DHCP only sees devices that were active since the last restart.
- Broad discovery rules, for example any device with a web interface, can give false positives.
- An integration is shown as installed when an integration with the same domain is installed.
- Refreshing SSDP relies on a private Home Assistant API and is skipped if that API changes.
