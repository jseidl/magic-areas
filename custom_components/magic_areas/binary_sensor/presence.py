"""Main presence tracking entity for Magic Areas."""

import asyncio
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import logging

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import STATE_ON
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)

from custom_components.magic_areas.base.entities import BinaryMagicEntity
from custom_components.magic_areas.base.magic import MagicArea, MagicMetaArea
from custom_components.magic_areas.const import (
    EMPTY_STRING,
    INVALID_STATES,
    ONE_MINUTE,
    PRESENCE_SENSOR_VALID_ON_STATES,
    UPDATE_INTERVAL,
    AreaAttributes,
    AreaConfigOptions,
    AreaStates,
    CalculationMode,
    CommonAttributes,
    MagicAreasEvents,
    MagicAreasFeatureInfo,
    MagicAreasFeatureInfoPresenceTracking,
    PresenceTrackingOptions,
)
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions

_LOGGER = logging.getLogger(__name__)


class AreaStateTrackerEntity(BinaryMagicEntity):
    """Tracks an area's state by tracking the configured entities."""

    ignore_non_state_change: bool = True

    def __init__(self, area: MagicArea) -> None:
        """Initialize the area tracker."""

        BinaryMagicEntity.__init__(self, area, domain=BINARY_SENSOR_DOMAIN)

        self.area: MagicArea | MagicMetaArea = area

        self._state: bool = False

        self._last_off_time: datetime = datetime.now(UTC) - timedelta(days=2)
        self._clear_timeout_callback: Callable[[], None] | None = None

        self._sensors: list[str] = []
        self._active_sensors: list[str] = []
        self._last_active_sensors: list[str] = []

        self._load_presence_sensors()

        _LOGGER.debug("%s: presence tracker initialized", self.area.name)

    def _setup_tracking_listeners(self) -> None:
        # Track presence sensor
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._sensors, self._sensor_state_change
            )
        )

        # Track light sensor for dark state (if resolved on area)
        if self.area.area_light_sensor:
            _LOGGER.debug(
                "%s: Tracking light sensor for dark state: %s",
                self.area.name,
                self.area.area_light_sensor,
            )
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self.area.area_light_sensor],
                    self._secondary_state_change,
                )
            )

        # Track ALL secondary states (sleep + user-defined) from single source
        secondary_state_entities_dict = self.area.secondary_state_entities

        if secondary_state_entities_dict:
            secondary_state_entity_list = list(secondary_state_entities_dict.values())
            _LOGGER.debug(
                "%s: Secondary state tracking: %s",
                self.area.name,
                str(secondary_state_entity_list),
            )
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    secondary_state_entity_list,
                    self._secondary_state_change,
                )
            )

        # Timed self update
        delta = timedelta(seconds=UPDATE_INTERVAL)
        self.async_on_remove(
            async_track_time_interval(self.hass, self._update_state, delta)
        )

        self.async_on_remove(self._cleanup_timers)

    @callback
    def _cleanup_timers(self) -> None:
        """Remove pending timers."""
        self._remove_clear_timeout()

    # Public methods

    def get_sensors(self) -> list[str]:
        """Return sensors used for tracking."""
        return self._sensors

    def get_metadata(self) -> dict:
        """Return metadata information about the area's occupancy."""
        return {
            AreaAttributes.PRESENCE_SENSORS.value: self._sensors,
            CommonAttributes.ACTIVE_SENSORS.value: self._active_sensors,
            AreaAttributes.LAST_ACTIVE_SENSORS.value: self._last_active_sensors,
            CommonAttributes.STATES.value: self.area.states,
            AreaAttributes.CLEAR_TIMEOUT.value: self._get_clear_timeout() / ONE_MINUTE,
        }

    # Helpers

    def _valid_on_states(self, additional_states: list[str] | None = None) -> list[str]:
        """Return valid ON states for entities."""

        valid_states = PRESENCE_SENSOR_VALID_ON_STATES.copy()

        if additional_states:
            valid_states.extend(additional_states)

        return [STATE_ON] if self.area.is_meta() else valid_states

    # Entity loading

    def _load_presence_sensors(self) -> None:
        """Load sensors that are relevant for presence sensing."""

        self._sensors = self.area.get_presence_sensors()

    # Entity state tracking & reporting
    def _secondary_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Handle area secondary state change event."""
        if event.data["new_state"] is None:
            return

        to_state = event.data["new_state"].state
        entity_id = event.data["entity_id"]

        _LOGGER.debug(
            "%s: Secondary state change: entity '%s' changed to %s",
            self.area.name,
            entity_id,
            to_state,
        )

        if to_state in INVALID_STATES:
            _LOGGER.debug(
                "%s: sensor '%s' has invalid state %s",
                self.area.name,
                entity_id,
                to_state,
            )
            return None

        self.hass.loop.call_soon_threadsafe(self._update_state, datetime.now(UTC))

    def _sensor_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Actions when the sensor state has changed."""
        if event.data["new_state"] is None:
            return

        # Ignore state reports taht aren't really a state change
        if (
            self.ignore_non_state_change
            and event.data["old_state"]
            and event.data["new_state"].state == event.data["old_state"].state
        ):
            return

        to_state = event.data["new_state"].state
        entity_id = event.data["entity_id"]

        _LOGGER.debug(
            "%s: sensor '%s' changed to {%s}",
            self.area.name,
            entity_id,
            to_state,
        )

        if to_state in INVALID_STATES:
            _LOGGER.debug(
                "%s: sensor '%s' has invalid state %s",
                self.area.name,
                entity_id,
                to_state,
            )
            return

        if to_state and to_state not in self._valid_on_states():
            _LOGGER.debug(
                "Setting last non-normal time %s %s",
                event.data["old_state"],
                event.data["new_state"],
            )
            self._last_off_time = datetime.now(UTC)  # Update last_off_time
            # Clear the timeout
            self._remove_clear_timeout()

        self.hass.loop.call_soon_threadsafe(self._update_state, datetime.now(UTC))

    async def _async_update_state(self, timeout: int) -> None:
        await asyncio.sleep(timeout)
        self._update_state()

    @callback
    def _update_state(self, extra: datetime | None = None) -> None:
        """Update the area's state and report changes."""

        states_tuple = self._update_area_states()
        new_states, lost_states = states_tuple

        state_changed = any(
            state in new_states for state in [AreaStates.OCCUPIED, AreaStates.CLEAR]
        )

        _LOGGER.debug(
            "%s: States updated. New states: %s / Lost states: %s",
            self.area.name,
            str(new_states),
            str(lost_states),
        )

        if state_changed:
            # Consider all secondary states new
            states_tuple = (self.area.states.copy(), [])

        self._report_state_change(states_tuple)

    def _report_state_change(self, states_tuple=([], [])):
        """Fire an event reporting area state change."""
        new_states, lost_states = states_tuple

        if set(new_states) == set(lost_states):
            return

        _LOGGER.debug(
            "%s: Reporting state change (new states: %s/lost states: %s)",
            self.area.name,
            str(new_states),
            str(lost_states),
        )
        dispatcher_send(
            self.hass, MagicAreasEvents.AREA_STATE_CHANGED, self.area.id, states_tuple
        )

    # Area state calculations

    def _update_area_states(self) -> tuple[set[str], set[str]]:
        """Return new and lost states for this area."""

        last_state: set[str] = set(self.area.states.copy())
        current_state: set[str] = set(self._get_area_states())

        if last_state == current_state:
            return (set(), set())

        # Calculate what's new
        new_states: set[str] = current_state - last_state
        lost_states: set[str] = last_state - current_state
        _LOGGER.debug(
            "%s: Current state: %s, last state: %s -> new states %s / lost states %s",
            self.area.name,
            str(current_state),
            str(last_state),
            str(new_states),
            str(lost_states),
        )

        self.area.states = list(current_state)

        return (new_states, lost_states)

    def _get_area_states(self) -> list[str]:
        """Return states for the area."""
        states = []

        # Get Main occupancy state
        current_state = self._get_occupancy_state()
        last_state = self.area.is_occupied()

        states.append(AreaStates.OCCUPIED if current_state else AreaStates.CLEAR)
        if current_state != last_state:
            self.area.last_changed = datetime.now(UTC)
            _LOGGER.debug(
                "%s: State changed to %s at %s",
                self.area.name,
                current_state,
                self.area.last_changed,
            )

        # Extended state
        seconds_since_last_change = (
            datetime.now(UTC) - self.area.last_changed
        ).total_seconds()

        extended_time = self.area.config.get(SecondaryStateOptions.EXTENDED_TIME)

        if (
            AreaStates.OCCUPIED in states
            and (seconds_since_last_change / ONE_MINUTE) >= extended_time
        ):
            states.append(AreaStates.EXTENDED)

        states.extend(self._get_secondary_states())

        return states

    def _get_secondary_states(self) -> list[str]:
        """Return secondary states for an area."""

        states: list[str] = []

        # Check darkness using resolved light sensor on area
        if self.area.is_area_dark():
            states.append(AreaStates.DARK)

        # Check ALL secondary states (sleep + user-defined) from single source
        for state_name, entity_id in self.area.secondary_state_entities.items():
            entity = self.hass.states.get(entity_id)
            if entity and entity.state.lower() in self._valid_on_states():
                states.append(state_name)

        # Meta-state bright (if not dark)
        if AreaStates.DARK not in states:
            states.append(AreaStates.BRIGHT)

        return states

    def _get_occupancy_state(self) -> bool:
        """Return occupancy state for an area."""

        area_state = self._get_sensors_state()

        if not area_state:
            if not self.area.is_occupied():
                return False

            if self._is_on_clear_timeout():
                _LOGGER.debug("%s: Area is on timeout", self.area.name)
                if self._timeout_exceeded():
                    return False
            else:
                if self.area.is_occupied() and not area_state:
                    _LOGGER.debug(
                        "%s: Area not on timeout, setting call_later", self.area.name
                    )
                    self._set_clear_timeout()
        else:
            self._remove_clear_timeout()

        return True

    def _get_sensors_state(self) -> bool:
        """Fetch state from tracked sensors."""

        valid_states = self._valid_on_states()

        _LOGGER.debug(
            "%s: Updating state. (Valid states: %s)",
            self.area.name,
            ",".join(valid_states),
        )

        active_sensors = []
        available_sensors = self._sensors.copy()

        # Filter out keep-only sensors if the area isn't occupied
        if not self.area.is_occupied():
            keep_only_entities = self.area.config.get(
                PresenceTrackingOptions.KEEP_ONLY_ENTITIES
            )
            available_sensors = [
                sensor for sensor in self._sensors if sensor not in keep_only_entities
            ]

        # Loop over all entities and check their state
        for sensor in available_sensors:
            try:
                entity = self.hass.states.get(sensor)

                if not entity:
                    _LOGGER.debug(
                        "%s: Could not get sensor state: '%s' entity not found, skipping",
                        self.area.name,
                        sensor,
                    )
                    continue

                _LOGGER.debug(
                    "%s: Sensor '%s' state: %s", self.area.name, sensor, entity.state
                )

                # Skip unavailable entities
                if entity.state in INVALID_STATES:
                    _LOGGER.debug(
                        "%s: Sensor '%s' is unavailable, skipping...",
                        self.area.name,
                        sensor,
                    )
                    continue

                if entity.state in valid_states:
                    _LOGGER.debug(
                        "%s: Valid presence sensor found: %s.", self.area.name, sensor
                    )
                    active_sensors.append(sensor)

            # Adding pylint exception because this is a last-resort hail-mary catch-all
            # pylint: disable-next=broad-exception-caught
            except Exception as e:
                _LOGGER.error(
                    "%s: Error getting entity state for '%s': %s",
                    self.area.name,
                    sensor,
                    str(e),
                )

        # Populate metadata
        if self._active_sensors:
            self._last_active_sensors = self._active_sensors

        self._active_sensors = active_sensors

        return len(active_sensors) > 0

    # Clear timeout

    def _set_clear_timeout(self):
        """Set clear timeout."""
        if not self.area.is_occupied():
            return False

        timeout = self._get_clear_timeout()

        _LOGGER.debug("%s: Scheduling clear in %s seconds", self.area.name, timeout)
        self._clear_timeout_callback = async_call_later(
            self.hass, timeout, self._update_state
        )

    def _get_clear_timeout(self) -> int:
        """Return configured clear timeout value."""
        if self.area.has_state(AreaStates.SLEEP):
            return (
                self.area.config.get(SecondaryStateOptions.SLEEP_TIMEOUT) * ONE_MINUTE
            )

        if self.area.has_state(AreaStates.EXTENDED):
            return (
                self.area.config.get(SecondaryStateOptions.EXTENDED_TIMEOUT)
                * ONE_MINUTE
            )

        return self.area.config.get(PresenceTrackingOptions.CLEAR_TIMEOUT) * ONE_MINUTE

    def _remove_clear_timeout(self) -> None:
        if not self._clear_timeout_callback:
            return

        _LOGGER.debug(
            "%s: Clearing timeout",
            self.area.name,
        )

        # pylint: disable-next=not-callable
        self._clear_timeout_callback()
        self._clear_timeout_callback = None

    def _is_on_clear_timeout(self) -> bool:
        return self._clear_timeout_callback is not None

    def _timeout_exceeded(self) -> bool:
        """Check if clear timeout is exceeded."""
        if not self.area.is_occupied():
            return False

        clear_delta = timedelta(seconds=self._get_clear_timeout())

        last_clear = self._last_off_time
        clear_time = last_clear + clear_delta
        time_now = datetime.now(UTC)

        if time_now >= clear_time:
            _LOGGER.debug("%s: Clear Timeout exceeded.", self.area.name)
            self._remove_clear_timeout()
            return True

        return False


class AreaStateBinarySensor(AreaStateTrackerEntity, BinarySensorEntity):
    """Create an area presence sensor entity that tracks the current occupied state."""

    feature_info: MagicAreasFeatureInfo = MagicAreasFeatureInfoPresenceTracking()

    # Init & Teardown

    def __init__(self, area: MagicArea) -> None:
        """Initialize the area presence binary sensor."""

        AreaStateTrackerEntity.__init__(self, area)
        BinarySensorEntity.__init__(self)

        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY
        self._attr_extra_state_attributes = {}
        self._attr_is_on: bool = False

        self._attr_icon: str = self.area.icon or self.feature_info.icons.get(
            BINARY_SENSOR_DOMAIN, EMPTY_STRING
        )

    async def async_added_to_hass(self) -> None:
        """Call to add the system to hass."""
        await super().async_added_to_hass()
        await self.restore_state()
        await self._load_attributes()

        # Setup the listeners
        await self._setup_listeners()

        self.hass.loop.call_soon_threadsafe(self._update_state, datetime.now(UTC))

        _LOGGER.debug("%s: area presence binary sensor initialized", self.area.name)

    async def _setup_listeners(self) -> None:
        # Setup state change listener
        async_dispatcher_connect(
            self.hass, MagicAreasEvents.AREA_STATE_CHANGED, self._area_state_changed
        )

        self._setup_tracking_listeners()

    # Helpers

    async def _load_attributes(self) -> None:
        # Add common attributes
        self._attr_extra_state_attributes.update(
            {
                CommonAttributes.STATES.value: [],
                CommonAttributes.ACTIVE_SENSORS.value: [],
                AreaAttributes.LAST_ACTIVE_SENSORS.value: [],
                AreaAttributes.PRESENCE_SENSORS.value: [],
                AreaAttributes.LIGHT_SENSOR: self.area.area_light_sensor,
                AreaAttributes.TYPE.value: self.area.config.get(AreaConfigOptions.TYPE),
                AreaAttributes.CLEAR_TIMEOUT.value: 0,
            }
        )

    # Area change handlers
    def _area_state_changed(
        self, area_id: str, states_tuple: tuple[list[str], list[str]]
    ) -> None:
        """Handle area state change event."""

        # pylint: disable-next=unused-variable
        new_states, old_states = states_tuple

        if area_id != self.area.id:
            _LOGGER.debug(
                "%s: Area state change event not for us. Skipping. (req: %s}/self: %s)",
                self.area.name,
                area_id,
                self.area.id,
            )
            return

        _LOGGER.debug(
            "%s: Binary presence sensor detected area state change.", self.area.name
        )

        self._attr_is_on = self.area.is_occupied()
        self._attr_extra_state_attributes.update(self.get_metadata())
        self.schedule_update_ha_state()


class MetaAreaStateBinarySensor(AreaStateBinarySensor):
    """Create an area presence sensor entity that tracks the current occupied state (Meta)."""

    area: MagicMetaArea
    ignore_non_state_change: bool = False

    def __init__(self, area: MagicMetaArea) -> None:
        """Initialize the area presence binary sensor."""

        AreaStateBinarySensor.__init__(self, area)

    async def _load_attributes(self) -> None:
        await super()._load_attributes()
        self._attr_extra_state_attributes.update(
            {
                AreaAttributes.AREAS.value: self.area.get_child_areas(),
            }
        )

    def _get_secondary_states(self) -> list[str]:
        """Return secondary states for an area through calculation."""

        states: list[str] = []
        mode: CalculationMode = CalculationMode(
            self.area.config.get(SecondaryStateOptions.CALCULATION_MODE)
        )

        child_areas: list[str] = self.area.get_child_areas()
        states_list: list[str] = []

        # Collect all states from child areas
        for area_slug in child_areas:
            area_entity_id: str = (
                f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{area_slug}_area_state"
            )
            area_state = self.hass.states.get(area_entity_id)

            if not area_state:
                continue
            if CommonAttributes.STATES.value not in area_state.attributes:
                continue

            states_list.extend(area_state.attributes[CommonAttributes.STATES.value])

        state_counter = Counter(states_list)
        child_area_count: int = len(child_areas)

        # Calculate for built-in secondary states (sleep, dark)
        for secondary_state in [AreaStates.SLEEP, AreaStates.DARK]:
            if secondary_state not in state_counter:
                continue

            amt_states = state_counter[secondary_state]

            if mode == CalculationMode.ANY and amt_states > 0:
                states.append(secondary_state)
            elif mode == CalculationMode.ALL and amt_states == child_area_count:
                states.append(secondary_state)
            elif mode == CalculationMode.MAJORITY and amt_states >= (
                child_area_count / 2
            ):
                states.append(secondary_state)

        # Calculate for user-defined states
        # User-defined states are any states not in the built-in list
        builtin_states = {s.value for s in AreaStates}
        for state_name, count in state_counter.items():
            if state_name in builtin_states:
                continue  # Skip built-in states (already handled)

            # Apply calculation mode to user-defined state
            if mode == CalculationMode.ANY and count > 0:
                states.append(state_name)
            elif mode == CalculationMode.ALL and count == child_area_count:
                states.append(state_name)
            elif mode == CalculationMode.MAJORITY and count >= (child_area_count / 2):
                states.append(state_name)

        # Meta-state bright
        if AreaStates.DARK not in states:
            states.append(AreaStates.BRIGHT)

        return states
