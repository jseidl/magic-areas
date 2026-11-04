"""Door transition occupancy binary sensor for Magic Areas.

Opening or closing a door is usually the *earliest* signal that someone
entered or left a room -- it happens before a motion/PIR sensor gets a
chance to see the person. This sensor pulses "on" for a configurable
amount of seconds whenever any door-classed sensor in the area transitions
(either direction), so that Magic Areas can mark the area as occupied a
few seconds earlier than it otherwise would.

See: https://github.com/jseidl/hass-magic_areas/discussions/610
"""

import logging

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import Event, EventStateChangedData, State, callback
from homeassistant.helpers.event import async_track_state_change_event

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    CONF_DOOR_TRANSITION_OCCUPANCY_TIMEOUT,
    DEFAULT_DOOR_TRANSITION_OCCUPANCY_TIMEOUT,
    MagicAreasFeatureInfoDoorTransitionOccupancy,
)
from custom_components.magic_areas.helpers.timer import ReusableTimer

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_DOOR_ENTITY_ID = "last_door_entity_id"


class AreaDoorTransitionOccupancyBinarySensor(MagicEntity, BinarySensorEntity):
    """Pulses "on" whenever a door sensor in the area transitions state."""

    feature_info = MagicAreasFeatureInfoDoorTransitionOccupancy()

    def __init__(self, area: MagicArea, door_sensors: list[str]) -> None:
        """Initialize the door transition occupancy sensor."""

        MagicEntity.__init__(self, area, domain=BINARY_SENSOR_DOMAIN)
        BinarySensorEntity.__init__(self)

        self._door_sensors: list[str] = door_sensors
        self._timeout: int = self.area.config.get(
            CONF_DOOR_TRANSITION_OCCUPANCY_TIMEOUT,
            DEFAULT_DOOR_TRANSITION_OCCUPANCY_TIMEOUT,
        )

        self._attr_device_class = BinarySensorDeviceClass.PRESENCE
        self._attr_is_on: bool = False
        self._attr_extra_state_attributes = {ATTR_LAST_DOOR_ENTITY_ID: None}

        self._timer: ReusableTimer | None = None

    async def async_added_to_hass(self) -> None:
        """Call to add the entity to hass."""
        await super().async_added_to_hass()
        await self.restore_state()

        # Transitions are momentary events: never restore an "on" pulse
        # across a restart, it would just get stuck without a running timer.
        self._attr_is_on = False

        if self._timeout > 0 and self._door_sensors:

            async def _clear_pulse(now) -> None:
                self._attr_is_on = False
                self.schedule_update_ha_state()

            self._timer = ReusableTimer(self.hass, self._timeout, _clear_pulse)

            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._door_sensors, self._async_door_state_change
                )
            )

        self.schedule_update_ha_state()

        _LOGGER.debug(
            "%s: Door transition occupancy sensor initialized (timeout=%ss, doors=%s)",
            self.area.name,
            self._timeout,
            self._door_sensors,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call to remove the entity from hass."""
        if self._timer:
            await self._timer.async_remove()
        await super().async_will_remove_from_hass()

    @callback
    def _async_door_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Treat any door state transition (open or close) as a presence pulse."""

        new_state: State | None = event.data.get("new_state")
        old_state: State | None = event.data.get("old_state")

        # Ignore anything that isn't an actual state transition (e.g. the
        # initial state report on startup, or attribute-only updates).
        if new_state is None or old_state is None:
            return
        if new_state.state == old_state.state:
            return

        entity_id = event.data["entity_id"]

        _LOGGER.debug(
            "%s: Door '%s' transitioned %s -> %s, pulsing occupancy for %s seconds",
            self.area.name,
            entity_id,
            old_state.state,
            new_state.state,
            self._timeout,
        )

        self._attr_is_on = True
        self._attr_extra_state_attributes[ATTR_LAST_DOOR_ENTITY_ID] = entity_id
        self.schedule_update_ha_state()

        if self._timer:
            self._timer.start()
