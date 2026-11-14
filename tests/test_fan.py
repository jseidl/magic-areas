"""Tests for the Fan groups feature."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.sensor.const import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.magic_areas.const import DOMAIN, AreaStates
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.fan_groups import FanGroupOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_in_attribute,
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
    trigger_occupancy,
)
from tests.mocks import MockBinarySensor, MockFan, MockSensor

# Constants

SETPOINT_VALUE = 30.0
SENSOR_INITIAL_VALUE = 25

# Fixtures


@pytest.fixture(name="fan_groups_config_entry")
def mock_config_entry_fan_groups() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    merge_feature_config(
        data,
        AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
        FanGroupOptions.to_config(
            {
                FanGroupOptions.REQUIRED_STATE.key: AreaStates.OCCUPIED,
                FanGroupOptions.SETPOINT.key: SETPOINT_VALUE,
            }
        ),
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_fan_groups")
async def setup_integration_fan_groups(
    hass: HomeAssistant,
    fan_groups_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with Fan groups config."""

    await init_integration(hass, [fan_groups_config_entry])
    yield
    await shutdown_integration(hass, [fan_groups_config_entry])


# Entities


@pytest.fixture(name="entities_fan_multiple")
async def setup_entities_fan_multiple(
    hass: HomeAssistant,
) -> list[MockFan]:
    """Create multiple mock fans setup the system with it."""
    mock_fan_entities: list[MockFan] = []
    nr_fans: int = 3
    for i in range(nr_fans):
        mock_fan_entities.append(
            MockFan(name=f"mock_fan_{i}", unique_id=f"unique_fan_{i}")
        )
    await setup_mock_entities(hass, FAN_DOMAIN, {DEFAULT_MOCK_AREA: mock_fan_entities})
    return mock_fan_entities


@pytest.fixture(name="entities_sensor_temperature_one")
async def setup_entities_sensor_temperature_one(
    hass: HomeAssistant,
) -> MockSensor:
    """Create one mock temperature sensor and setup the system with it."""

    mock_temperature_sensor = MockSensor(
        name="mock_temperature_sensor",
        unique_id="unique_temperature_sensor",
        native_value=int(SENSOR_INITIAL_VALUE),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        extra_state_attributes={
            "unit_of_measurement": UnitOfTemperature.CELSIUS,
        },
    )

    await setup_mock_entities(
        hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [mock_temperature_sensor]}
    )
    return mock_temperature_sensor


# Tests


async def test_fan_group_basic(
    hass: HomeAssistant,
    entities_fan_multiple: list[MockFan],
    _setup_integration_fan_groups,
) -> None:
    """Test Fan groups basic functionality."""

    fan_group_entity_id = (
        f"{FAN_DOMAIN}.magic_areas_fan_groups_{DEFAULT_MOCK_AREA}_fan_group"
    )

    # Initialization test
    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_OFF)
    for fan_entity in entities_fan_multiple:
        assert_in_attribute(fan_group_state, ATTR_ENTITY_ID, fan_entity.entity_id)

    # Basic group test
    # Flip group on, check members
    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: fan_group_entity_id}
    )
    await hass.async_block_till_done()

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_ON)

    for fan_entity in entities_fan_multiple:
        fan_entity_state = hass.states.get(fan_entity.entity_id)
        assert_state(fan_entity_state, STATE_ON)

    # Flip group off, check members
    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: fan_group_entity_id}
    )
    await hass.async_block_till_done()

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_OFF)

    for fan_entity in entities_fan_multiple:
        fan_entity_state = hass.states.get(fan_entity.entity_id)
        assert_state(fan_entity_state, STATE_OFF)

    # Flip member on, check group
    first_fan_entity_id = entities_fan_multiple[0].entity_id
    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: first_fan_entity_id}
    )
    await hass.async_block_till_done()

    first_fan_state = hass.states.get(first_fan_entity_id)
    assert_state(first_fan_state, STATE_ON)

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_ON)


async def test_fan_group_logic(
    hass: HomeAssistant,
    entities_fan_multiple: list[MockFan],
    entities_sensor_temperature_one: MockSensor,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_fan_groups,
) -> None:
    """Test Fan groups logic."""

    fan_group_entity_id = (
        f"{FAN_DOMAIN}.magic_areas_fan_groups_{DEFAULT_MOCK_AREA}_fan_group"
    )
    fan_control_entity_id = (
        f"{SWITCH_DOMAIN}.magic_areas_fan_groups_{DEFAULT_MOCK_AREA}_fan_control"
    )
    tracked_entity_id = f"{SENSOR_DOMAIN}.magic_areas_aggregates_{DEFAULT_MOCK_AREA}_aggregate_temperature"
    motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id
    area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA}_area_state"
    temperature_sensor_entity_id = entities_sensor_temperature_one.entity_id

    # Initialization checks
    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_OFF)

    fan_control_state = hass.states.get(fan_control_entity_id)
    assert_state(fan_control_state, STATE_OFF)

    temperature_sensor_state = hass.states.get(temperature_sensor_entity_id)
    assert_state(temperature_sensor_state, str(int(SENSOR_INITIAL_VALUE)))

    tracked_sensor_state = hass.states.get(tracked_entity_id)
    assert_state(tracked_sensor_state, str(float(SENSOR_INITIAL_VALUE)))

    motion_sensor_state = hass.states.get(motion_sensor_entity_id)
    assert_state(motion_sensor_state, STATE_OFF)

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_OFF)

    # Fan control off, under setpoint
    await trigger_occupancy(hass, entities_binary_sensor_motion_one[0], occupied=True)

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_ON)

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_OFF)

    # > Reset
    await trigger_occupancy(hass, entities_binary_sensor_motion_one[0], occupied=False)

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_OFF)

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_OFF)

    # Set tracked sensor over setpoint
    hass.states.async_set(
        temperature_sensor_entity_id,
        str(int(SETPOINT_VALUE * 2)),
        attributes={"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()

    temperature_sensor_state = hass.states.get(temperature_sensor_entity_id)
    assert_state(temperature_sensor_state, str(int(SETPOINT_VALUE * 2)))

    tracked_sensor_state = hass.states.get(tracked_entity_id)
    assert_state(tracked_sensor_state, str(SETPOINT_VALUE * 2))

    # Fan control off, over setpoint
    await trigger_occupancy(hass, entities_binary_sensor_motion_one[0], occupied=True)

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_ON)

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_OFF)

    # > Reset
    await trigger_occupancy(hass, entities_binary_sensor_motion_one[0], occupied=False)

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_OFF)

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_OFF)

    # Turn on fan control
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: fan_control_entity_id}
    )
    await hass.async_block_till_done()

    fan_control_state = hass.states.get(fan_control_entity_id)
    assert_state(fan_control_state, STATE_ON)

    # Fan control on, over setpoint
    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_OFF)

    await trigger_occupancy(hass, entities_binary_sensor_motion_one[0], occupied=True)

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_ON)

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_ON)

    # > Reset
    await trigger_occupancy(hass, entities_binary_sensor_motion_one[0], occupied=False)

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_OFF)

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_OFF)

    # Fan control on, initially under setpoint but then over
    # > Set temperature back to initial value
    hass.states.async_set(
        temperature_sensor_entity_id,
        str(SENSOR_INITIAL_VALUE),
        attributes={"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()
    temperature_sensor_state = hass.states.get(temperature_sensor_entity_id)
    assert_state(temperature_sensor_state, str(SENSOR_INITIAL_VALUE))

    tracked_sensor_state = hass.states.get(tracked_entity_id)
    assert_state(tracked_sensor_state, str(float(SENSOR_INITIAL_VALUE)))

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_OFF)

    await trigger_occupancy(hass, entities_binary_sensor_motion_one[0], occupied=True)

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_ON)

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_OFF)

    # > Set temperature back up
    hass.states.async_set(
        temperature_sensor_entity_id,
        str(int(SETPOINT_VALUE * 2)),
        attributes={"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()

    temperature_sensor_state = hass.states.get(temperature_sensor_entity_id)
    assert_state(temperature_sensor_state, str(int(SETPOINT_VALUE * 2)))

    tracked_sensor_state = hass.states.get(tracked_entity_id)
    assert_state(tracked_sensor_state, str(SETPOINT_VALUE * 2))

    await asyncio.sleep(1)

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_ON)

    # > Set temperature back down
    hass.states.async_set(
        temperature_sensor_entity_id,
        str(SENSOR_INITIAL_VALUE),
        attributes={"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()
    temperature_sensor_state = hass.states.get(temperature_sensor_entity_id)
    assert_state(temperature_sensor_state, str(SENSOR_INITIAL_VALUE))

    tracked_sensor_state = hass.states.get(tracked_entity_id)
    assert_state(tracked_sensor_state, str(float(SENSOR_INITIAL_VALUE)))

    await asyncio.sleep(1)

    fan_group_state = hass.states.get(fan_group_entity_id)
    assert_state(fan_group_state, STATE_OFF)


async def test_fan_group_not_created_without_fans(
    hass: HomeAssistant,
    fan_groups_config_entry: MockConfigEntry,
) -> None:
    """Test an area with no fans gets no fan group."""
    await init_integration(hass, [fan_groups_config_entry])

    fan_group_entity_id = (
        f"{FAN_DOMAIN}.magic_areas_fan_groups_{DEFAULT_MOCK_AREA}_fan_group"
    )
    assert hass.states.get(fan_group_entity_id) is None

    await shutdown_integration(hass, [fan_groups_config_entry])


async def test_fan_group_creation_error_is_contained(
    hass: HomeAssistant,
    entities_fan_multiple: list[MockFan],
    fan_groups_config_entry: MockConfigEntry,
    caplog,
) -> None:
    """Test a failing fan group is logged and does not stop the area from loading."""
    with patch(
        "custom_components.magic_areas.fan.AreaFanGroup",
        side_effect=RuntimeError("boom"),
    ):
        await init_integration(hass, [fan_groups_config_entry])

    fan_group_entity_id = (
        f"{FAN_DOMAIN}.magic_areas_fan_groups_{DEFAULT_MOCK_AREA}_fan_group"
    )
    area_sensor_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA}_area_state"
    assert hass.states.get(fan_group_entity_id) is None
    assert hass.states.get(area_sensor_id) is not None
    assert "Error creating fan group: boom" in caplog.text

    await shutdown_integration(hass, [fan_groups_config_entry])


async def test_stale_fan_entities_are_cleaned_up_on_reload(
    hass: HomeAssistant,
    entities_fan_multiple: list[MockFan],
    fan_groups_config_entry: MockConfigEntry,
) -> None:
    """Test a leftover Magic Areas fan entity is removed when the entry reloads."""
    await init_integration(hass, [fan_groups_config_entry])
    registry = er.async_get(hass)
    stale = registry.async_get_or_create(
        FAN_DOMAIN,
        DOMAIN,
        "stale_fan_group",
        config_entry=fan_groups_config_entry,
    )
    fan_group_entity_id = (
        f"{FAN_DOMAIN}.magic_areas_fan_groups_{DEFAULT_MOCK_AREA}_fan_group"
    )
    assert registry.async_get(stale.entity_id) is not None

    await hass.config_entries.async_reload(fan_groups_config_entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(stale.entity_id) is None
    assert registry.async_get(fan_group_entity_id) is not None

    await shutdown_integration(hass, [fan_groups_config_entry])


FAN_GROUP_ID = f"{FAN_DOMAIN}.magic_areas_fan_groups_{DEFAULT_MOCK_AREA}_fan_group"
FAN_CONTROL_ID = (
    f"{SWITCH_DOMAIN}.magic_areas_fan_groups_{DEFAULT_MOCK_AREA}_fan_control"
)
TEMPERATURE_AGGREGATE_ID = (
    f"{SENSOR_DOMAIN}.magic_areas_aggregates_{DEFAULT_MOCK_AREA}_aggregate_temperature"
)


async def _enable_fan_control(hass: HomeAssistant) -> None:
    """Turn the fan control switch on."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: FAN_CONTROL_ID},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_fan_control_ignores_states_other_than_the_required_one(
    hass: HomeAssistant,
    entities_fan_multiple: list[MockFan],
    entities_sensor_temperature_one: MockSensor,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
) -> None:
    """Test the fans stay off while the area is occupied but not in the required state."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    merge_feature_config(
        data,
        AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
        FanGroupOptions.to_config(
            {
                FanGroupOptions.REQUIRED_STATE.key: AreaStates.EXTENDED,
                FanGroupOptions.SETPOINT.key: SETPOINT_VALUE,
            }
        ),
    )
    config_entry = MockConfigEntry(domain=DOMAIN, data=data)
    await init_integration(hass, [config_entry])
    await _enable_fan_control(hass)

    # Occupied, but not yet "extended", so the fans must not start even though
    # the tracked temperature is over the setpoint.
    await trigger_occupancy(hass, entities_binary_sensor_motion_one[0], occupied=True)
    hass.states.async_set(
        TEMPERATURE_AGGREGATE_ID,
        str(int(SETPOINT_VALUE * 2)),
        attributes={"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()

    assert_state(hass.states.get(FAN_GROUP_ID), STATE_OFF)

    await shutdown_integration(hass, [config_entry])


async def test_fan_control_turns_fans_off_when_setpoint_is_no_longer_reached(
    hass: HomeAssistant,
    entities_fan_multiple: list[MockFan],
    entities_sensor_temperature_one: MockSensor,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_fan_groups,
) -> None:
    """Test running fans stop once the tracked value falls below the setpoint."""
    await _enable_fan_control(hass)
    await trigger_occupancy(hass, entities_binary_sensor_motion_one[0], occupied=True)

    hass.states.async_set(
        TEMPERATURE_AGGREGATE_ID,
        str(int(SETPOINT_VALUE * 2)),
        attributes={"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()
    assert_state(hass.states.get(FAN_GROUP_ID), STATE_ON)

    hass.states.async_set(
        TEMPERATURE_AGGREGATE_ID,
        str(int(SETPOINT_VALUE / 2)),
        attributes={"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()

    assert_state(hass.states.get(FAN_GROUP_ID), STATE_OFF)


async def test_fan_control_warns_when_tracked_sensor_is_missing(
    hass: HomeAssistant,
    entities_fan_multiple: list[MockFan],
    entities_sensor_temperature_one: MockSensor,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_fan_groups,
    caplog,
) -> None:
    """Test a missing tracked aggregate is reported and the fans are left alone."""
    await _enable_fan_control(hass)
    hass.states.async_remove(TEMPERATURE_AGGREGATE_ID)
    await hass.async_block_till_done()

    await trigger_occupancy(hass, entities_binary_sensor_motion_one[0], occupied=True)

    assert "is not found" in caplog.text
    assert_state(hass.states.get(FAN_GROUP_ID), STATE_OFF)
