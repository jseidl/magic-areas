"""Test for aggregate (group) sensor behavior."""

from collections.abc import AsyncGenerator
import logging
from random import randint
from statistics import mean
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor.const import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    UnitOfElectricCurrent,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN
from custom_components.magic_areas.const.aggregates import AggregateOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor, MockSensor

_LOGGER = logging.getLogger(__name__)


# Fixtures


@pytest.fixture(name="aggregates_config_entry")
def mock_config_entry_aggregates() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}))
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_aggregates")
async def setup_integration_aggregates(
    hass: HomeAssistant,
    aggregates_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with secondary states config."""

    await init_integration(hass, [aggregates_config_entry])
    yield
    await shutdown_integration(hass, [aggregates_config_entry])


# Entities


@pytest.fixture(name="entities_binary_sensor_connectivity_multiple")
async def setup_entities_binary_sensor_connectivity_multiple(
    hass: HomeAssistant,
) -> list[MockBinarySensor]:
    """Create multiple mock sensor and setup the system with it."""
    nr_entities = 3
    mock_binary_sensor_entities = []
    for i in range(nr_entities):
        mock_binary_sensor_entities.append(
            MockBinarySensor(
                name=f"connectivity_sensor_{i}",
                unique_id=f"connectivity_sensor_{i}",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
            )
        )
    await setup_mock_entities(
        hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: mock_binary_sensor_entities}
    )
    return mock_binary_sensor_entities


@pytest.fixture(name="entities_sensor_temperature_multiple")
async def setup_entities_sensor_temperature_multiple(
    hass: HomeAssistant,
) -> list[MockSensor]:
    """Create multiple mock sensor and setup the system with it."""
    nr_entities = 3
    mock_sensor_entities = []
    for i in range(nr_entities):
        random_value = randint(0, 100)
        mock_sensor_entities.append(
            MockSensor(
                name=f"temperature_sensor_{i}",
                unique_id=f"temperature_sensor_{i}",
                native_value=random_value,
                device_class=SensorDeviceClass.TEMPERATURE,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                unit_of_measurement=UnitOfTemperature.CELSIUS,
                extra_state_attributes={
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                },
            )
        )
    await setup_mock_entities(
        hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: mock_sensor_entities}
    )
    return mock_sensor_entities


@pytest.fixture(name="entities_sensor_current_multiple")
async def setup_entities_sensor_current_multiple(
    hass: HomeAssistant,
) -> list[MockSensor]:
    """Create multiple mock sensor and setup the system with it."""
    nr_entities = 3
    mock_sensor_entities = []
    for i in range(nr_entities):
        random_value = randint(0, 100)
        mock_sensor_entities.append(
            MockSensor(
                name=f"current_sensor_{i}",
                unique_id=f"current_sensor_{i}",
                native_value=random_value,
                device_class=SensorDeviceClass.CURRENT,
                native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                extra_state_attributes={
                    "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                },
            )
        )
    await setup_mock_entities(
        hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: mock_sensor_entities}
    )
    return mock_sensor_entities


# Tests


async def test_aggregates_binary_sensor_regular(
    hass: HomeAssistant,
    entities_binary_sensor_motion_multiple: list[MockBinarySensor],
    _setup_integration_aggregates,
) -> None:
    """Test binary sensor aggregates with all=False."""

    aggregate_sensor_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_kitchen_aggregate_motion"
    )

    # Init test & individual ON/OFF flip
    aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
    assert aggregate_sensor_state is not None
    assert aggregate_sensor_state.state == STATE_OFF
    assert hasattr(aggregate_sensor_state, "attributes")
    assert ATTR_ENTITY_ID in aggregate_sensor_state.attributes

    group_members: list[str] = aggregate_sensor_state.attributes[ATTR_ENTITY_ID]

    for mock_entity in entities_binary_sensor_motion_multiple:
        assert mock_entity.entity_id in group_members

        mock_state = hass.states.get(mock_entity.entity_id)
        assert_state(mock_state, STATE_OFF)

        # Test state flip ON
        hass.states.async_set(mock_entity.entity_id, STATE_ON)
        await hass.async_block_till_done()

        mock_state = hass.states.get(mock_entity.entity_id)
        assert_state(mock_state, STATE_ON)
        aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
        assert_state(aggregate_sensor_state, STATE_ON)

        # Test state flip OFF
        hass.states.async_set(mock_entity.entity_id, STATE_OFF)
        await hass.async_block_till_done()
        mock_state = hass.states.get(mock_entity.entity_id)
        assert_state(mock_state, STATE_OFF)
        aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
        assert_state(aggregate_sensor_state, STATE_OFF)

    # Turn all ON
    for mock_entity in entities_binary_sensor_motion_multiple:
        hass.states.async_set(mock_entity.entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Turn all off and ensure only off when last off
    for entity_index, mock_entity in enumerate(entities_binary_sensor_motion_multiple):
        last_sensor = entity_index == (len(entities_binary_sensor_motion_multiple) - 1)
        hass.states.async_set(mock_entity.entity_id, STATE_OFF)
        await hass.async_block_till_done()
        aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
        assert_state(aggregate_sensor_state, STATE_OFF if last_sensor else STATE_ON)


async def test_aggregates_binary_sensor_all(
    hass: HomeAssistant,
    entities_binary_sensor_connectivity_multiple: list[MockBinarySensor],
    _setup_integration_aggregates,
) -> None:
    """Test binary sensor aggregates with all=True."""

    aggregate_sensor_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_kitchen_aggregate_connectivity"
    )

    # Init test
    aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
    assert aggregate_sensor_state is not None
    assert aggregate_sensor_state.state == STATE_OFF
    assert hasattr(aggregate_sensor_state, "attributes")
    assert ATTR_ENTITY_ID in aggregate_sensor_state.attributes

    group_members: list[str] = aggregate_sensor_state.attributes[ATTR_ENTITY_ID]

    # ON test
    for entity_index, mock_entity in enumerate(
        entities_binary_sensor_connectivity_multiple
    ):
        last_sensor = entity_index == (
            len(entities_binary_sensor_connectivity_multiple) - 1
        )

        assert mock_entity.entity_id in group_members

        mock_state = hass.states.get(mock_entity.entity_id)
        assert_state(mock_state, STATE_OFF)

        # Test state flip ON
        hass.states.async_set(mock_entity.entity_id, STATE_ON)
        await hass.async_block_till_done()
        mock_state = hass.states.get(mock_entity.entity_id)
        assert_state(mock_state, STATE_ON)
        aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
        assert_state(aggregate_sensor_state, STATE_ON if last_sensor else STATE_OFF)

    # OFF test
    for entity_index, mock_entity in enumerate(
        entities_binary_sensor_connectivity_multiple
    ):
        last_sensor = entity_index == (
            len(entities_binary_sensor_connectivity_multiple) - 1
        )

        # Test state flip OFF
        hass.states.async_set(mock_entity.entity_id, STATE_OFF)
        await hass.async_block_till_done()
        mock_state = hass.states.get(mock_entity.entity_id)
        assert_state(mock_state, STATE_OFF)
        aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
        assert_state(aggregate_sensor_state, STATE_OFF)


async def test_aggregates_sensor_avg(
    hass: HomeAssistant,
    entities_sensor_temperature_multiple: list[MockSensor],
    _setup_integration_aggregates,
) -> None:
    """Test sensor aggregates with average mode."""

    aggregate_sensor_id = (
        f"{SENSOR_DOMAIN}.magic_areas_aggregates_kitchen_aggregate_temperature"
    )

    _LOGGER.warning(entities_sensor_temperature_multiple)

    entity_values = []

    # Read initial values
    for mock_entity in entities_sensor_temperature_multiple:
        mock_state = hass.states.get(mock_entity.entity_id)
        assert mock_state is not None
        entity_values.append(int(mock_state.state))

    # Init test
    aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
    assert aggregate_sensor_state is not None
    assert round(float(aggregate_sensor_state.state), 2) == round(
        mean(entity_values), 2
    )

    # Change all the values
    changed_values = []
    for mock_entity in entities_sensor_temperature_multiple:
        random_value = randint(0, 100)
        changed_values.append(random_value)
        hass.states.async_set(
            mock_entity.entity_id,
            str(random_value),
            attributes={"unit_of_measurement": UnitOfTemperature.CELSIUS},
        )
        await hass.async_block_till_done()
        changed_state = hass.states.get(mock_entity.entity_id)
        assert changed_state is not None
        assert int(changed_state.state) == random_value

    # Check changed values
    aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
    assert aggregate_sensor_state is not None
    assert round(float(aggregate_sensor_state.state), 2) == round(
        mean(changed_values), 2
    )


async def test_aggregates_sensor_sum(
    hass: HomeAssistant,
    entities_sensor_current_multiple: list[MockSensor],
    _setup_integration_aggregates,
) -> None:
    """Test sensor aggregates with sum mode."""

    aggregate_sensor_id = (
        f"{SENSOR_DOMAIN}.magic_areas_aggregates_kitchen_aggregate_current"
    )

    _LOGGER.warning(entities_sensor_current_multiple)

    entity_values = []

    # Read initial values
    for mock_entity in entities_sensor_current_multiple:
        mock_state = hass.states.get(mock_entity.entity_id)
        assert mock_state is not None
        entity_values.append(int(mock_state.state))

    # Init test
    aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
    assert aggregate_sensor_state is not None
    assert round(float(aggregate_sensor_state.state), 2) == round(sum(entity_values), 2)

    # Change all the values
    changed_values = []
    for mock_entity in entities_sensor_current_multiple:
        random_value = randint(0, 100)
        changed_values.append(random_value)
        hass.states.async_set(
            mock_entity.entity_id,
            str(random_value),
            attributes={"unit_of_measurement": UnitOfElectricCurrent.AMPERE},
        )
        await hass.async_block_till_done()
        changed_state = hass.states.get(mock_entity.entity_id)
        assert changed_state is not None
        assert int(changed_state.state) == random_value

    # Check changed values
    aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
    assert aggregate_sensor_state is not None
    assert round(float(aggregate_sensor_state.state), 2) == round(
        sum(changed_values), 2
    )
