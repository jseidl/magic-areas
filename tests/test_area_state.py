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
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, StateMachine

from custom_components.magic_areas.binary_sensor.presence import AreaStateTrackerEntity
from custom_components.magic_areas.const import (
    DOMAIN,
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
from tests.mocks import MockBinarySensor

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
