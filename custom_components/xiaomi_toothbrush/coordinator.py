"""Data coordinator for Xiaomi Toothbrush integration."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any, Callable

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL
from .parser import XiaomiToothbrushData, XiaomiToothbrushParser
from .gatt_client import XiaomiToothbrushGATT

_LOGGER = logging.getLogger(__name__)

# GATT polling interval (seconds) - poll after brushing ends
GATT_POLL_INTERVAL = 60


class XiaomiToothbrushCoordinator(DataUpdateCoordinator[XiaomiToothbrushData]):
    """Coordinator for Xiaomi Toothbrush data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{address}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.address = address
        self.device_name = name
        self.parser = XiaomiToothbrushParser()
        self._last_service_info: BluetoothServiceInfoBleak | None = None
        self._cancel_bluetooth_callback: Callable[[], None] | None = None

        # Current data
        self.data = XiaomiToothbrushData()

        # Session tracking
        self._session_start_time: float | None = None
        self._last_brushing_state: bool = False
        self._total_brushing_time: int = 0
        self._current_session_duration: int = 0
        
        # GATT
        self._last_gatt_poll: float = 0
        self._gatt_battery: int | None = None

    async def async_start(self) -> None:
        """Start listening to Bluetooth advertisements."""
        _LOGGER.info("Starting Bluetooth listener for %s", self.address)

        self._cancel_bluetooth_callback = bluetooth.async_register_callback(
            self.hass,
            self._handle_bluetooth_event,
            bluetooth.BluetoothCallbackMatcher(
                address=self.address,
            ),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )

        # Try to get initial data
        service_info = bluetooth.async_last_service_info(
            self.hass, self.address, connectable=False
        )
        if service_info:
            self._process_service_info(service_info)

    @callback
    def _handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle Bluetooth advertisement."""
        self._process_service_info(service_info)

    def _process_service_info(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Process Bluetooth service info and update data."""
        self._last_service_info = service_info

        service_data: dict[str, Any] = {}
        for uuid, data in service_info.service_data.items():
            service_data[uuid] = data

        if not service_data:
            return

        parsed = self.parser.parse_advertisement(service_data)

        if parsed:
            self._update_data(parsed)

    def _update_data(self, parsed: XiaomiToothbrushData) -> None:
        """Update coordinator data with parsed values."""
        current_time = time.time()
        
        # Track brushing sessions
        if parsed.is_brushing and not self._last_brushing_state:
            # Brushing started
            _LOGGER.info("Brushing session STARTED")
            self._session_start_time = current_time
            self._current_session_duration = 0

        elif not parsed.is_brushing and self._last_brushing_state:
            # Brushing stopped
            if self._session_start_time:
                duration = int(current_time - self._session_start_time)
                self._total_brushing_time += duration
                self._current_session_duration = duration
                _LOGGER.info("Brushing session ENDED. Duration: %d seconds", duration)
            self._session_start_time = None
            
            # Schedule GATT poll after brushing ends
            self.hass.async_create_task(self._delayed_gatt_poll())

        elif parsed.is_brushing and self._session_start_time:
            # Still brushing - update duration
            self._current_session_duration = int(current_time - self._session_start_time)

        self._last_brushing_state = parsed.is_brushing
        
        # Always set duration from tracked value
        parsed.brushing_duration = self._current_session_duration
        
        # Use cached GATT battery if available
        if self._gatt_battery is not None:
            parsed.battery_percent = self._gatt_battery

        self.data = parsed
        self.async_set_updated_data(parsed)

    async def _delayed_gatt_poll(self) -> None:
        """Poll GATT after a short delay (device needs time to become connectable)."""
        await asyncio.sleep(5)  # Wait 5 seconds after brushing ends
        await self._poll_gatt_data()

    async def _poll_gatt_data(self) -> None:
        """Poll data via GATT connection."""
        current_time = time.time()
        
        # Rate limit
        if current_time - self._last_gatt_poll < GATT_POLL_INTERVAL:
            return
            
        # Don't poll while brushing
        if self._last_brushing_state:
            return
            
        self._last_gatt_poll = current_time
        _LOGGER.debug("Polling GATT data from %s", self.address)
        
        gatt = XiaomiToothbrushGATT(self.address)
        
        try:
            connected = await gatt.connect(timeout=10.0)
            if not connected:
                _LOGGER.debug("GATT connection failed")
                return
                
            # Read battery
            battery = await gatt.read_battery()
            if battery is not None:
                self._gatt_battery = battery
                self.data.battery_percent = battery
                _LOGGER.info("Battery from GATT: %d%%", battery)
                
            # Read device info (once)
            if not gatt.manufacturer:
                await gatt.read_device_info()
                
            await gatt.disconnect()
            
            # Update
            self.async_set_updated_data(self.data)
            
        except Exception as e:
            _LOGGER.debug("GATT poll error: %s", e)
        finally:
            await gatt.disconnect()

    async def _async_update_data(self) -> XiaomiToothbrushData:
        """Fetch data from device (called periodically)."""
        return self.data

    async def async_stop(self) -> None:
        """Stop listening to Bluetooth advertisements."""
        if self._cancel_bluetooth_callback:
            self._cancel_bluetooth_callback()
            self._cancel_bluetooth_callback = None

    @property
    def rssi(self) -> int | None:
        """Return the last known RSSI value."""
        if self._last_service_info:
            return self._last_service_info.rssi
        return None

    @property
    def total_brushing_time_today(self) -> int:
        """Return total brushing time in seconds for today."""
        return self._total_brushing_time
    
    @property
    def current_session_duration(self) -> int:
        """Return current brushing session duration in seconds."""
        return self._current_session_duration
