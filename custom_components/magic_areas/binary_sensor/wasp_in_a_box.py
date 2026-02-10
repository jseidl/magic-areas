"""Wasp in a box binary sensor component."""

import logging

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Event, EventStateChangedData, State, callback
from homeassistant.helpers.event import async_track_state_change_event

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    ONE_MINUTE,
    MagicAreasFeatureInfoWaspInABox,
)
from custom_components.magic_areas.const.wasp_in_a_box import (
    WASP_IN_A_BOX_BOX_DEVICE_CLASSES,
    WaspInABoxOptions,
)
from custom_components.magic_areas.helpers.timer import ReusableTimer

_LOGGER = logging.getLogger(__name__)


ATTR_BOX = "box"
ATTR_WASP = "wasp"


class AreaWaspInABoxBinarySensor(MagicEntity, BinarySensorEntity):
    """Wasp In The Box logic tracking sensor for the area."""

    feature_info = MagicAreasFeatureInfoWaspInABox()

    def __init__(self, area: MagicArea) -> None:
        """Initialize the area presence binary sensor."""

        MagicEntity.__init__(self, area, domain=BINARY_SENSOR_DOMAIN)
        BinarySensorEntity.__init__(self)

        self._delay: int = self.area.config.get(WaspInABoxOptions.DELAY)

        self._wasp_timeout: int = self.area.config.get(WaspInABoxOptions.WASP_TIMEOUT)

        self._attr_device_class = BinarySensorDeviceClass.PRESENCE
        self._attr_extra_state_attributes = {
            ATTR_BOX: STATE_OFF,
            ATTR_WASP: STATE_OFF,
        }

        self.wasp: bool = False
        self._wasp_timer: ReusableTimer | None = None
        self._attr_is_on: bool = False

        self._wasp_sensors: list[str] = []
        self._box_sensors: list[str] = []

    async def async_added_to_hass(self) -> None:
        """Call to add the entity to hass."""
        await super().async_added_to_hass()
        await self.restore_state()

        # Check entities exist
        wasp_device_classes = self.area.config.get(
            WaspInABoxOptions.WASP_DEVICE_CLASSES
        )

        for device_class in wasp_device_classes:
            dc_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{self.area.slug}_aggregate_{device_class}"
            dc_state = self.hass.states.get(dc_entity_id)
            if not dc_state:
                continue
            self._wasp_sensors.append(dc_entity_id)

        for device_class in WASP_IN_A_BOX_BOX_DEVICE_CLASSES:
            dc_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{self.area.slug}_aggregate_{device_class}"
            dc_state = self.hass.states.get(dc_entity_id)
            if not dc_state:
                continue
            self._box_sensors.append(dc_entity_id)

        # Initialize timer if timeout configured
        if self._wasp_timeout > 0:

            async def forget_wasp(now):
                self.wasp = False
                self._attr_extra_state_attributes[ATTR_WASP] = STATE_OFF
                self._attr_is_on = self.wasp
                self.schedule_update_ha_state()

            self._wasp_timer = ReusableTimer(
                self.hass, self._wasp_timeout * ONE_MINUTE, forget_wasp
            )

        # Add listeners
        if self._wasp_sensors:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._wasp_sensors, self._async_wasp_sensor_state_change
                )
            )
        if self._box_sensors:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._box_sensors, self._async_box_sensor_state_change
                )
            )

    async def async_will_remove_from_hass(self) -> None:
        """Call to remove the entity to hass."""
        if self._wasp_timer:
            await self._wasp_timer.async_remove()
        await super().async_will_remove_from_hass()

    @callback
    async def _async_wasp_sensor_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Register wasp sensor state change event."""

        new_state: State | None = event.data.get("new_state")
        old_state: State | None = event.data.get("old_state")

        # Ignore state reports that aren't really a state change
        if new_state is None or old_state is None:
            return
        if new_state.state == old_state.state:
            return

        self.wasp_in_a_box(wasp_state=new_state.state)

    @callback
    async def _async_box_sensor_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Register box sensor state change event."""

        new_state: State | None = event.data.get("new_state")
        old_state: State | None = event.data.get("old_state")

        # Ignore state reports that aren't really a state change
        if new_state is None or old_state is None:
            return
        if new_state.state == old_state.state:
            return

        if self._delay:
            self.wasp = False
            self._attr_is_on = self.wasp
            self._attr_extra_state_attributes[ATTR_BOX] = new_state.state
            self._attr_extra_state_attributes[ATTR_WASP] = STATE_OFF
            self.schedule_update_ha_state()
            if self._wasp_timer:
                self._wasp_timer.cancel()
            self.hass.loop.call_later(
                self._delay, self.wasp_in_a_box, None, new_state.state
            )
        else:
            self.wasp_in_a_box(box_state=new_state.state)

    def wasp_in_a_box(
        self,
        wasp_state: str | None = None,
        box_state: str | None = None,
    ) -> None:
        """Perform Wasp In A Box Logic."""

        if not wasp_state:
            # Get Wasp State
            wasp_state = STATE_OFF
            for wasp_sensor in self._wasp_sensors:
                wasp_sensor_state = self.hass.states.get(wasp_sensor)
                if not wasp_sensor_state:
                    continue
                if wasp_sensor_state.state == STATE_ON:
                    wasp_state = STATE_ON
                    break

        if not box_state:
            # Get Box State
            box_state = STATE_OFF
            for box_sensor in self._box_sensors:
                box_sensor_state = self.hass.states.get(box_sensor)
                if not box_sensor_state:
                    continue
                if box_sensor_state.state == STATE_ON:
                    box_state = STATE_ON
                    break

        # Main Logic
        if wasp_state == STATE_ON:
            self.wasp = True
            if self._wasp_timer:
                self._wasp_timer.cancel()
        elif box_state == STATE_ON:
            self.wasp = False
            if self._wasp_timer:
                self._wasp_timer.cancel()
        else:
            # Wasp is OFF and Box is OFF → start timer
            if self._wasp_timer and self.wasp:
                self._wasp_timer.start()

        self._attr_extra_state_attributes[ATTR_BOX] = box_state
        self._attr_extra_state_attributes[ATTR_WASP] = wasp_state

        self._attr_is_on = self.wasp
        self.schedule_update_ha_state()
