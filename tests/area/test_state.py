"""Test for area changes and how the system handles it."""

from collections.abc import AsyncGenerator
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_PLAYING, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, StateMachine

from custom_components.magic_areas.binary_sensor.presence import AreaStateTrackerEntity
from custom_components.magic_areas.const import (
    DOMAIN,
    UPDATE_INTERVAL,
    AreaAttributes,
    AreaStates,
    CommonAttributes,
    PresenceTrackingOptions,
)
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_in_attribute,
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    safe_set_state,
    setup_mock_entities,
    shutdown_integration,
    trigger_occupancy,
    trigger_secondary_state,
)
from tests.mocks import MockBinarySensor, MockMediaPlayer

_LOGGER = logging.getLogger(__name__)


# Fixtures


@pytest.fixture(name="secondary_states_config_entry")
def mock_config_entry_secondary_states() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        SecondaryStateOptions.to_config(
            {
                SecondaryStateOptions.SLEEP_ENTITY.key: "binary_sensor.sleep_sensor",
            }
        ),
    )
    merge_feature_config(
        data,
        AggregateOptions.to_config(
            {
                AggregateOptions.MIN_ENTITIES.key: 1,
                AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key: [
                    BinarySensorDeviceClass.MOTION.value,
                    BinarySensorDeviceClass.LIGHT.value,
                ],
            }
        ),
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="keep_only_sensor_config_entry")
def mock_config_entry_keep_only_sensor() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    # Merge keep_only_entities into existing presence_tracking config
    if "presence_tracking" not in data:
        data["presence_tracking"] = {}
    data["presence_tracking"][PresenceTrackingOptions.KEEP_ONLY_ENTITIES.key] = [
        "binary_sensor.motion_sensor_1"
    ]
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_secondary_states")
async def setup_integration_secondary_states(
    hass: HomeAssistant,
    secondary_states_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with secondary states config."""

    await init_integration(hass, [secondary_states_config_entry])
    yield
    await shutdown_integration(hass, [secondary_states_config_entry])


@pytest.fixture(name="_setup_integration_keep_only_sensor")
async def setup_integration_keep_only_sensor(
    hass: HomeAssistant,
    keep_only_sensor_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with secondary states config."""

    await init_integration(hass, [keep_only_sensor_config_entry])
    yield
    await shutdown_integration(hass, [keep_only_sensor_config_entry])


# Entities


@pytest.fixture(name="secondary_states_sensors")
async def setup_secondary_state_sensors(hass: HomeAssistant) -> list[MockBinarySensor]:
    """Create binary sensors for the secondary states."""
    mock_binary_sensor_entities = [
        MockBinarySensor(
            name="sleep_sensor",
            unique_id="sleep_sensor",
            device_class=None,
        ),
        MockBinarySensor(
            name="area_light_sensor",
            unique_id="area_light_sensor",
            device_class=BinarySensorDeviceClass.LIGHT,
        ),
    ]
    await setup_mock_entities(
        hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: mock_binary_sensor_entities}
    )
    return mock_binary_sensor_entities


# Tests


async def test_area_primary_state_change(
    hass: HomeAssistant,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_basic,
) -> None:
    """Test primary area state change."""

    motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id
    area_sensor_entity_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_kitchen_area_state"
    )

    # Validate the right enties were created.
    area_binary_sensor = hass.states.get(area_sensor_entity_id)
    assert_state(area_binary_sensor, STATE_OFF)
    assert_in_attribute(
        area_binary_sensor,
        AreaAttributes.PRESENCE_SENSORS.value,
        motion_sensor_entity_id,
    )
    assert_in_attribute(
        area_binary_sensor, CommonAttributes.STATES.value, AreaStates.CLEAR
    )

    # Turn on motion sensor
    await trigger_occupancy(hass, motion_sensor_entity_id, occupied=True)

    # Update states
    area_binary_sensor = hass.states.get(area_sensor_entity_id)
    motion_sensor = hass.states.get(motion_sensor_entity_id)
    assert_state(motion_sensor, STATE_ON)
    assert_state(area_binary_sensor, STATE_ON)
    assert_in_attribute(
        area_binary_sensor, CommonAttributes.STATES.value, AreaStates.OCCUPIED
    )

    # Turn off motion sensor
    await trigger_occupancy(hass, motion_sensor_entity_id, occupied=False)

    # Update states
    area_binary_sensor = hass.states.get(area_sensor_entity_id)
    motion_sensor = hass.states.get(motion_sensor_entity_id)
    assert_state(motion_sensor, STATE_OFF)
    assert_state(area_binary_sensor, STATE_OFF)
    assert_in_attribute(
        area_binary_sensor, CommonAttributes.STATES.value, AreaStates.CLEAR
    )


async def test_area_secondary_state_change(
    hass: HomeAssistant,
    secondary_states_sensors: list[MockBinarySensor],
    _setup_integration_secondary_states,
) -> None:
    """Test secondary area state changes."""

    area_sensor_entity_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_kitchen_area_state"
    )

    secondary_state_map = {
        secondary_states_sensors[0].entity_id: (AreaStates.SLEEP, None),
        secondary_states_sensors[1].entity_id: (AreaStates.BRIGHT, AreaStates.DARK),
    }

    for entity_id, state_tuples in secondary_state_map.items():
        area_binary_sensor = hass.states.get(area_sensor_entity_id)
        entity_state = hass.states.get(entity_id)

        # Ensure off
        assert_state(entity_state, STATE_OFF)
        assert_in_attribute(
            area_binary_sensor,
            CommonAttributes.STATES.value,
            state_tuples[0],
            negate=True,
        )
        if state_tuples[1]:
            assert_in_attribute(
                area_binary_sensor, CommonAttributes.STATES.value, state_tuples[1]
            )

        # Turn entity on
        await trigger_secondary_state(hass, entity_id, active=True)

        # Update states
        area_binary_sensor = hass.states.get(area_sensor_entity_id)
        entity_state = hass.states.get(entity_id)

        # Ensure on
        assert_state(entity_state, STATE_ON)
        assert_in_attribute(
            area_binary_sensor, CommonAttributes.STATES.value, state_tuples[0]
        )
        if state_tuples[1]:
            assert_in_attribute(
                area_binary_sensor,
                CommonAttributes.STATES.value,
                state_tuples[1],
                negate=True,
            )

        # Turn entity off
        await trigger_secondary_state(hass, entity_id, active=False)

        # Update states
        area_binary_sensor = hass.states.get(area_sensor_entity_id)
        entity_state = hass.states.get(entity_id)

        # Ensure off
        assert_state(entity_state, STATE_OFF)
        assert_in_attribute(
            area_binary_sensor,
            CommonAttributes.STATES.value,
            state_tuples[0],
            negate=True,
        )
        if state_tuples[1]:
            assert_in_attribute(
                area_binary_sensor, CommonAttributes.STATES.value, state_tuples[1]
            )


# Test extended state
# @TODO pending figuring out virtualclock


# Test keep-only sensors
async def test_keep_only_sensors(
    hass: HomeAssistant,
    entities_binary_sensor_motion_multiple: list[MockBinarySensor],
    _setup_integration_keep_only_sensor,
) -> None:
    """Test keep-only sensors."""

    motion_sensor_entity_id = entities_binary_sensor_motion_multiple[0].entity_id
    flappy_sensor_entity_id = entities_binary_sensor_motion_multiple[1].entity_id
    area_sensor_entity_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_kitchen_area_state"
    )

    # Validate the right enties were created.
    area_binary_sensor = hass.states.get(area_sensor_entity_id)

    assert_state(area_binary_sensor, STATE_OFF)
    assert_in_attribute(
        area_binary_sensor,
        AreaAttributes.PRESENCE_SENSORS.value,
        motion_sensor_entity_id,
    )
    assert_in_attribute(
        area_binary_sensor,
        AreaAttributes.PRESENCE_SENSORS.value,
        flappy_sensor_entity_id,
    )
    assert_in_attribute(
        area_binary_sensor, CommonAttributes.STATES.value, AreaStates.CLEAR
    )

    # Turn on flappy sensor
    hass.states.async_set(flappy_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Update states, ensure area remains clear
    area_binary_sensor = hass.states.get(area_sensor_entity_id)
    flappy_sensor = hass.states.get(flappy_sensor_entity_id)

    assert_state(flappy_sensor, STATE_ON)
    assert_state(area_binary_sensor, STATE_OFF)
    assert_in_attribute(
        area_binary_sensor, CommonAttributes.STATES.value, AreaStates.CLEAR
    )

    # Turn on motion sensor
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Update states, ensure area is now occupied
    area_binary_sensor = hass.states.get(area_sensor_entity_id)
    motion_sensor = hass.states.get(motion_sensor_entity_id)

    assert_state(motion_sensor, STATE_ON)
    assert_state(area_binary_sensor, STATE_ON)
    assert_in_attribute(
        area_binary_sensor, CommonAttributes.STATES.value, AreaStates.OCCUPIED
    )

    # Turn off motion sensor
    hass.states.async_set(motion_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    # Update states, ensure area remains occupied
    area_binary_sensor = hass.states.get(area_sensor_entity_id)
    motion_sensor = hass.states.get(motion_sensor_entity_id)

    assert_state(motion_sensor, STATE_OFF)
    assert_state(area_binary_sensor, STATE_ON)
    assert_in_attribute(
        area_binary_sensor, CommonAttributes.STATES.value, AreaStates.OCCUPIED
    )

    # Turn off flappy sensor
    await safe_set_state(hass, flappy_sensor_entity_id, active=False)

    # Update states, ensure area clears
    area_binary_sensor = hass.states.get(area_sensor_entity_id)
    flappy_sensor = hass.states.get(flappy_sensor_entity_id)

    assert_state(flappy_sensor, STATE_OFF)
    assert_state(area_binary_sensor, STATE_OFF)
    assert_in_attribute(
        area_binary_sensor, CommonAttributes.STATES.value, AreaStates.CLEAR
    )


# Extended state, timeouts and defensive branches

AREA_SENSOR_ID = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA}_area_state"
EXTENDED_TIME_MINUTES = 2
EXTENDED_TIMEOUT_MINUTES = 3


@pytest.fixture(name="extended_config_entry")
def mock_config_entry_extended() -> MockConfigEntry:
    """Config entry with short extended time and extended timeout."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        SecondaryStateOptions.to_config(
            {
                SecondaryStateOptions.EXTENDED_TIME.key: EXTENDED_TIME_MINUTES,
                SecondaryStateOptions.EXTENDED_TIMEOUT.key: EXTENDED_TIMEOUT_MINUTES,
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Move time forward and run anything that became due."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_area_becomes_extended_after_extended_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    extended_config_entry: MockConfigEntry,
) -> None:
    """Test an area that stays occupied long enough gains the extended state."""
    await init_integration(hass, [extended_config_entry])
    motion_sensor_id = entities_binary_sensor_motion_one[0].entity_id

    hass.states.async_set(motion_sensor_id, STATE_ON)
    await hass.async_block_till_done()
    area_state = hass.states.get(AREA_SENSOR_ID)
    assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.OCCUPIED)
    assert_in_attribute(
        area_state, CommonAttributes.STATES.value, AreaStates.EXTENDED, negate=True
    )

    await _advance(hass, freezer, EXTENDED_TIME_MINUTES * 60 + 1)

    assert_in_attribute(
        hass.states.get(AREA_SENSOR_ID),
        CommonAttributes.STATES.value,
        AreaStates.EXTENDED,
    )

    await shutdown_integration(hass, [extended_config_entry])


async def test_extended_area_clears_after_the_extended_timeout(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    extended_config_entry: MockConfigEntry,
) -> None:
    """Test an extended area waits for the extended timeout, not the clear timeout."""
    await init_integration(hass, [extended_config_entry])
    motion_sensor_id = entities_binary_sensor_motion_one[0].entity_id

    hass.states.async_set(motion_sensor_id, STATE_ON)
    await hass.async_block_till_done()
    await _advance(hass, freezer, EXTENDED_TIME_MINUTES * 60 + 1)

    # The configured clear timeout is 0, so only the extended timeout can keep
    # the area occupied after the motion stops.
    hass.states.async_set(motion_sensor_id, STATE_OFF)
    await hass.async_block_till_done()
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_ON)

    # An update before the timeout elapses leaves the area occupied.
    await _advance(hass, freezer, 61)
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_ON)

    await _advance(hass, freezer, EXTENDED_TIMEOUT_MINUTES * 60)
    area_state = hass.states.get(AREA_SENSOR_ID)
    assert_state(area_state, STATE_OFF)
    assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.CLEAR)

    await shutdown_integration(hass, [extended_config_entry])


async def test_secondary_sensor_removal_is_ignored(
    hass: HomeAssistant,
    secondary_states_sensors: list[MockBinarySensor],
    _setup_integration_secondary_states,
) -> None:
    """Test a secondary state sensor losing its state does not change the area."""
    sleep_sensor = secondary_states_sensors[0]

    hass.states.async_remove(sleep_sensor.entity_id)
    await hass.async_block_till_done()

    area_state = hass.states.get(AREA_SENSOR_ID)
    assert_state(area_state, STATE_OFF)
    assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.CLEAR)


async def test_sensor_read_failure_is_logged(
    hass: HomeAssistant,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_basic,
    caplog,
) -> None:
    """Test a failure reading a presence sensor is logged and does not break the area."""
    motion_sensor_id = entities_binary_sensor_motion_one[0].entity_id
    original_get = StateMachine.get

    def failing_get(self, entity_id):
        if entity_id == motion_sensor_id:
            raise RuntimeError("boom")
        return original_get(self, entity_id)

    with patch.object(StateMachine, "get", failing_get):
        hass.states.async_set(motion_sensor_id, STATE_ON)
        await hass.async_block_till_done()

    assert "Error getting entity state for" in caplog.text
    assert hass.states.get(AREA_SENSOR_ID) is not None


async def test_inconsistent_occupied_state_schedules_a_clear_timeout(
    hass: HomeAssistant,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_basic,
    caplog,
) -> None:
    """Test the safety net warns and reschedules when occupied with nothing pending."""
    motion_sensor_id = entities_binary_sensor_motion_one[0].entity_id
    await trigger_occupancy(hass, motion_sensor_id, occupied=True)
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_ON)

    # With no clear timeout ever scheduled, the area is occupied with no active
    # sensors and nothing pending: the state the safety net exists for.
    with patch.object(AreaStateTrackerEntity, "_set_clear_timeout") as set_timeout:
        hass.states.async_set(motion_sensor_id, STATE_OFF)
        await hass.async_block_till_done()

    assert "State inconsistency detected" in caplog.text
    assert set_timeout.called


# Guards that keep the tracker safe regardless of its caller
# pylint: disable=protected-access


def _tracker(hass: HomeAssistant) -> AreaStateTrackerEntity:
    """Return the presence tracker entity of the default area."""
    return hass.data[BINARY_SENSOR_DOMAIN].get_entity(AREA_SENSOR_ID)


async def test_valid_on_states_accepts_additional_states(
    hass: HomeAssistant,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_basic,
) -> None:
    """Test extra states can be added to the states that count as active."""
    tracker = _tracker(hass)

    default_states = tracker._valid_on_states()
    extended_states = tracker._valid_on_states(["custom_on"])

    assert STATE_ON in default_states
    assert "custom_on" not in default_states
    assert "custom_on" in extended_states
    assert set(default_states) <= set(extended_states)
    # The caller's list is never modified.
    assert tracker._valid_on_states() == default_states


async def test_clear_timeout_is_not_scheduled_for_a_clear_area(
    hass: HomeAssistant,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_basic,
) -> None:
    """Test a clear timeout is only ever scheduled for an occupied area."""
    tracker = _tracker(hass)
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_OFF)

    assert tracker._set_clear_timeout() is False
    assert tracker._is_on_clear_timeout() is False


async def test_clear_timeout_cannot_be_exceeded_for_a_clear_area(
    hass: HomeAssistant,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_basic,
) -> None:
    """Test a clear area never reports an exceeded clear timeout."""
    tracker = _tracker(hass)
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_OFF)

    assert tracker._timeout_exceeded() is False


async def test_unavailable_secondary_sensor_is_ignored(
    hass: HomeAssistant,
    secondary_states_sensors: list[MockBinarySensor],
    _setup_integration_secondary_states,
) -> None:
    """Test a secondary state sensor going unavailable does not change the area."""
    sleep_sensor = secondary_states_sensors[0]
    await trigger_secondary_state(hass, sleep_sensor, active=True)
    assert_in_attribute(
        hass.states.get(AREA_SENSOR_ID), CommonAttributes.STATES.value, AreaStates.SLEEP
    )

    hass.states.async_set(sleep_sensor.entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    # The unavailable report is ignored, so the area keeps its last sleep state.
    assert_in_attribute(
        hass.states.get(AREA_SENSOR_ID), CommonAttributes.STATES.value, AreaStates.SLEEP
    )


# Regression tests for areas getting stuck occupied

CLEAR_TIMEOUT_MINUTES = 1
CLEAR_TIMEOUT_SECONDS = CLEAR_TIMEOUT_MINUTES * 60
UPDATE_INTERVAL_SECONDS = UPDATE_INTERVAL + 1
STATE_IDLE = "idle"
STATE_STANDBY = "standby"


@pytest.fixture(name="clear_timeout_config_entry")
def mock_config_entry_clear_timeout() -> MockConfigEntry:
    """Config entry with a real (non-zero) clear timeout."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        PresenceTrackingOptions.to_config(
            {
                PresenceTrackingOptions.CLEAR_TIMEOUT.key: CLEAR_TIMEOUT_MINUTES,
                PresenceTrackingOptions.SENSOR_DEVICE_CLASS.key: (
                    PresenceTrackingOptions.SENSOR_DEVICE_CLASS.default
                ),
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="clear_timeout_area")
async def setup_clear_timeout_area(
    hass: HomeAssistant,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    clear_timeout_config_entry: MockConfigEntry,
) -> AsyncGenerator[dict[str, str]]:
    """Area with a motion sensor and a media player, 1 minute clear timeout."""
    media_player = MockMediaPlayer(name="tv", unique_id="tv")
    await setup_mock_entities(
        hass, MEDIA_PLAYER_DOMAIN, {DEFAULT_MOCK_AREA: [media_player]}
    )
    await init_integration(hass, [clear_timeout_config_entry])

    yield {
        "motion_id": entities_binary_sensor_motion_one[0].entity_id,
        "media_player_id": media_player.entity_id,
    }

    await shutdown_integration(hass, [clear_timeout_config_entry])


async def test_inactive_to_inactive_changes_do_not_postpone_clearing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clear_timeout_area: dict[str, str],
) -> None:
    """Test a chatty inactive entity cannot keep an area occupied forever."""
    motion_id = clear_timeout_area["motion_id"]
    media_player_id = clear_timeout_area["media_player_id"]

    hass.states.async_set(motion_id, STATE_ON)
    await hass.async_block_till_done()
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_ON)

    hass.states.async_set(motion_id, STATE_OFF)
    await hass.async_block_till_done()
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_ON)

    # The media player flaps between inactive states more often than the timeout
    # would elapse. This must not restart the countdown.
    for index in range(4):
        await _advance(hass, freezer, CLEAR_TIMEOUT_SECONDS / 3)
        hass.states.async_set(
            media_player_id, STATE_STANDBY if index % 2 == 0 else STATE_IDLE
        )
        await hass.async_block_till_done()

    await _advance(hass, freezer, UPDATE_INTERVAL_SECONDS)

    area_state = hass.states.get(AREA_SENSOR_ID)
    assert_state(area_state, STATE_OFF)
    assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.CLEAR)


async def test_active_sensor_going_inactive_restarts_the_clear_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clear_timeout_area: dict[str, str],
) -> None:
    """Test an entity leaving the active state still restarts the countdown."""
    motion_id = clear_timeout_area["motion_id"]
    media_player_id = clear_timeout_area["media_player_id"]

    hass.states.async_set(motion_id, STATE_ON)
    await hass.async_block_till_done()
    hass.states.async_set(media_player_id, STATE_PLAYING)
    await hass.async_block_till_done()
    hass.states.async_set(motion_id, STATE_OFF)
    await hass.async_block_till_done()

    # Playing media keeps the area occupied well past the clear timeout
    await _advance(hass, freezer, CLEAR_TIMEOUT_SECONDS * 3)
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_ON)

    # Media stopping is a real active -> inactive change: countdown restarts
    hass.states.async_set(media_player_id, STATE_IDLE)
    await hass.async_block_till_done()
    await _advance(hass, freezer, CLEAR_TIMEOUT_SECONDS / 2)
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_ON)

    await _advance(hass, freezer, CLEAR_TIMEOUT_SECONDS)
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_OFF)


async def test_fired_clear_timer_is_no_longer_pending(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clear_timeout_area: dict[str, str],
) -> None:
    """Test the timer handle is released when the clear timer fires."""
    motion_id = clear_timeout_area["motion_id"]
    tracker = _tracker(hass)

    hass.states.async_set(motion_id, STATE_ON)
    await hass.async_block_till_done()
    hass.states.async_set(motion_id, STATE_OFF)
    await hass.async_block_till_done()
    assert tracker._is_on_clear_timeout() is True  # pylint: disable=protected-access

    await _advance(hass, freezer, CLEAR_TIMEOUT_SECONDS + 1)

    assert tracker._is_on_clear_timeout() is False  # pylint: disable=protected-access
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_OFF)


async def test_watchdog_clears_an_area_when_the_clear_timer_is_lost(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clear_timeout_area: dict[str, str],
) -> None:
    """Test the periodic update still clears an area whose timer went missing."""
    motion_id = clear_timeout_area["motion_id"]
    tracker = _tracker(hass)

    hass.states.async_set(motion_id, STATE_ON)
    await hass.async_block_till_done()
    hass.states.async_set(motion_id, STATE_OFF)
    await hass.async_block_till_done()

    # Simulate a lost timer
    tracker._remove_clear_timeout()  # pylint: disable=protected-access
    assert tracker._is_on_clear_timeout() is False  # pylint: disable=protected-access

    # The next periodic update notices nothing is pending and reschedules the
    # clear timer, so the area is not stuck.
    await _advance(hass, freezer, UPDATE_INTERVAL_SECONDS)
    assert tracker._is_on_clear_timeout() is True  # pylint: disable=protected-access

    await _advance(hass, freezer, CLEAR_TIMEOUT_SECONDS + 1)
    assert_state(hass.states.get(AREA_SENSOR_ID), STATE_OFF)
