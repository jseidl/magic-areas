"""BLE Tracker binary sensor component."""

from datetime import UTC, datetime
import logging

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers.event import async_track_state_change_event

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    ATTR_ACTIVE_SENSORS,
    CONF_BLE_TRACKER_ENTITIES,
    MagicAreasFeatureInfoBLETrackers,
    MagicAreasFeatures,
)

_LOGGER = logging.getLogger(__name__)


class AreaBLETrackerBinarySensor(MagicEntity, BinarySensorEntity):
    """BLE Tracker monitoring sensor for the area."""

    feature_info = MagicAreasFeatureInfoBLETrackers()
    _sensors: list[str]

    def __init__(self, area: MagicArea) -> None:
        """Initialize the area presence binary sensor."""

        MagicEntity.__init__(self, area, domain=BINARY_SENSOR_DOMAIN)
        BinarySensorEntity.__init__(self)

        self._sensors = self.area.feature_config(MagicAreasFeatures.BLE_TRACKERS).get(
            CONF_BLE_TRACKER_ENTITIES, []
        )

        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY
        self._attr_extra_state_attributes = {
            ATTR_ENTITY_ID: self._sensors,
            ATTR_ACTIVE_SENSORS: [],
        }
        self._attr_is_on: bool = False

    async def async_added_to_hass(self) -> None:
        """Call to add the system to hass."""
        await super().async_added_to_hass()
        await self.restore_state()

        # Setup the listeners
        await self._setup_listeners()

        self.hass.loop.call_soon_threadsafe(self._update_state, datetime.now(UTC))

        _LOGGER.debug("%s: BLE Tracker monitor sensor initialized", self.area.name)

    async def _setup_listeners(self) -> None:
        """Attach state chagne listeners."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._sensors, self._sensor_state_change
            )
        )

    def _sensor_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Call update state from track state change event."""

        self._update_state()

    @callback
    def _update_state(self, extra: datetime | None = None) -> None:
        """Calculate state based off BLE tracker sensors."""

        calculated_state: bool = False
        active_sensors: list[str] = []

        for sensor in self._sensors:
            sensor_state = self.hass.states.get(sensor)

            if not sensor_state:
                continue

            normalized_state = sensor_state.state.lower()

            if (
                normalized_state == self.area.slug
                or normalized_state == self.area.id
                or normalized_state == self.area.name.lower()
            ):
                calculated_state = True
                active_sensors.append(sensor)

        _LOGGER.debug(
            "%s: BLE Tracker monitor sensor state change: %s -> %s",
            self.area.name,
            self._attr_is_on,
            calculated_state,
        )

        self._attr_is_on = calculated_state
        self._attr_extra_state_attributes[ATTR_ACTIVE_SENSORS] = active_sensors
        self.schedule_update_ha_state()
