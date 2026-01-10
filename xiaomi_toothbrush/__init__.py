"""Xiaomi Toothbrush SMI-T501 Integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import XiaomiToothbrushCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Xiaomi Toothbrush from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if setup was successful
    """
    address: str = entry.data[CONF_ADDRESS]
    name: str = entry.data.get(CONF_NAME, "Xiaomi Toothbrush")

    _LOGGER.debug("Setting up Xiaomi Toothbrush: %s (%s)", name, address)

    # Check if Bluetooth is available
    if not bluetooth.async_scanner_count(hass, connectable=False):
        raise ConfigEntryNotReady("No Bluetooth adapter available")

    # Create coordinator
    coordinator = XiaomiToothbrushCoordinator(hass, address, name)

    # Start listening to Bluetooth advertisements
    await coordinator.async_start()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Xiaomi Toothbrush integration set up: %s", name)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if unload was successful
    """
    _LOGGER.debug("Unloading Xiaomi Toothbrush: %s", entry.data.get(CONF_NAME))

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: XiaomiToothbrushCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update.

    Args:
        hass: Home Assistant instance
        entry: Config entry
    """
    await hass.config_entries.async_reload(entry.entry_id)
