"""Fan Control switch."""

import logging

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import Event, EventStateChangedData
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    AreaStates,
    MagicAreasEvents,
    MagicAreasFeatureInfoFanGroups,
)
from custom_components.magic_areas.const.fan_groups import FanGroupOptions
from custom_components.magic_areas.switch.base import SwitchBase

_LOGGER = logging.getLogger(__name__)


class FanControlSwitch(SwitchBase):
    """Switch to enable/disable fan control."""

    feature_info = MagicAreasFeatureInfoFanGroups()
    _attr_entity_category = EntityCategory.CONFIG

    setpoint: float = 0.0
    tracked_entity_id: str

    def __init__(self, area: MagicArea) -> None:
        """Initialize the Fan control switch."""

        SwitchBase.__init__(self, area)

        tracked_device_class = self.area.config.get(
            FanGroupOptions.TRACKED_DEVICE_CLASS
        )
        self.tracked_entity_id = f"{SENSOR_DOMAIN}.magic_areas_aggregates_{self.area.slug}_aggregate_{tracked_device_class}"

        self.setpoint = float(self.area.config.get(FanGroupOptions.SETPOINT))

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, MagicAreasEvents.AREA_STATE_CHANGED, self.area_state_changed
            )
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.tracked_entity_id],
                self.aggregate_sensor_state_changed,
            )
        )

    async def aggregate_sensor_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Call update state from track state change event."""

        await self.run_logic(self.area.states)

    async def area_state_changed(self, area_id, states_tuple):
        """Handle area state change event."""

        if area_id != self.area.id:
            _LOGGER.debug(
                "%s: Area state change event not for us. Skipping. (event: %s/self: %s)",
                self.name,
                area_id,
                self.area.id,
            )
            return

        # pylint: disable-next=unused-variable
        new_states, lost_states = states_tuple
        await self.run_logic(states=new_states)

    async def run_logic(self, states: list[str]) -> None:
        """Run fan control logic."""

        if not self.is_on:
            _LOGGER.debug("%s: Control disabled, skipping.", self.name)
            return

        fan_group_entity_id = (
            f"{FAN_DOMAIN}.magic_areas_fan_groups_{self.area.slug}_fan_group"
        )

        if AreaStates.CLEAR in states:
            _LOGGER.debug("%s: Area clear, turning off fans", self.name)
            await self.hass.services.async_call(
                FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: fan_group_entity_id}
            )
            return

        required_state = self.area.config.get(FanGroupOptions.REQUIRED_STATE)

        if required_state not in states:
            _LOGGER.debug(
                "%s: Area not in required state '%s' (states: %s)",
                self.name,
                required_state,
                str(states),
            )
            return

        _LOGGER.debug(
            "%s: Area in required state '%s', checking tracked aggregate and setpoint.",
            self.name,
            required_state,
        )
        if self.is_setpoint_reached():
            _LOGGER.debug("%s: Setpoint reached, turning on fans", self.name)
            await self.hass.services.async_call(
                FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: fan_group_entity_id}
            )
        else:
            fan_group_state = self.hass.states.get(fan_group_entity_id)
            if fan_group_state and fan_group_state.state == STATE_ON:
                _LOGGER.debug("%s: Setpoint not reached, turning off fans", self.name)
                await self.hass.services.async_call(
                    FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: fan_group_entity_id}
                )
        return

    def is_setpoint_reached(self) -> bool:
        """Check wether the setpoint is reached."""

        tracked_sensor_state = self.hass.states.get(self.tracked_entity_id)

        if not tracked_sensor_state:
            _LOGGER.warning(
                "%s: Tracked sensor entity '%s' is not found. Please ensure aggregates are enabled and the selected device class is configured.",
                self.name,
                self.tracked_entity_id,
            )
            return False

        tracked_sensor_value = float(tracked_sensor_state.state)
        _LOGGER.debug(
            "%s: Setpoint value: %.2f, Sensor value: %.2f",
            self.name,
            self.setpoint,
            tracked_sensor_value,
        )
        return tracked_sensor_value >= self.setpoint
