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
from homeassistant.components.sun.const import STATE_ABOVE_HORIZON
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
    ATTR_ACTIVE_SENSORS,
    ATTR_AREAS,
    ATTR_CLEAR_TIMEOUT,
    ATTR_LAST_ACTIVE_SENSORS,
    ATTR_PRESENCE_SENSORS,
    ATTR_STATES,
    ATTR_TYPE,
    CONF_CLEAR_TIMEOUT,
    CONF_EXTENDED_TIME,
    CONF_EXTENDED_TIMEOUT,
    CONF_KEEP_ONLY_ENTITIES,
    CONF_SECONDARY_STATES,
    CONF_SECONDARY_STATES_CALCULATION_MODE,
    CONF_SLEEP_TIMEOUT,
    CONF_TYPE,
    CONFIGURABLE_AREA_STATE_MAP,
    DEFAULT_CLEAR_TIMEOUT,
    DEFAULT_EXTENDED_TIME,
    DEFAULT_EXTENDED_TIMEOUT,
    DEFAULT_SECONDARY_STATES_CALCULATION_MODE,
    DEFAULT_SLEEP_TIMEOUT,
    EMPTY_STRING,
    INVALID_STATES,
    ONE_MINUTE,
    PRESENCE_SENSOR_VALID_ON_STATES,
    UPDATE_INTERVAL,
    AreaStates,
    CalculationMode,
    MagicAreasEvents,
    MagicAreasFeatureInfo,
    MagicAreasFeatureInfoPresenceTracking,
)

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

        # Track secondary states
        secondary_state_entities: list[str] = []
        configurable_states = self._get_configured_secondary_states()

        for configurable_state in configurable_states:
            configurable_state_entity = CONFIGURABLE_AREA_STATE_MAP[configurable_state]
            tracked_entity = self.area.config.get(CONF_SECONDARY_STATES, {}).get(
                configurable_state_entity, None
            )
            if not tracked_entity:
                continue

            secondary_state_entities.append(tracked_entity)

        if secondary_state_entities:
            _LOGGER.debug(
                "%s: Secondary state tracking: %s",
                self.area.name,
                str(secondary_state_entities),
            )
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, secondary_state_entities, self._secondary_state_change
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

    @callback
    def _validate_state_consistency(self, now: datetime | None = None) -> None:
        """Validate area state consistency and schedule clear timeout if needed.

        Catches edge cases where:
        1. Area is stuck occupied due to a race condition or bug
        2. Sensors became unavailable during startup
        3. Any other scenario where occupied state has no timeout scheduled
        """
        if not self.area.is_occupied():
            return

        has_active_sensors = self._get_sensors_state()
        has_timeout_pending = self._is_on_clear_timeout()

        if not has_active_sensors and not has_timeout_pending:
            _LOGGER.warning(
                "%s: State inconsistency detected - occupied with no active sensors "
                "and no timeout scheduled. Scheduling clear timeout.",
                self.area.name,
            )
            self._set_clear_timeout()

    # Public methods

    def get_sensors(self) -> list[str]:
        """Return sensors used for tracking."""
        return self._sensors

    def get_metadata(self) -> dict:
        """Return metadata information about the area's occupancy."""
        return {
            ATTR_PRESENCE_SENSORS: self._sensors,
            ATTR_ACTIVE_SENSORS: self._active_sensors,
            ATTR_LAST_ACTIVE_SENSORS: self._last_active_sensors,
            ATTR_STATES: self.area.states,
            ATTR_CLEAR_TIMEOUT: self._get_clear_timeout() / ONE_MINUTE,
        }

    # Helpers

    def _valid_on_states(self, additional_states: list[str] | None = None) -> list[str]:
        """Return valid ON states for entities."""

        valid_states = PRESENCE_SENSOR_VALID_ON_STATES.copy()

        if additional_states:
            valid_states.extend(additional_states)

        return [STATE_ON] if self.area.is_meta() else valid_states

    def _get_configured_secondary_states(self) -> list[str]:
        """Return configured secondary states."""
        secondary_states = []

        for (
            configurable_state,
            configurable_state_entity,
        ) in CONFIGURABLE_AREA_STATE_MAP.items():
            secondary_state_entity = self.area.config.get(
                CONF_SECONDARY_STATES, {}
            ).get(configurable_state_entity, None)

            if not secondary_state_entity:
                continue

            secondary_states.append(configurable_state)

        return secondary_states

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

        # Safety check: ensure stuck states get cleared
        self._validate_state_consistency()

    def _report_state_change(self, states_tuple=([], [])):
        """Fire an event reporting area state change."""
        new_states, lost_states = states_tuple
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

        extended_time = self.area.config.get(CONF_SECONDARY_STATES, {}).get(
            CONF_EXTENDED_TIME, DEFAULT_EXTENDED_TIME
        )

        if (
            AreaStates.OCCUPIED in states
            and (seconds_since_last_change / ONE_MINUTE) >= extended_time
        ):
            states.append(AreaStates.EXTENDED)

        states.extend(self._get_secondary_states())

        return states

    def _get_secondary_states(self) -> list[AreaStates]:
        """Return secondary states for an area."""

        states: list[AreaStates] = []

        configurable_states = self._get_configured_secondary_states()

        # Assume AreaStates.DARK if not configured
        if AreaStates.DARK not in configurable_states:
            states.append(AreaStates.DARK)

        for configurable_state in configurable_states:
            configurable_state_entity = CONFIGURABLE_AREA_STATE_MAP[configurable_state]

            secondary_state_entity = self.area.config.get(
                CONF_SECONDARY_STATES, {}
            ).get(configurable_state_entity, None)

            if not secondary_state_entity:
                continue

            entity = self.hass.states.get(secondary_state_entity)
            if not entity:
                continue

            has_valid_state = entity.state.lower() in self._valid_on_states(
                [STATE_ABOVE_HORIZON]
            )
            state_to_add = None

            # Handle dark state from light sensor as an inverted configurable state
            inverted_states = [AreaStates.DARK]

            # Handle both forward and inverted configurable state
            if configurable_state in inverted_states:
                if not has_valid_state:
                    state_to_add = configurable_state
            else:
                if has_valid_state:
                    state_to_add = configurable_state

            if state_to_add:
                _LOGGER.debug(
                    "%s: Secondary state: %s is at %s, adding %s",
                    self.area.name,
                    secondary_state_entity,
                    entity.state.lower(),
                    configurable_state,
                )
                states.append(AreaStates(configurable_state))

        # Meta-state bright
        if AreaStates.DARK in configurable_states and AreaStates.DARK not in states:
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
            keep_only_entities = self.area.config.get(CONF_KEEP_ONLY_ENTITIES, [])
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
                self.area.config.get(CONF_SECONDARY_STATES, {}).get(
                    CONF_SLEEP_TIMEOUT, DEFAULT_SLEEP_TIMEOUT
                )
                * ONE_MINUTE
            )

        if self.area.has_state(AreaStates.EXTENDED):
            return (
                self.area.config.get(CONF_SECONDARY_STATES, {}).get(
                    CONF_EXTENDED_TIMEOUT, DEFAULT_EXTENDED_TIMEOUT
                )
                * ONE_MINUTE
            )

        return (
            self.area.config.get(CONF_CLEAR_TIMEOUT, DEFAULT_CLEAR_TIMEOUT) * ONE_MINUTE
        )

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

        # Ensure clear timeout is scheduled if needed after startup
        # This catches the case where area was occupied before restart but timer was lost
        self.hass.loop.call_soon_threadsafe(self._ensure_clear_timeout_on_startup)

        _LOGGER.debug("%s: area presence binary sensor initialized", self.area.name)

    async def restore_state(self) -> None:
        """Restore the state of the entity and area.states list.

        Extends parent to also restore area.states from saved attributes,
        fixing the bug where timers don't fire after HA restart because
        area.is_occupied() returns False when area.states is empty.
        """
        await super().restore_state()

        # Restore area.states from saved attributes
        last_state = await self.async_get_last_state()
        if last_state is not None and ATTR_STATES in last_state.attributes:
            restored_states = last_state.attributes[ATTR_STATES]
            if isinstance(restored_states, list):
                self.area.states = list(restored_states)
                _LOGGER.info(
                    "%s: Restored area.states from attributes: %s",
                    self.area.name,
                    restored_states,
                )

    @callback
    def _ensure_clear_timeout_on_startup(self) -> None:
        """Ensure clear timeout is scheduled if area is occupied with no active sensors.

        This handles the case where:
        1. Area was occupied before HA restart
        2. Timer was scheduled but lost when HA stopped
        3. After restart, area.states is restored but no sensors are active
        4. Without this, area would stay occupied forever
        """
        if not self.area.is_occupied():
            return

        has_active_sensors = self._get_sensors_state()
        has_timeout_pending = self._is_on_clear_timeout()

        _LOGGER.debug(
            "%s: Startup validation - occupied=%s, active_sensors=%s, timeout_pending=%s",
            self.area.name,
            self.area.is_occupied(),
            has_active_sensors,
            has_timeout_pending,
        )

        if not has_active_sensors and not has_timeout_pending:
            _LOGGER.info(
                "%s: Occupied with no active sensors after startup, scheduling clear timeout",
                self.area.name,
            )
            self._set_clear_timeout()

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
                ATTR_STATES: [],
                ATTR_ACTIVE_SENSORS: [],
                ATTR_LAST_ACTIVE_SENSORS: [],
                ATTR_PRESENCE_SENSORS: [],
                ATTR_TYPE: self.area.config.get(CONF_TYPE),
                ATTR_CLEAR_TIMEOUT: 0,
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
                ATTR_AREAS: self.area.get_child_areas(),
            }
        )

    def _get_secondary_states(self) -> list[AreaStates]:
        """Return secondary states for an area through calculation."""

        states: list[AreaStates] = []
        mode: CalculationMode = CalculationMode(
            self.area.config.get(CONF_SECONDARY_STATES, {}).get(
                CONF_SECONDARY_STATES_CALCULATION_MODE,
                DEFAULT_SECONDARY_STATES_CALCULATION_MODE,
            )
        )

        child_areas: list[str] = self.area.get_child_areas()
        states_list: list[AreaStates] = []

        for area_slug in child_areas:
            area_entity_id: str = (
                f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{area_slug}_area_state"
            )
            area_state = self.hass.states.get(area_entity_id)

            if not area_state:
                continue
            if ATTR_STATES not in area_state.attributes:
                continue

            states_list.extend(area_state.attributes[ATTR_STATES])

        state_counter = Counter(states_list)
        child_area_count: int = len(child_areas)

        for secondary_state in CONFIGURABLE_AREA_STATE_MAP:
            if secondary_state not in state_counter:
                continue

            amt_states = state_counter[AreaStates(secondary_state)]

            if mode == CalculationMode.ANY and amt_states > 0:
                states.append(AreaStates(secondary_state))
                continue

            if mode == CalculationMode.ALL and amt_states == child_area_count:
                states.append(AreaStates(secondary_state))
                continue

            if mode == CalculationMode.MAJORITY and amt_states >= (
                child_area_count / 2
            ):
                states.append(AreaStates(secondary_state))
                continue

        # Meta-state bright
        if AreaStates.DARK not in states:
            states.append(AreaStates.BRIGHT)

        return states
