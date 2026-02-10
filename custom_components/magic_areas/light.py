"""Platform file for Magic Area's light entities."""

import logging

from homeassistant.components.group.light import FORWARDED_ATTRIBUTES, LightGroup
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    AREA_PRIORITY_STATES,
    EMPTY_STRING,
    AreaStates,
    ConfigDomains,
    Features,
    MagicAreasEvents,
    MagicAreasFeatureInfoLightGroups,
)
from custom_components.magic_areas.const.light_groups import (
    LIGHT_GROUP_ALL,
    LIGHT_GROUP_ALL_ICON,
    LightGroupActOn,
    LightGroupEntryOptions,
    LightGroupOptions,
    slugify_group_name,
)
from custom_components.magic_areas.helpers.area import get_area_from_config_entry
from custom_components.magic_areas.util import cleanup_removed_entries

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the area light config entry."""

    area: MagicArea | None = get_area_from_config_entry(hass, config_entry)
    assert area is not None

    # Check feature availability
    if not area.has_feature(Features.LIGHT_GROUPS):
        return

    # Check if there are any lights
    if not area.has_entities(LIGHT_DOMAIN):
        _LOGGER.debug("%s: No %s entities for area.", area.name, LIGHT_DOMAIN)
        return

    light_entities = [e["entity_id"] for e in area.entities[LIGHT_DOMAIN]]

    light_groups = []

    # Create light groups
    if area.is_meta():
        # Meta-areas use simple all_lights group
        light_groups.append(
            MagicLightGroup(area, light_entities, translation_key=LIGHT_GROUP_ALL)
        )
    else:
        # Get feature config
        feature_config = area.config.get_raw(ConfigDomains.FEATURES, {}).get(
            Features.LIGHT_GROUPS, {}
        )

        groups = feature_config.get(LightGroupOptions.GROUPS.key, [])

        # Create custom light groups from groups list
        for group_config in groups:
            group_name = group_config[LightGroupEntryOptions.NAME.key]
            group_lights_config = group_config.get(
                LightGroupEntryOptions.LIGHTS.key, []
            )

            # Filter to lights actually in this area
            group_lights = [
                light for light in group_lights_config if light in light_entities
            ]

            if not group_lights:
                _LOGGER.debug(
                    "%s: Skipping group '%s' - no lights in area", area.name, group_name
                )
                continue

            _LOGGER.debug(
                "%s: Creating group '%s' with lights: %s",
                area.name,
                group_name,
                group_lights,
            )

            light_group = AreaLightGroup(area, group_lights, group_config=group_config)
            light_groups.append(light_group)

        # Create "All Lights" aggregator group
        if light_groups:
            _LOGGER.debug(
                "%s: Creating 'All Lights' group with %d lights",
                area.name,
                len(light_entities),
            )
            light_groups.append(AreaLightGroup(area, light_entities, group_config=None))

    # Create all groups
    if light_groups:
        async_add_entities(light_groups)

    if LIGHT_DOMAIN in area.magic_entities:
        cleanup_removed_entries(
            area.hass, light_groups, area.magic_entities[LIGHT_DOMAIN]
        )


class MagicLightGroup(MagicEntity, LightGroup):
    """Magic Light Group for Meta-areas."""

    feature_info = MagicAreasFeatureInfoLightGroups()

    def __init__(
        self, area, entities, name=EMPTY_STRING, translation_key: str | None = None
    ):
        """Initialize parent class and state."""
        MagicEntity.__init__(
            self, area, domain=LIGHT_DOMAIN, translation_key=translation_key
        )
        LightGroup.__init__(
            self,
            name=name,
            unique_id=self.unique_id,
            entity_ids=entities,
            mode=False,
        )
        if not name:
            delattr(self, "_attr_name")

    def _get_active_lights(self) -> list[str]:
        """Return list of lights that are on."""
        active_lights = []
        for entity_id in self._entity_ids:
            light_state = self.hass.states.get(entity_id)
            if not light_state:
                continue
            if light_state.state == STATE_ON:
                active_lights.append(entity_id)

        return active_lights

    async def async_turn_on(self, **kwargs) -> None:
        """Forward the turn_on command to lights that are already on.

        This prevents turning on lights that are off when adjusting brightness
        or other attributes of the group.
        """

        data = {
            key: value for key, value in kwargs.items() if key in FORWARDED_ATTRIBUTES
        }

        # Get active lights or default to all lights
        active_lights = self._get_active_lights() or self._entity_ids
        _LOGGER.debug(
            "%s: restricting call to active lights: %s",
            self.area.name,
            str(active_lights),
        )

        data[ATTR_ENTITY_ID] = active_lights

        _LOGGER.debug("%s: Forwarded turn_on command: %s", self.area.name, data)

        await self.hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            data,
            blocking=True,
            context=self._context,
        )


class AreaLightGroup(MagicLightGroup):
    """Magic Light Group for regular areas."""

    def __init__(self, area, entities, *, group_config=None):
        """Initialize light group.

        Args:
            area: MagicArea instance
            entities: List of light entity IDs
            group_config: Group config dict. If None, this is "All Lights" aggregator

        """
        if group_config is None:
            # All Lights aggregator group
            MagicLightGroup.__init__(
                self, area, entities, translation_key=LIGHT_GROUP_ALL
            )
            self._icon = LIGHT_GROUP_ALL_ICON
            self.assigned_states = []
            self.act_on = []
            self._group_config = None

        else:
            # Custom user-defined group
            group_name = group_config[LightGroupEntryOptions.NAME.key]
            group_slug = slugify_group_name(group_name)
            MagicLightGroup.__init__(
                self, area, entities, name=group_name, translation_key=group_slug
            )

            # Add UUID to unique_id for stability across renames
            group_uuid = group_config[LightGroupEntryOptions.UUID.key]
            self._attr_unique_id = f"{self._attr_unique_id}_{group_uuid}"

            self.assigned_states = group_config.get(
                LightGroupEntryOptions.STATES.key, LightGroupEntryOptions.STATES.default
            )
            self.act_on = group_config.get(
                LightGroupEntryOptions.ACT_ON.key, LightGroupEntryOptions.ACT_ON.default
            )
            self._icon = group_config.get(
                LightGroupEntryOptions.ICON.key, LightGroupEntryOptions.ICON.default
            )
            self._group_config = group_config

        # Common initialization
        self.controlling = True
        self.controlled = False

        # Add static attributes
        self._attr_extra_state_attributes["lights"] = self._entity_ids
        self._attr_extra_state_attributes["controlling"] = self.controlling

        # Add group-specific attributes for custom groups
        if self._group_config:
            self._attr_extra_state_attributes["states"] = self.assigned_states
            self._attr_extra_state_attributes["act_on"] = self.act_on

        group_identifier = group_name if group_config else "All Lights"
        self.logger.debug(
            "%s: Light group (%s) created with %d entities",
            self.area.name,
            group_identifier,
            len(self._entity_ids),
        )

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    async def async_added_to_hass(self) -> None:
        """Restore state and setup listeners."""
        # Get last state
        last_state = await self.async_get_last_state()

        if last_state:
            self.logger.debug(
                "%s: State restored [state=%s]", self.name, last_state.state
            )
            self._attr_is_on = last_state.state == STATE_ON

            if "controlling" in last_state.attributes:
                controlling = last_state.attributes["controlling"]
                self.controlling = controlling
                self._attr_extra_state_attributes["controlling"] = self.controlling
        else:
            self._attr_is_on = False

        self.schedule_update_ha_state()

        # Setup state change listeners
        await self._setup_listeners()

        await super().async_added_to_hass()

    async def _setup_listeners(self, _=None) -> None:
        """Set up listeners for area state change."""
        async_dispatcher_connect(
            self.hass, MagicAreasEvents.AREA_STATE_CHANGED, self.area_state_changed
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.entity_id],
                self.group_state_changed,
            )
        )

    # State Change Handling

    def area_state_changed(self, area_id, states_tuple):
        """Handle area state change event."""
        if area_id != self.area.id:
            self.logger.debug(
                "%s: Area state change event not for us. Skipping. (req: %s/self: %s)",
                self.name,
                area_id,
                self.area.id,
            )
            return

        if not self.is_control_enabled():
            self.logger.debug(
                "%s: Automatic control for light group is disabled, skipping...",
                self.name,
            )
            return False

        self.logger.debug("%s: Light group detected area state change", self.name)

        # Route based on group type
        if self._group_config is None:
            # All Lights: Only turn off when clear
            return self._handle_all_lights_state_change(states_tuple)
        # Custom group: Handle based on configured states
        return self._handle_custom_group_state_change(states_tuple)

    def _handle_all_lights_state_change(self, states_tuple):
        """Handle state change for All Lights group - simple off when clear."""
        new_states, _lost_states = states_tuple

        if AreaStates.CLEAR in new_states:
            self.logger.debug("%s: Area is clear, should turn off lights!", self.name)
            self.reset_control()
            return self._turn_off()

        return False

    def _handle_custom_group_state_change(self, states_tuple):
        """Handle state change for custom groups based on assigned states."""
        new_states, lost_states = states_tuple

        if AreaStates.CLEAR in new_states:
            self.logger.debug(
                "%s: Area is clear, reset control state and Noop!", self.name
            )
            self.reset_control()
            return False

        if self.area.has_state(AreaStates.BRIGHT):
            # Only turn off lights when bright if the room was already occupied
            if (
                AreaStates.BRIGHT in new_states
                and AreaStates.OCCUPIED not in new_states
            ):
                self.controlled = True
                self._turn_off()
            return False

        # Only react to actual secondary state changes
        if not new_states and not lost_states:
            self.logger.debug("%s: No new or lost states, noop.", self.name)
            return False

        # Do not handle lights that are not tied to a state
        if not self.assigned_states:
            self.logger.debug("%s: No assigned states. noop.", self.name)
            return False

        # If area clear, do nothing (All Lights group will handle)
        if not self.area.is_occupied():
            self.logger.debug("%s: Area not occupied, ignoring.", self.name)
            return False

        self.logger.debug(
            "%s: Assigned states: %s. New states: %s / Lost states %s",
            self.name,
            str(self.assigned_states),
            str(new_states),
            str(lost_states),
        )

        # Calculate valid states (if area has states we listen to)
        # and check if area is under one or more priority state
        valid_states = [
            state for state in self.assigned_states if self.area.has_state(state)
        ]
        has_priority_states = any(
            self.area.has_state(state) for state in AREA_PRIORITY_STATES
        )
        non_priority_states = [
            state for state in valid_states if state not in AREA_PRIORITY_STATES
        ]

        self.logger.debug(
            "%s: Has priority states? %s. Non-priority states: %s",
            self.name,
            has_priority_states,
            str(non_priority_states),
        )

        # ACT ON Control
        # Do not act on occupancy change if not defined on act_on
        if (
            AreaStates.OCCUPIED in new_states
            and LightGroupActOn.OCCUPANCY not in self.act_on
        ):
            self.logger.debug(
                "Area occupancy change detected but not configured to act on. Skipping."
            )
            return False

        # Do not act on state change if not defined on act_on
        if (
            AreaStates.OCCUPIED not in new_states
            and LightGroupActOn.STATE not in self.act_on
        ):
            self.logger.debug(
                "Area state change detected but not configured to act on. Skipping."
            )
            return False

        # Prefer priority states when present
        if has_priority_states:
            for non_priority_state in non_priority_states:
                valid_states.remove(non_priority_state)

        if valid_states:
            self.logger.debug(
                "%s: Area has valid states (%s), Group should turn on!",
                self.name,
                str(valid_states),
            )
            self.controlled = True
            return self._turn_on()

        # Only turn lights off if not going into dark state
        if AreaStates.DARK in new_states:
            self.logger.debug(
                "%s: Entering %s state, noop.", self.name, AreaStates.DARK
            )
            return False

        # Turn off if we're a PRIORITY_STATE and we're coming out of it
        out_of_priority_states = [
            state
            for state in AREA_PRIORITY_STATES
            if state in self.assigned_states and state in lost_states
        ]
        if out_of_priority_states:
            self.controlled = True
            return self._turn_off()

        # Do not turn off if no new PRIORITY_STATES
        new_priority_states = [
            state for state in AREA_PRIORITY_STATES if state in new_states
        ]
        if not new_priority_states:
            self.logger.debug("%s: No new priority states. Noop.", self.name)
            return False

        self.controlled = True
        return self._turn_off()

    # Light Handling

    def _turn_on(self):
        """Turn on light if it's not already on and if we're controlling it."""
        if not self.controlling:
            return False

        if self.is_on:
            return False

        self.controlled = True

        service_data = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call(LIGHT_DOMAIN, SERVICE_TURN_ON, service_data)

        return True

    def _turn_off(self):
        """Turn off light if it's not already off and we're controlling it."""
        if not self.controlling:
            return False

        if not self.is_on:
            return False

        service_data = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call(LIGHT_DOMAIN, SERVICE_TURN_OFF, service_data)

        return True

    # Control Release

    def is_control_enabled(self):
        """Check if light control is enabled by checking light control switch state."""
        entity_id = (
            f"{SWITCH_DOMAIN}.magic_areas_light_groups_{self.area.slug}_light_control"
        )

        switch_entity = self.hass.states.get(entity_id)

        if not switch_entity:
            return False

        return switch_entity.state.lower() == STATE_ON

    def reset_control(self):
        """Reset control status."""
        self.controlling = True
        self._attr_extra_state_attributes["controlling"] = self.controlling
        self.schedule_update_ha_state()
        self.logger.debug("%s: Control Reset.", self.name)

    def group_state_changed(self, event):
        """Handle group state change events."""
        # If area is not occupied, reset control
        if not self.area.is_occupied():
            self.reset_control()
        else:
            origin_event = event.context.origin_event

            # All Lights group doesn't track manual changes
            if self._group_config is None:
                return False

            # Ignore certain events for custom groups
            if origin_event.event_type == "state_changed":
                # Skip non ON/OFF state changes
                if (
                    "old_state" not in origin_event.data
                    or not origin_event.data["old_state"]
                    or not origin_event.data["old_state"].state
                    or origin_event.data["old_state"].state not in [STATE_ON, STATE_OFF]
                ):
                    return False
                if (
                    "new_state" not in origin_event.data
                    or not origin_event.data["new_state"]
                    or not origin_event.data["new_state"].state
                    or origin_event.data["new_state"].state not in [STATE_ON, STATE_OFF]
                ):
                    return False

                # Skip restored events
                if (
                    "restored" in origin_event.data["old_state"].attributes
                    and origin_event.data["old_state"].attributes["restored"]
                ):
                    return False

            # Handle custom group manual control
            if self.controlled:
                self.controlled = False
                self.logger.debug("%s: Group controlled by us.", self.name)
            else:
                # If not, it was manually controlled, stop controlling
                self.controlling = False
                self.logger.debug("%s: Group controlled by something else.", self.name)

        # Update attribute
        self._attr_extra_state_attributes["controlling"] = self.controlling
        self.schedule_update_ha_state()

        return True
