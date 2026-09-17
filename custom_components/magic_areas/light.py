"""Platform file for Magic Area's light entities."""

import logging
import uuid

from slugify import slugify

from homeassistant.components.group.light import FORWARDED_ATTRIBUTES, LightGroup
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import Context, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    EMPTY_STRING,
    AreaStates,
    ConfigDomains,
    Features,
    MagicAreasEvents,
    MagicAreasFeatureInfoLightGroups,
)
from custom_components.magic_areas.const.light_groups import (
    LIGHT_GROUP_CONTEXT_PREFIX,
    LightGroupAllLightsConfig,
    LightGroupAttributes,
    LightGroupEntryOptions,
    LightGroupOperationMode,
    LightGroupOptions,
    LightGroupTurnOffWhen,
    LightGroupTurnOnWhen,
)
from custom_components.magic_areas.helpers.area import get_area_from_config_entry
from custom_components.magic_areas.util import cleanup_removed_entries

_LOGGER = logging.getLogger(__name__)

ADAPTIVE_LIGHTING_CONTEXT_TOKEN: str = ":al:"

# Entry Setup


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

    # Create "All Lights"
    light_groups.append(
        MagicLightGroup(
            area,
            light_entities,
            icon=LightGroupAllLightsConfig.ICON.value,
            translation_key=LightGroupAllLightsConfig.NAME.value,
        )
    )

    # Create custom groups
    feature_config = area.config.get_raw(ConfigDomains.FEATURES, {}).get(
        Features.LIGHT_GROUPS, {}
    )

    groups = feature_config.get(LightGroupOptions.GROUPS.key, [])

    # Create custom light groups from groups list
    for group_config in groups:
        group_name = group_config[LightGroupEntryOptions.NAME.key]
        group_lights_config = group_config.get(LightGroupEntryOptions.LIGHTS.key, [])

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

        light_group = AreaLightGroup(area, group_config)
        light_groups.append(light_group)

    # Create all groups
    if light_groups:
        async_add_entities(light_groups)

    if LIGHT_DOMAIN in area.magic_entities:
        cleanup_removed_entries(
            area.hass, light_groups, area.magic_entities[LIGHT_DOMAIN]
        )


# Classes


class MagicLightGroup(MagicEntity, LightGroup):
    """Magic Light Group for Meta-areas."""

    feature_info = MagicAreasFeatureInfoLightGroups()

    def __init__(
        self,
        area,
        entities,
        *,
        name=EMPTY_STRING,
        icon=None,
        translation_key: str | None = None,
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

        if icon:
            self._attr_icon = icon

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

        _LOGGER.debug(
            "%s (%s): Forwarded turn_on command: %s", self.area.name, self.name, data
        )

        await self.hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            data,
            blocking=True,
            context=self._context,
        )


class AreaLightGroup(MagicLightGroup):
    """Magic Light Group for regular areas."""

    def __init__(self, area, group_config):
        """Initialize light group.

        Args:
            area: MagicArea instance
            group_config: Group config dict

        """
        # Custom user-defined group
        group_name = group_config[LightGroupEntryOptions.NAME.key]
        MagicLightGroup.__init__(
            self,
            area,
            group_config[LightGroupEntryOptions.LIGHTS.key],
            name=group_name,
            translation_key=slugify(group_name).replace("-", "_"),
        )

        # Set group properties
        self.manual_mode = False
        self.assigned_states = set(
            group_config.get(LightGroupEntryOptions.STATES.key, [])
        )
        self.turn_on_when = set(
            group_config.get(
                LightGroupEntryOptions.TURN_ON_WHEN.key,
                LightGroupEntryOptions.TURN_ON_WHEN.default,
            )
        )
        self.turn_off_when = set(
            group_config.get(
                LightGroupEntryOptions.TURN_OFF_WHEN.key,
                LightGroupEntryOptions.TURN_OFF_WHEN.default,
            )
        )
        self.require_dark = bool(
            group_config.get(
                LightGroupEntryOptions.REQUIRE_DARK.key,
                LightGroupEntryOptions.REQUIRE_DARK.default,
            )
        )

        _LOGGER.debug(
            "%s: Light group (%s) created with %d entities",
            self.area.name,
            group_name if group_config else "All Lights",
            len(self._entity_ids),
        )

    # Callbacks

    async def async_added_to_hass(self) -> None:
        """Restore state and setup listeners."""
        # Get last state
        last_state = await self.async_get_last_state()

        if last_state:
            _LOGGER.debug(
                "%s (%s): State restored [state=%s]",
                self.area.name,
                self.name,
                last_state.state,
            )
            self._attr_is_on = last_state.state == STATE_ON

            if LightGroupAttributes.MODE in last_state.attributes:
                # Light groups are always reset to manual=False on clear, if area is occupied, ignore saved state and force False
                if self.area.is_occupied():
                    manual_mode = last_state.attributes[LightGroupAttributes.MODE.value]
                    self.manual_mode = (
                        manual_mode == LightGroupOperationMode.MANUAL.value
                    )
                else:
                    self.manual_mode = False
        else:
            self._attr_is_on = False

        self.update_attributes()

        # Subscribe to area state changes (area-specific event)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{MagicAreasEvents.AREA_STATE_CHANGED}_{self.area.id}",
                self.area_state_changed,
            )
        )

        # Also subscribe to exterior area events if needed for EXTERIOR_BRIGHT trigger
        if LightGroupTurnOffWhen.EXTERIOR_BRIGHT in self.turn_off_when:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"{MagicAreasEvents.AREA_STATE_CHANGED}_exterior",
                    self.area_state_changed,
                )
            )

        # Subscribe to child light state changes to detect manual control
        @callback
        def _child_light_changed(event):
            """Handle child light state change."""
            # Check if the state change was triggered by our magic context
            # If not, it's a manual change - enter manual mode

            if self._should_release_control(event.context):
                self._manual_mode_set_or_reset()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_ids, _child_light_changed
            )
        )

        await super().async_added_to_hass()

    # General Helpers

    def _is_control_enabled(self):
        """Check if light control is enabled by checking light control switch state."""

        entity_id = (
            f"{SWITCH_DOMAIN}.magic_areas_light_groups_{self.area.slug}_light_control"
        )

        switch_entity = self.hass.states.get(entity_id)

        if not switch_entity:
            return False

        return switch_entity.state.lower() == STATE_ON

    def _generate_context_id(self):
        """Generate context id with prefix."""

        return Context(id="_".join([LIGHT_GROUP_CONTEXT_PREFIX, uuid.uuid4().hex]))

    def _has_required_states(self, current_states: set[str]) -> bool:
        """Check if area has any of the required states for this group."""

        # Empty configured states is unexpected, fail
        if not self.assigned_states:
            return False

        # Area must have at least one configured state
        return bool(self.assigned_states.intersection(current_states))

    def _get_current_area_states(self) -> set[str]:
        """Get current states of the area.

        The area state system handles brightness fallback logic internally
        (area sensor → exterior sensor → sun.sun), so `dark` or `bright`
        will be present in the returned states based on that fallback chain.
        """

        return self._apply_state_priority(set(self.area.states))

    def _apply_state_priority(self, states: set[str]) -> set[str]:
        """Apply state priority rules to filter states.

        Priority order (highest to lowest):
        1. Sleep state
        2. User-defined states
        3. Built-in states (occupied, extended, dark, bright, clear)

        Returns:
            Filtered set of states based on priority rules

        """

        # If sleep is present, return only sleep
        if AreaStates.SLEEP in states:
            return {AreaStates.SLEEP}

        # Get user-defined state names (exclude 'sleep' since it's built-in)
        user_defined_state_names = set(self.area.secondary_state_entities.keys()) - {
            "sleep"
        }
        user_defined_in_current = states & user_defined_state_names

        # If any user-defined states present, return only those
        if user_defined_in_current:
            return user_defined_in_current

        # Otherwise return all states (all built-in states)
        return states

    def update_attributes(self):
        """Update light group attributes."""

        self._attr_extra_state_attributes.update(
            {
                LightGroupAttributes.MODE.value: (
                    LightGroupOperationMode.MANUAL.value
                    if self.manual_mode
                    else LightGroupOperationMode.MAGIC.value
                )
            }
        )

        self.schedule_update_ha_state()

    # Turn on / off helpers

    def _turn_on_lights(self) -> None:
        """Turn on lights with magic context."""
        self.hass.services.call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": self.entity_id},
            context=self._generate_context_id(),
        )

    def _turn_off_lights(self) -> None:
        """Turn off lights with magic context."""
        self.hass.services.call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {"entity_id": self.entity_id},
            context=self._generate_context_id(),
        )

    # Turn on / off decision logic

    def _should_turn_off_on_exterior_bright(
        self, new_states: set[str], lost_states: set[str]
    ) -> bool:
        """Check if lights should turn off due to exterior becoming bright."""

        _LOGGER.debug(
            "%s (%s): Checking if should turn off due exterior brightness. new=%s",
            self.area.name,
            self.name,
            new_states,
        )

        if not self.is_on:
            _LOGGER.debug("%s (%s): Light is already off", self.area.name, self.name)
            return False

        # Manual mode blocks all other automatic turn-offs
        if self.manual_mode:
            _LOGGER.debug(
                "%s (%s): Manual mode blocks turn-off", self.area.name, self.name
            )
            return False

        if LightGroupTurnOffWhen.EXTERIOR_BRIGHT not in self.turn_off_when:
            _LOGGER.debug(
                "%s (%s): No turn-off triggers configured for Exterior Brightness",
                self.area.name,
                self.name,
            )
            return False

        return AreaStates.BRIGHT in new_states and AreaStates.DARK in lost_states

    def _should_turn_off(
        self, current_states: set[str], new_states: set[str], lost_states: set[str]
    ) -> bool:
        """Determine if lights should turn off based on current conditions."""
        _LOGGER.debug(
            "%s (%s): Checking if should turn off. current=%s, new=%s, lost=%s",
            self.area.name,
            self.name,
            current_states,
            new_states,
            lost_states,
        )

        # Empty turn_off_when = never turn off automatically
        if not self.turn_off_when:
            _LOGGER.debug(
                "%s (%s): No turn-off triggers configured", self.area.name, self.name
            )
            return False

        # Light control is the primary check
        if not self._is_control_enabled():
            _LOGGER.debug(
                "%s (%s): Light control disabled, blocking turn-off",
                self.area.name,
                self.name,
            )
            return False

        # Are we off already?
        if not self.is_on:
            _LOGGER.debug(
                "%s (%s): Light group off, turn-off unnecessary.",
                self.area.name,
                self.name,
            )
            return False

        # Area just got occupied
        if AreaStates.OCCUPIED in new_states and AreaStates.CLEAR in lost_states:
            _LOGGER.debug(
                "%s (%s): Area just got occupied, blocking turn-off",
                self.area.name,
                self.name,
            )
            return False

        # AREA_CLEAR
        if LightGroupTurnOffWhen.AREA_CLEAR in self.turn_off_when:
            if AreaStates.CLEAR in new_states and AreaStates.OCCUPIED in lost_states:
                _LOGGER.debug(
                    "%s (%s): AREA_CLEAR trigger - turning off",
                    self.area.name,
                    self.name,
                )
                return True

        # Manual mode blocks all other automatic turn-offs
        if self.manual_mode:
            _LOGGER.debug(
                "%s (%s): Manual mode blocks turn-off", self.area.name, self.name
            )
            return False

        # Check STATE_LOSS - turn off when we no longer have any assigned states
        if LightGroupTurnOffWhen.STATE_LOSS in self.turn_off_when:
            if self.area.is_occupied() and self.assigned_states:
                # Check if we lost any assigned state OR don't have any left after filtering
                lost_assigned = self.assigned_states.intersection(lost_states)
                remaining_assigned = self.assigned_states.intersection(current_states)

                if lost_assigned or not remaining_assigned:
                    if not remaining_assigned:
                        _LOGGER.debug(
                            "%s (%s): STATE_LOSS trigger - no assigned states remain (lost: %s)",
                            self.area.name,
                            self.name,
                            lost_assigned or "filtered by priority",
                        )
                        return True

        # Note: EXTERIOR_BRIGHT is handled separately in area_state_changed
        # Default fail False
        _LOGGER.debug("%s (%s): No turn-off conditions met", self.area.name, self.name)
        return False

    def _should_turn_on(
        self, current_states: set[str], new_states: set[str], lost_states: set[str]
    ) -> bool:
        """Determine if lights should turn on based on current conditions."""
        _LOGGER.debug(
            "%s (%s): Checking if should turn on. current=%s, new=%s, lost=%s",
            self.area.name,
            self.name,
            current_states,
            new_states,
            lost_states,
        )

        # Light control is the primary check
        if not self._is_control_enabled():
            _LOGGER.debug(
                "%s (%s): Light control disabled, blocking turn-on",
                self.area.name,
                self.name,
            )
            return False

        # Are we on already?
        if self.is_on:
            _LOGGER.debug(
                "%s (%s): Light group on, turn-on unnecessary.",
                self.area.name,
                self.name,
            )
            return False

        # Manual mode blocks automatic turn-on
        if self.manual_mode:
            _LOGGER.debug(
                "%s (%s): Manual mode active, blocking turn-on",
                self.area.name,
                self.name,
            )
            return False

        # Bail on non-occupied areas
        if not self.area.is_occupied():
            _LOGGER.debug(
                "%s (%s): Area is clear, blocking turn-on",
                self.area.name,
                self.name,
            )
            return False

        # Check darkness requirement (one-shot check)
        if self.require_dark:
            if not self.area.is_area_dark():
                _LOGGER.debug(
                    "%s (%s): Require dark but area is bright",
                    self.area.name,
                    self.name,
                )
                return False

        # Check if any turn-on trigger fired
        if not self._check_turn_on_triggers(new_states):
            _LOGGER.debug("%s (%s): No triggers fired.", self.area.name, self.name)

            # If we didn't got a hit on any triggers, we still need to check if this light should be turned on if
            # 1. If AreaStates.EXTENDED is on current_states and we have AreaStates.EXTENDED
            # 2. If AreaStates.OCCUPIED is on current_states and we have AreaStates.OCCUPIED, but AreaStates.EXTENDED is NOT in current_states
            if (
                AreaStates.EXTENDED in current_states
                and AreaStates.EXTENDED not in self.assigned_states
            ):
                return False
            if (
                AreaStates.OCCUPIED in current_states
                and AreaStates.OCCUPIED not in self.assigned_states
            ):
                return False

        # Check if we have required states
        if not self._has_required_states(current_states):
            _LOGGER.debug(
                "%s (%s): Required states not met (need %s, have %s)",
                self.area.name,
                self.name,
                self.assigned_states,
                current_states,
            )
            return False

        _LOGGER.debug(
            "%s (%s): All conditions met, should turn on", self.area.name, self.name
        )
        return True

    def _check_turn_on_triggers(self, new_states: set[str]) -> bool:
        """Check if any configured turn-on trigger has fired."""

        _LOGGER.debug(
            "%s (%s): Checking turn-on triggers. new_states=%s, turn_on_when=%s",
            self.area.name,
            self.name,
            new_states,
            self.turn_on_when,
        )

        # AREA_OCCUPIED: area just became occupied
        if LightGroupTurnOnWhen.AREA_OCCUPIED in self.turn_on_when:
            if AreaStates.OCCUPIED in new_states:
                _LOGGER.debug(
                    "%s (%s): AREA_OCCUPIED trigger fired", self.area.name, self.name
                )
                return True

        # STATE_GAIN: area gained one of our configured states
        if LightGroupTurnOnWhen.STATE_GAIN in self.turn_on_when:
            if self.assigned_states.intersection(new_states):
                _LOGGER.debug(
                    "%s (%s): STATE_GAIN trigger fired (gained: %s)",
                    self.area.name,
                    self.name,
                    self.assigned_states.intersection(new_states),
                )
                return True

        # AREA_DARK: area just became dark
        if LightGroupTurnOnWhen.AREA_DARK in self.turn_on_when:
            if AreaStates.DARK in new_states:
                _LOGGER.debug(
                    "%s (%s): AREA_DARK trigger fired", self.area.name, self.name
                )
                return True

        _LOGGER.debug("%s (%s): No turn-on triggers fired", self.area.name, self.name)
        return False

    # Event handler

    def area_state_changed(
        self, area_id: str, states_tuple: tuple[set[str], set[str]]
    ) -> None:
        """Handle area state change events.

        Args:
            area_id: The area that changed state
            states_tuple: Tuple of (new_states, lost_states)

        """
        new_states, lost_states = states_tuple

        _LOGGER.debug(
            "%s (%s): area_state_changed called. area_id=%s, new_states=%s, lost_states=%s",
            self.area.name,
            self.name,
            area_id,
            new_states,
            lost_states,
        )

        # Handle exterior area events for EXTERIOR_BRIGHT trigger
        if area_id == "exterior":
            if self._should_turn_off_on_exterior_bright(new_states, lost_states):
                _LOGGER.debug(
                    "%s (%s): Exterior bright, turning off", self.area.name, self.name
                )
                self._turn_off_lights()
            return

        # Process events for our own area
        current_states = self._get_current_area_states()
        _LOGGER.debug(
            "%s (%s): Current area states: %s",
            self.area.name,
            self.name,
            current_states,
        )

        # Reset manual control on clear
        if AreaStates.CLEAR in new_states:
            self._manual_mode_reset()

        # Evaluate turn-off conditions first
        if self._should_turn_off(current_states, new_states, lost_states):
            _LOGGER.debug(
                "%s (%s): Turn-off conditions met, turning off",
                self.area.name,
                self.name,
            )
            self._turn_off_lights()
            return

        # Evaluate turn-on conditions
        if self._should_turn_on(current_states, new_states, lost_states):
            _LOGGER.debug(
                "%s (%s): Turn-on conditions met, turning on", self.area.name, self.name
            )
            self._turn_on_lights()
        else:
            _LOGGER.debug(
                "%s (%s): Turn-on conditions not met", self.area.name, self.name
            )

    # Manual call interceptors

    def _manual_mode_set(self):
        """Set manual mode and update attributes."""
        self.manual_mode = True
        self.update_attributes()
        _LOGGER.debug("%s (%s): Manual mode set.", self.area.name, self.name)

    def _manual_mode_reset(self):
        """Reset manual mode back to magic mode and update attributes."""
        self.manual_mode = False
        self.update_attributes()
        _LOGGER.debug("%s (%s): Manual mode reset.", self.area.name, self.name)

    def _manual_mode_set_or_reset(self):
        """Set or reset manual mode depending on area occupancy."""

        if self.area.is_occupied():
            self._manual_mode_set()
        else:
            self._manual_mode_reset()

    def _should_release_control(self, context: Context | None = None) -> bool:
        """Check if control should be released."""

        _context: Context | None = self._context

        if context:
            _context = context

        # Release if context not set
        if not _context:
            return True

        # Don't release if it's our own context
        if any(
            item.startswith(LIGHT_GROUP_CONTEXT_PREFIX)
            for item in (_context.id, _context.parent_id)
            if item is not None
        ):
            return False

        # Don't release if it's Adaptive Lighting's context
        if any(
            ADAPTIVE_LIGHTING_CONTEXT_TOKEN in item
            for item in (_context.id, _context.parent_id)
            if item is not None
        ):
            return False

        # Release by default
        return True

    def async_update_group_state(self) -> None:
        """Recompute aggregate state, then check who triggered it."""
        super().async_update_group_state()

        if not self._should_release_control():
            return

        self._manual_mode_set_or_reset()

    async def async_turn_on(self, **kwargs) -> None:
        """Handle turn on service call.

        Service calls on the light group entity are treated as manual control,
        unless they have the magic context prefix (programmatic/internal calls).
        """
        # Only enter manual mode if context is not magic
        if self._should_release_control():
            self._manual_mode_set_or_reset()

        await super().async_turn_on(**kwargs)

    async def async_turn_off(self, **kwargs) -> None:
        """Handle turn off service call.

        Service calls on the light group entity are treated as manual control,
        unless they have the magic context prefix (programmatic/internal calls).
        """
        # Only enter manual mode if context is not magic
        if self._should_release_control():
            self._manual_mode_set_or_reset()

        await super().async_turn_off(**kwargs)
