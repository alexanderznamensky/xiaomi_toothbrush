"""GATT client for Xiaomi Toothbrush direct connection."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bleak.exc import BleakError
from homeassistant.components import bluetooth

if TYPE_CHECKING:
    from bleak import BleakClient
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Standard BLE UUIDs
UUID_BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"
UUID_MANUFACTURER_NAME = "00002a29-0000-1000-8000-00805f9b34fb"
UUID_MODEL_NUMBER = "00002a24-0000-1000-8000-00805f9b34fb"
UUID_SERIAL_NUMBER = "00002a25-0000-1000-8000-00805f9b34fb"
UUID_FIRMWARE_REV = "00002a26-0000-1000-8000-00805f9b34fb"
UUID_HARDWARE_REV = "00002a27-0000-1000-8000-00805f9b34fb"


class XiaomiToothbrushGATT:
    """GATT client for Xiaomi Toothbrush using HA Bluetooth."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize GATT client."""
        self.hass = hass
        self.address = address
        self._client: BleakClient | None = None
        
        # Cached data
        self.battery_level: int | None = None
        self.manufacturer: str | None = None
        self.model: str | None = None
        self.serial_number: str | None = None
        self.firmware: str | None = None
        self.hardware: str | None = None

    async def connect(self, timeout: float = 10.0) -> bool:
        """Connect to the toothbrush using HA Bluetooth."""
        try:
            _LOGGER.debug("Connecting to %s via HA Bluetooth...", self.address)
            
            # Get BLE device from HA
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            
            if not ble_device:
                _LOGGER.debug("Device %s not found", self.address)
                return False
            
            # Use bleak-retry-connector via HA's async_get_bluetooth_adapters
            from bleak_retry_connector import establish_connection
            from bleak import BleakClient
            
            self._client = await establish_connection(
                BleakClient,
                ble_device,
                self.address,
                max_attempts=2,
            )
            
            if self._client and self._client.is_connected:
                _LOGGER.info("GATT connected to %s", self.address)
                return True
            else:
                _LOGGER.debug("Failed to connect to %s", self.address)
                return False
                
        except BleakError as e:
            _LOGGER.debug("Connection error: %s", e)
            return False
        except Exception as e:
            _LOGGER.debug("Unexpected error connecting: %s", e)
            return False

    async def disconnect(self) -> None:
        """Disconnect from the toothbrush."""
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            finally:
                self._client = None

    async def read_battery(self) -> int | None:
        """Read battery level."""
        if not self._client or not self._client.is_connected:
            return None
            
        try:
            data = await self._client.read_gatt_char(UUID_BATTERY_LEVEL)
            if data:
                self.battery_level = data[0]
                _LOGGER.info("GATT battery level: %d%%", self.battery_level)
                return self.battery_level
        except BleakError as e:
            _LOGGER.debug("Failed to read battery: %s", e)
        except Exception as e:
            _LOGGER.debug("Battery read error: %s", e)
            
        return None

    async def read_device_info(self) -> dict[str, str]:
        """Read device information."""
        info = {}
        
        if not self._client or not self._client.is_connected:
            return info
        
        # Manufacturer
        try:
            data = await self._client.read_gatt_char(UUID_MANUFACTURER_NAME)
            if data:
                self.manufacturer = data.decode('utf-8', errors='ignore').strip('\x00')
                info['manufacturer'] = self.manufacturer
        except Exception:
            pass
                
        # Model
        try:
            data = await self._client.read_gatt_char(UUID_MODEL_NUMBER)
            if data:
                self.model = data.decode('utf-8', errors='ignore').strip('\x00')
                info['model'] = self.model
        except Exception:
            pass
                
        # Serial
        try:
            data = await self._client.read_gatt_char(UUID_SERIAL_NUMBER)
            if data:
                self.serial_number = data.decode('utf-8', errors='ignore').strip('\x00')
                info['serial'] = self.serial_number
        except Exception:
            pass
                
        # Firmware
        try:
            data = await self._client.read_gatt_char(UUID_FIRMWARE_REV)
            if data:
                self.firmware = data.decode('utf-8', errors='ignore').strip('\x00')
                info['firmware'] = self.firmware
        except Exception:
            pass
                
        # Hardware
        try:
            data = await self._client.read_gatt_char(UUID_HARDWARE_REV)
            if data:
                self.hardware = data.decode('utf-8', errors='ignore').strip('\x00')
                info['hardware'] = self.hardware
        except Exception:
            pass
                
        return info

    async def read_all(self) -> bool:
        """Read all available data."""
        if not self._client or not self._client.is_connected:
            return False
            
        await self.read_battery()
        await self.read_device_info()
        return True

    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._client is not None and self._client.is_connected
