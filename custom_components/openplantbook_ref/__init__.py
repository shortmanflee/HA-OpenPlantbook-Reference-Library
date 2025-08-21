"""Plant Sensor integration setup."""

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.openplantbook_ref.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

# Config schema - integration can only be set up from config entries
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.config_entry_only_config_schema(DOMAIN)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(_hass: HomeAssistant, _config: dict) -> bool:
    """Set up the Plant Sensor integration from yaml (not used)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plant Sensor from a config entry."""
    _LOGGER.info(
        "Setting up Plant Sensor integration entry: %s (title: %s, version: %s)",
        entry.entry_id,
        entry.title,
        entry.version,
    )
    _LOGGER.debug("Config entry data keys: %s", list(entry.data.keys()))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    # Set up the entry's listener for reloading when config changes
    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    _LOGGER.debug("Update listener added for config entry %s", entry.entry_id)

    # Forward the main config entry to sensor platform
    _LOGGER.debug("Forwarding config entry to platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "Plant Sensor integration setup completed successfully for entry %s",
        entry.entry_id,
    )
    return True


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry updates."""
    _LOGGER.info("Handling config entry update for %s", entry.entry_id)
    _LOGGER.debug("Reloading config entry after update")
    # Reload the entry to pick up any changes
    await hass.config_entries.async_reload(entry.entry_id)
    _LOGGER.debug("Config entry %s reloaded successfully", entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Plant Sensor config entry: %s", entry.entry_id)

    # Remove entry data from hass.data
    removed_data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if removed_data:
        _LOGGER.debug("Removed entry data for %s", entry.entry_id)
    else:
        _LOGGER.warning("No entry data found to remove for %s", entry.entry_id)

    # Unload platforms
    unload_result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_result:
        _LOGGER.info("Successfully unloaded config entry %s", entry.entry_id)
    else:
        _LOGGER.error("Failed to unload config entry %s", entry.entry_id)

    return unload_result


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a device from a config entry."""
    _LOGGER.info(
        "Attempting to remove device %s from config entry %s",
        device_entry.id,
        config_entry.entry_id,
    )
    _LOGGER.debug("Device identifiers: %s", device_entry.identifiers)

    # Find the device ID from the device identifiers
    device_id = None
    for identifier in device_entry.identifiers:
        if identifier[0] == DOMAIN:  # Check if it's our domain
            device_id = identifier[1]
            _LOGGER.debug("Found device ID: %s", device_id)
            break

    if not device_id:
        _LOGGER.warning(
            "Could not find device ID in identifiers for device %s", device_entry.id
        )
        return False

    # Find and remove the corresponding subentry
    subentry_to_remove = None
    _LOGGER.debug("Searching through %d subentries", len(config_entry.subentries))
    for subentry_id, subentry in config_entry.subentries.items():
        subentry_device_id = subentry.data.get("device_id")
        _LOGGER.debug(
            "Checking subentry %s with device_id %s", subentry_id, subentry_device_id
        )
        if subentry_device_id == device_id:
            subentry_to_remove = subentry_id
            _LOGGER.debug("Found matching subentry: %s", subentry_id)
            break

    if subentry_to_remove:
        hass.config_entries.async_remove_subentry(config_entry, subentry_to_remove)
        _LOGGER.info("Removed subentry %s for device %s", subentry_to_remove, device_id)
        return True

    _LOGGER.warning(
        "Could not find subentry with device_id %s for device removal", device_id
    )
    return False
