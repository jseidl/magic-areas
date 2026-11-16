"""Test for aggregate (group) sensor behavior."""

import logging
from random import randint
from statistics import mean
from unittest.mock import patch

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
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.magic_areas.const import DOMAIN
from custom_components.magic_areas.const.aggregates import AggregateOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
)
from tests.mocks import MockBinarySensor, MockSensor

_LOGGER = logging.getLogger(__name__)


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


async def test_aggregates_sensor_aqi_unitless(
    hass: HomeAssistant,
    entities_sensor_aqi_multiple: list[MockSensor],
    _setup_integration_aggregates,
) -> None:
    """AQI sensors are unitless in HA and must still be aggregated (#631)."""

    aggregate_sensor_id = (
        f"{SENSOR_DOMAIN}.magic_areas_aggregates_kitchen_aggregate_aqi"
    )

    entity_values = []
    for mock_entity in entities_sensor_aqi_multiple:
        mock_state = hass.states.get(mock_entity.entity_id)
        assert mock_state is not None
        assert "unit_of_measurement" not in mock_state.attributes
        entity_values.append(int(mock_state.state))

    aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
    assert aggregate_sensor_state is not None
    assert round(float(aggregate_sensor_state.state), 2) == round(
        mean(entity_values), 2
    )
    assert "unit_of_measurement" not in aggregate_sensor_state.attributes


SLUG = DEFAULT_MOCK_AREA.value


SENSOR_MODULE = "custom_components.magic_areas.sensor"


def _sensor_aggregate_id(device_class: str) -> str:
    """Return the entity id of a sensor aggregate."""
    return f"{SENSOR_DOMAIN}.magic_areas_aggregates_{SLUG}_aggregate_{device_class}"


def _make_sensor(
    device_class: SensorDeviceClass | None, unit: str | None, index: int = 1
) -> MockSensor:
    """Create a mock sensor reporting a value for the given device class."""
    name = f"{device_class.value if device_class else 'plain'}_{index}"
    attributes = {"unit_of_measurement": unit} if unit else {}
    return MockSensor(
        name=name,
        unique_id=name,
        native_value=10,
        device_class=device_class,
        native_unit_of_measurement=unit,
        unit_of_measurement=unit,
        extra_state_attributes=attributes,
    )


async def _setup_sensor_aggregates(
    hass: HomeAssistant,
    config_entries_to_unload: list[MockConfigEntry],
    sensors: list[MockSensor],
    **aggregate_options,
) -> None:
    """Register the sensors, enable Aggregates with the options and load the area."""
    if sensors:
        await setup_mock_entities(hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: sensors})
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    merge_feature_config(
        data,
        AggregateOptions.to_config(
            {AggregateOptions.MIN_ENTITIES.key: 1, **aggregate_options}
        ),
    )
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    config_entries_to_unload.append(entry)
    await init_integration(hass, [entry])


class TestSensorAggregateSetup:
    """Test the sensor aggregate creation rules."""

    async def test_aggregate_created_for_configured_class(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test an aggregate exists for a configured device class."""
        await _setup_sensor_aggregates(
            hass,
            config_entries_to_unload,
            [_make_sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)],
        )

        assert hass.states.get(_sensor_aggregate_id("temperature")) is not None

    async def test_no_aggregates_without_sensors(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test an area without sensors gets no sensor aggregates."""
        await _setup_sensor_aggregates(hass, config_entries_to_unload, [])

        assert hass.states.get(_sensor_aggregate_id("temperature")) is None

    async def test_sensors_without_state_are_skipped(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test a registered sensor that has no state yet is not aggregated."""
        sensor = _make_sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)
        await setup_mock_entities(hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [sensor]})
        hass.states.async_remove(sensor.entity_id)
        await hass.async_block_till_done()

        await _setup_sensor_aggregates(hass, config_entries_to_unload, [])

        assert hass.states.get(_sensor_aggregate_id("temperature")) is None

    async def test_sensors_without_device_class_are_skipped(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test sensors with no device class are never aggregated."""
        await _setup_sensor_aggregates(
            hass, config_entries_to_unload, [_make_sensor(None, None)]
        )

        assert hass.states.get(_sensor_aggregate_id("temperature")) is None
        assert not [
            entity_id
            for entity_id in hass.states.async_entity_ids(SENSOR_DOMAIN)
            if "aggregate" in entity_id
        ]

    async def test_aggregate_skipped_below_minimum_entities(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test a device class with too few sensors gets no aggregate."""
        await _setup_sensor_aggregates(
            hass,
            config_entries_to_unload,
            [_make_sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)],
            **{AggregateOptions.MIN_ENTITIES.key: 2},
        )

        assert hass.states.get(_sensor_aggregate_id("temperature")) is None

    async def test_aggregate_skipped_for_unconfigured_class(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test a device class that is not configured gets no aggregate."""
        await _setup_sensor_aggregates(
            hass,
            config_entries_to_unload,
            [_make_sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)],
            **{AggregateOptions.SENSOR_DEVICE_CLASSES.key: ["humidity"]},
        )

        assert hass.states.get(_sensor_aggregate_id("temperature")) is None

    async def test_disabling_aggregates_removes_the_sensor(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test an aggregate is removed from the registry once Aggregates is disabled."""
        await _setup_sensor_aggregates(
            hass,
            config_entries_to_unload,
            [_make_sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)],
        )
        registry = er.async_get(hass)
        aggregate_id = _sensor_aggregate_id("temperature")
        assert registry.async_get(aggregate_id) is not None

        data = dict(config_entries_to_unload[0].data)
        data["features"] = {}
        hass.config_entries.async_update_entry(config_entries_to_unload[0], data=data)
        await hass.async_block_till_done()

        assert registry.async_get(aggregate_id) is None

    async def test_aggregate_creation_error_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test a failing aggregate does not break the platform."""
        with patch(
            f"{SENSOR_MODULE}.AreaAggregateSensor", side_effect=RuntimeError("boom")
        ):
            await _setup_sensor_aggregates(
                hass,
                config_entries_to_unload,
                [
                    _make_sensor(
                        SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS
                    )
                ],
            )

        assert hass.states.get(_sensor_aggregate_id("temperature")) is None
        assert "Error creating 'temperature' aggregate sensor: boom" in caplog.text


class TestAggregateStateClass:
    """Test the state class given to aggregates of cumulative device classes."""

    @pytest.mark.parametrize(
        ("device_class", "unit", "expected"),
        [
            (SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, "measurement"),
            (SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, "total"),
            (SensorDeviceClass.GAS, UnitOfVolume.CUBIC_METERS, "total_increasing"),
            (SensorDeviceClass.WATER, UnitOfVolume.CUBIC_METERS, "total_increasing"),
        ],
    )
    async def test_aggregate_state_class(
        self,
        hass: HomeAssistant,
        config_entries_to_unload,
        device_class: SensorDeviceClass,
        unit: str,
        expected: str,
    ):
        """Test the aggregate uses the state class that fits its device class."""
        await _setup_sensor_aggregates(
            hass,
            config_entries_to_unload,
            [_make_sensor(device_class, unit)],
            **{AggregateOptions.SENSOR_DEVICE_CLASSES.key: [device_class.value]},
        )

        state = hass.states.get(_sensor_aggregate_id(device_class.value))
        assert state is not None
        assert state.attributes["state_class"] == expected


BINARY_SENSOR_MODULE = "custom_components.magic_areas.binary_sensor"


def _binary_aggregate_id(device_class: str) -> str:
    """Return the entity id of a binary sensor aggregate."""
    return (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{SLUG}_aggregate_{device_class}"
    )


def _make_binary_sensor(
    device_class: BinarySensorDeviceClass, index: int = 1
) -> MockBinarySensor:
    """Create a mock binary sensor of the given device class."""
    return MockBinarySensor(
        name=f"{device_class.value}_{index}",
        unique_id=f"{device_class.value}_{index}",
        device_class=device_class,
    )


async def _setup_binary_aggregates(
    hass: HomeAssistant,
    sensors: list[MockBinarySensor],
    *feature_configs: dict,
) -> MockConfigEntry:
    """Register the sensors, enable the given features and load the integration."""
    if sensors:
        await setup_mock_entities(
            hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: sensors}
        )
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    merge_feature_config(data, *feature_configs)
    config_entry = MockConfigEntry(domain=DOMAIN, data=data)
    await init_integration(hass, [config_entry])
    return config_entry


class TestAggregateSensors:
    """Test the binary sensor aggregate creation rules."""

    async def test_aggregate_created_when_minimum_is_met(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test an aggregate exists for a configured device class."""
        config_entries_to_unload.append(
            await _setup_binary_aggregates(
                hass,
                [
                    _make_binary_sensor(BinarySensorDeviceClass.MOTION, 1),
                    _make_binary_sensor(BinarySensorDeviceClass.MOTION, 2),
                ],
                AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 2}),
            )
        )

        assert hass.states.get(_binary_aggregate_id("motion")) is not None

    async def test_aggregate_skipped_below_minimum_entities(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test a device class with too few sensors gets no aggregate."""
        config_entries_to_unload.append(
            await _setup_binary_aggregates(
                hass,
                [_make_binary_sensor(BinarySensorDeviceClass.MOTION, 1)],
                AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 2}),
            )
        )

        assert hass.states.get(_binary_aggregate_id("motion")) is None

    async def test_aggregate_skipped_for_unconfigured_device_class(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test a device class that is not configured gets no aggregate."""
        config_entries_to_unload.append(
            await _setup_binary_aggregates(
                hass,
                [_make_binary_sensor(BinarySensorDeviceClass.MOTION, 1)],
                AggregateOptions.to_config(
                    {
                        AggregateOptions.MIN_ENTITIES.key: 1,
                        AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key: ["door"],
                    }
                ),
            )
        )

        assert hass.states.get(_binary_aggregate_id("motion")) is None

    async def test_aggregate_ignores_sensors_without_device_class(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test binary sensors with no device class are not aggregated."""
        no_class = MockBinarySensor(
            name="no_class", unique_id="no_class", device_class=None
        )
        config_entries_to_unload.append(
            await _setup_binary_aggregates(
                hass,
                [no_class],
                AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
            )
        )

        assert hass.states.get(no_class.entity_id) is not None
        for aggregate_class in ("motion", "door", "light", "occupancy", "window"):
            assert hass.states.get(_binary_aggregate_id(aggregate_class)) is None

    async def test_aggregate_creation_error_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test a failing aggregate does not break the platform."""
        with patch(
            f"{BINARY_SENSOR_MODULE}.AreaAggregateBinarySensor",
            side_effect=RuntimeError("boom"),
        ):
            config_entries_to_unload.append(
                await _setup_binary_aggregates(
                    hass,
                    [_make_binary_sensor(BinarySensorDeviceClass.MOTION, 1)],
                    AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
                )
            )

        assert hass.states.get(_binary_aggregate_id("motion")) is None
        assert "Error creating 'motion' aggregate sensor: boom" in caplog.text
