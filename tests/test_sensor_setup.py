"""Tests for the sensor platform setup (aggregate sensors)."""

from collections.abc import AsyncGenerator
import logging
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.sensor.const import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.magic_areas.const import DOMAIN
from custom_components.magic_areas.const.aggregates import AggregateOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockSensor

_LOGGER = logging.getLogger(__name__)

SLUG = DEFAULT_MOCK_AREA.value
MODULE = "custom_components.magic_areas.sensor"


def _aggregate_id(device_class: str) -> str:
    """Return the entity id of a sensor aggregate."""
    return f"{SENSOR_DOMAIN}.magic_areas_aggregates_{SLUG}_aggregate_{device_class}"


def _sensor(
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


@pytest.fixture(name="entries")
async def fixture_entries(hass: HomeAssistant) -> AsyncGenerator[list[MockConfigEntry]]:
    """Unload every entry registered by a test once it is done."""
    registered: list[MockConfigEntry] = []
    yield registered
    await shutdown_integration(hass, registered)


async def _setup(
    hass: HomeAssistant,
    entries: list[MockConfigEntry],
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
    entries.append(entry)
    await init_integration(hass, [entry])


class TestSensorAggregateSetup:
    """Test the sensor aggregate creation rules."""

    async def test_aggregate_created_for_configured_class(
        self, hass: HomeAssistant, entries
    ):
        """Test an aggregate exists for a configured device class."""
        await _setup(
            hass,
            entries,
            [_sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)],
        )

        assert hass.states.get(_aggregate_id("temperature")) is not None

    async def test_no_aggregates_without_sensors(self, hass: HomeAssistant, entries):
        """Test an area without sensors gets no sensor aggregates."""
        await _setup(hass, entries, [])

        assert hass.states.get(_aggregate_id("temperature")) is None

    async def test_sensors_without_state_are_skipped(
        self, hass: HomeAssistant, entries
    ):
        """Test a registered sensor that has no state yet is not aggregated."""
        sensor = _sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)
        await setup_mock_entities(hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [sensor]})
        hass.states.async_remove(sensor.entity_id)
        await hass.async_block_till_done()

        await _setup(hass, entries, [])

        assert hass.states.get(_aggregate_id("temperature")) is None

    async def test_sensors_without_device_class_are_skipped(
        self, hass: HomeAssistant, entries
    ):
        """Test sensors with no device class are never aggregated."""
        await _setup(hass, entries, [_sensor(None, None)])

        assert hass.states.get(_aggregate_id("temperature")) is None
        assert not [
            entity_id
            for entity_id in hass.states.async_entity_ids(SENSOR_DOMAIN)
            if "aggregate" in entity_id
        ]

    async def test_aggregate_skipped_below_minimum_entities(
        self, hass: HomeAssistant, entries
    ):
        """Test a device class with too few sensors gets no aggregate."""
        await _setup(
            hass,
            entries,
            [_sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)],
            **{AggregateOptions.MIN_ENTITIES.key: 2},
        )

        assert hass.states.get(_aggregate_id("temperature")) is None

    async def test_aggregate_skipped_for_unconfigured_class(
        self, hass: HomeAssistant, entries
    ):
        """Test a device class that is not configured gets no aggregate."""
        await _setup(
            hass,
            entries,
            [_sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)],
            **{AggregateOptions.SENSOR_DEVICE_CLASSES.key: ["humidity"]},
        )

        assert hass.states.get(_aggregate_id("temperature")) is None

    async def test_disabling_aggregates_removes_the_sensor(
        self, hass: HomeAssistant, entries
    ):
        """Test an aggregate is removed from the registry once Aggregates is disabled."""
        await _setup(
            hass,
            entries,
            [_sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)],
        )
        registry = er.async_get(hass)
        aggregate_id = _aggregate_id("temperature")
        assert registry.async_get(aggregate_id) is not None

        data = dict(entries[0].data)
        data["features"] = {}
        hass.config_entries.async_update_entry(entries[0], data=data)
        await hass.async_block_till_done()

        assert registry.async_get(aggregate_id) is None

    async def test_aggregate_creation_error_is_contained(
        self, hass: HomeAssistant, entries, caplog
    ):
        """Test a failing aggregate does not break the platform."""
        with patch(f"{MODULE}.AreaAggregateSensor", side_effect=RuntimeError("boom")):
            await _setup(
                hass,
                entries,
                [_sensor(SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS)],
            )

        assert hass.states.get(_aggregate_id("temperature")) is None
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
        entries,
        device_class: SensorDeviceClass,
        unit: str,
        expected: str,
    ):
        """Test the aggregate uses the state class that fits its device class."""
        await _setup(
            hass,
            entries,
            [_sensor(device_class, unit)],
            **{AggregateOptions.SENSOR_DEVICE_CLASSES.key: [device_class.value]},
        )

        state = hass.states.get(_aggregate_id(device_class.value))
        assert state is not None
        assert state.attributes["state_class"] == expected
