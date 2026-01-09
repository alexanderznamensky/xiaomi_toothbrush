"""Binary sensor platform for Xiaomi Toothbrush integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import XiaomiToothbrushCoordinator

_LOGGER = logging.getLogger(__name__)


BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="brushing",
        name="Brushing",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:toothbrush-electric",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Xiaomi Toothbrush binary sensors from a config entry."""
    coordinator: XiaomiToothbrushCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        XiaomiToothbrushBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class XiaomiToothbrushBinarySensor(
    CoordinatorEntity[XiaomiToothbrushCoordinator], RestoreEntity, BinarySensorEntity
):
    """Representation of a Xiaomi Toothbrush binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: XiaomiToothbrushCoordinator,
        entry: ConfigEntry,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{description.key}"
        self._restored_state: bool | None = None

        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_ADDRESS])},
            name=entry.data.get(CONF_NAME, "Xiaomi Toothbrush"),
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()
        
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._restored_state = last_state.state == "on"
            _LOGGER.debug("Restored brushing state: %s", self._restored_state)

    @property
    def is_on(self) -> bool | None:
        """Return True if brushing is active."""
        # Live value takes priority
        if self.coordinator.data is not None:
            return self.coordinator.data.is_brushing
        
        # Fall back to restored state (typically False after restart)
        return self._restored_state

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Always available if we have any state
        if self.is_on is not None:
            return True
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None]:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return {}

        data = self.coordinator.data
        return {
            "raw_data": data.raw_data,
            "last_duration": data.brushing_duration,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
