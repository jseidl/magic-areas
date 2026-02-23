"""Test for area changes and how the system handles it."""

from collections.abc import AsyncGenerator
import logging
from typing import Any

from custom_components.magic_areas.const.aggregates import AggregateOptions
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import (
    DOMAIN,
    AreaAttributes,
    AreaStates,
    CommonAttributes,
    PresenceTrackingOptions,
)
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
