"""Climate control feature switch."""

import logging

from homeassistant.components.climate.const import (
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    AreaStates,
    MagicAreasEvents,
    MagicAreasFeatureInfoClimateControl,
)
from custom_components.magic_areas.const.climate_control import ClimateControlOptions
from custom_components.magic_areas.switch.base import SwitchBase

_LOGGER = logging.getLogger(__name__)


class ClimateControlSwitch(SwitchBase):
    """Switch to enable/disable climate control."""

    feature_info = MagicAreasFeatureInfoClimateControl()
    _attr_entity_category = EntityCategory.CONFIG

    preset_map: dict[str, str]
    climate_entity_id: str | None

    def __init__(self, area: MagicArea) -> None:
        """Initialize the Climate control switch."""

        SwitchBase.__init__(self, area)

        self.climate_entity_id = self.area.config.get(ClimateControlOptions.ENTITY_ID)

        if not self.climate_entity_id:
            raise ValueError("Climate entity not set")

        self.preset_map = {
            AreaStates.CLEAR: self.area.config.get(ClimateControlOptions.PRESET_CLEAR),
            AreaStates.OCCUPIED: self.area.config.get(
                ClimateControlOptions.PRESET_OCCUPIED
            ),
            AreaStates.SLEEP: self.area.config.get(ClimateControlOptions.PRESET_SLEEP),
            AreaStates.EXTENDED: self.area.config.get(
                ClimateControlOptions.PRESET_EXTENDED
            ),
        }

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{MagicAreasEvents.AREA_STATE_CHANGED}_{self.area.id}",
                self.area_state_changed,
            )
        )

    async def area_state_changed(
        self, area_id: str, states_tuple: set[set[AreaStates]]
    ) -> None:
        """Handle area state change event."""

        if not self.is_on:
            self.logger.debug("%s: Control disabled. Skipping.", self.name)
            return

        new_states: set[AreaStates]
        lost_states: set[AreaStates]

        new_states, lost_states = states_tuple

        if new_states == lost_states:
            self.logger.debug("%s: No state change. Skipping.", self.name)
            return

        # Process new states if available.
        # This is the main behavior of triggering when gaining a state.
        if new_states:
            return await self.process_states(new_states)

        # If no new states but lost states, send all states.
        # This is necessary when leaving priority states like sleep,
        # that don't have an opposite state as occupied/clear.
        if lost_states:
            return await self.process_states(self.area.states)

    async def process_states(self, area_states: set[AreaStates]):
        """Process available states and apply corresponding preset."""

        priority_states: list[AreaStates] = [
            AreaStates.SLEEP,
            AreaStates.EXTENDED,
            AreaStates.OCCUPIED,
        ]

        # Handle area clear because the other states doesn't matter
        if AreaStates.CLEAR in area_states:
            if self.preset_map[AreaStates.CLEAR]:
                await self.apply_preset(AreaStates.CLEAR)
            return

        # Handle each state top priority to last, returning early
        for p_state in priority_states:
            if p_state in area_states and self.preset_map[p_state]:
                return await self.apply_preset(p_state)

    async def apply_preset(self, state_name: AreaStates):
        """Set climate entity to given preset."""

        selected_preset: str = self.preset_map[state_name]

        try:
            await self.hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_PRESET_MODE,
                {
                    ATTR_ENTITY_ID: self.climate_entity_id,
                    ATTR_PRESET_MODE: selected_preset,
                },
            )
        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            self.logger.error("%s: Error applying preset: %s", self.name, str(e))
