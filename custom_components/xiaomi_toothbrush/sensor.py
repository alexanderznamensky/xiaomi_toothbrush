"""Sensor platform for Xiaomi Toothbrush integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import XiaomiToothbrushCoordinator

_LOGGER = logging.getLogger(__name__)


SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="brushing_duration",
        name="Brushing Duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        key="total_time_today",
        name="Total Brushing Time Today",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:timer-check",
    ),
    SensorEntityDescription(
        key="signal_strength",
        name="Signal Strength",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Xiaomi Toothbrush sensors from a config entry."""
    coordinator: XiaomiToothbrushCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        XiaomiToothbrushSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class XiaomiToothbrushSensor(
    CoordinatorEntity[XiaomiToothbrushCoordinator], RestoreEntity, SensorEntity
):
    """Representation of a Xiaomi Toothbrush sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: XiaomiToothbrushCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{description.key}"
        self._restored_value: Any = None

        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_ADDRESS])},
            name=entry.data.get(CONF_NAME) or "SMI-T501",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()
        
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._restored_value = float(last_state.state)
                _LOGGER.debug(
                    "Restored %s: %s", 
                    self.entity_description.key, 
                    self._restored_value
                )
                
                # Also restore to coordinator if applicable
                key = self.entity_description.key
                if key == "battery" and self.coordinator._gatt_battery is None:
                    self.coordinator._gatt_battery = int(self._restored_value)
                elif key == "total_time_today":
                    self.coordinator._total_brushing_time = int(self._restored_value)
                elif key == "brushing_duration":
                    self.coordinator._current_session_duration = int(self._restored_value)
                    
            except (ValueError, TypeError):
                pass

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        key = self.entity_description.key
        
        # Try to get live value first
        live_value = self._get_live_value()
        
        if live_value is not None:
            return live_value
        
        # Fall back to restored value
        return self._restored_value
    
    def _get_live_value(self) -> Any:
        """Get live value from coordinator."""
        key = self.entity_description.key

        # Battery - use cached GATT value (may be set from restore)
        if key == "battery":
            return self.coordinator._gatt_battery

        # Other sensors need coordinator.data
        if self.coordinator.data is None:
            return None

        if key == "brushing_duration":
            return self.coordinator._current_session_duration

        if key == "total_time_today":
            return self.coordinator.total_brushing_time_today

        if key == "signal_strength":
            return self.coordinator.rssi

        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Always available if we have a restored or live value
        if self.native_value is not None:
            return True
        
        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
