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
    """Set up Xiaomi Toothbrush sensors from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities
    """
    coordinator: XiaomiToothbrushCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        XiaomiToothbrushSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class XiaomiToothbrushSensor(
    CoordinatorEntity[XiaomiToothbrushCoordinator], SensorEntity
):
    """Representation of a Xiaomi Toothbrush sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: XiaomiToothbrushCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data coordinator
            entry: Config entry
            description: Sensor description
        """
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{description.key}"

        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_ADDRESS])},
            name=entry.data.get(CONF_NAME, "Xiaomi Toothbrush"),
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None

        data = self.coordinator.data
        key = self.entity_description.key

        if key == "battery":
            return data.battery_percent

        if key == "brushing_duration":
            return data.brushing_duration

        if key == "total_time_today":
            return self.coordinator.total_brushing_time_today

        if key == "signal_strength":
            return self.coordinator.rssi

        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # For battery and signal, always try to show value
        if self.entity_description.key in ("battery", "signal_strength"):
            return self.coordinator.last_update_success

        # For other sensors, check if we have valid data
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
