"""Config flow for Xiaomi Toothbrush integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, XIAOMI_SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


class XiaomiToothbrushConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Xiaomi Toothbrush."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: bluetooth.BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, bluetooth.BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the Bluetooth discovery step.

        Args:
            discovery_info: Discovered Bluetooth device info

        Returns:
            Flow result
        """
        _LOGGER.debug("Bluetooth discovery: %s", discovery_info)

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Bluetooth device setup.

        Args:
            user_input: User input from the form

        Returns:
            Flow result
        """
        if self._discovery_info is None:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name or "Xiaomi Toothbrush",
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_NAME: self._discovery_info.name,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or self._discovery_info.address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step.

        Args:
            user_input: User input from the form

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]

            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            # Validate the address format
            if not self._is_valid_mac(address):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "Xiaomi Toothbrush"),
                    data={
                        CONF_ADDRESS: address.upper(),
                        CONF_NAME: user_input.get(CONF_NAME, "Xiaomi Toothbrush"),
                    },
                )

        # Discover available devices
        await self._async_discover_devices()

        # Build device list for selection
        device_options = {
            address: f"{info.name or 'Unknown'} ({address})"
            for address, info in self._discovered_devices.items()
        }

        if device_options:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): vol.In(device_options),
                        vol.Optional(CONF_NAME, default="Xiaomi Toothbrush"): str,
                    }
                ),
                errors=errors,
            )

        # No devices found, allow manual entry
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME, default="Xiaomi Toothbrush"): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "note": "No devices found. Enter MAC address manually."
            },
        )

    async def _async_discover_devices(self) -> None:
        """Discover Xiaomi toothbrush devices."""
        self._discovered_devices = {}

        # Get all Bluetooth devices
        for service_info in bluetooth.async_discovered_service_info(
            self.hass, connectable=True
        ):
            # Check if it's a Xiaomi device with toothbrush characteristics
            if self._is_xiaomi_toothbrush(service_info):
                self._discovered_devices[service_info.address] = service_info

        _LOGGER.debug("Discovered devices: %s", list(self._discovered_devices.keys()))

    def _is_xiaomi_toothbrush(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> bool:
        """Check if a device is a Xiaomi toothbrush.

        Args:
            service_info: Bluetooth service info

        Returns:
            True if the device appears to be a Xiaomi toothbrush
        """
        # Check by name
        name = service_info.name or ""
        if "SMI-T" in name.upper() or "TOOTHBRUSH" in name.upper():
            return True

        # Check for Xiaomi service UUID
        if XIAOMI_SERVICE_UUID in service_info.service_data:
            return True

        return False

    @staticmethod
    def _is_valid_mac(address: str) -> bool:
        """Validate MAC address format.

        Args:
            address: MAC address string

        Returns:
            True if valid MAC address format
        """
        import re

        pattern = r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"
        return bool(re.match(pattern, address))
