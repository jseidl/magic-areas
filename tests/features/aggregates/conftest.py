"""Fixtures for the aggregates and threshold feature tests."""

from collections.abc import AsyncGenerator
from random import randint
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
    LIGHT_LUX,
    UnitOfElectricCurrent,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN
from custom_components.magic_areas.const.aggregates import AggregateOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor, MockSensor


@pytest.fixture(name="aggregates_config_entry")
def mock_config_entry_aggregates() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        AggregateOptions.to_config(
            {
                AggregateOptions.MIN_ENTITIES.key: 1,
                AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key: [
                    cls.value for cls in BinarySensorDeviceClass
                ],
                AggregateOptions.SENSOR_DEVICE_CLASSES.key: [
                    cls.value for cls in SensorDeviceClass
                ],
            }
        )
    )
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


@pytest.fixture(name="entities_sensor_aqi_multiple")
async def setup_entities_sensor_aqi_multiple(
    hass: HomeAssistant,
) -> list[MockSensor]:
    """Create multiple mock AQI sensors and setup the system with it.

    Home Assistant AQI sensors are intentionally unitless (device_class=aqi,
    state_class=measurement, no unit_of_measurement) -- deliberately not
    setting native_unit_of_measurement/unit_of_measurement here, unlike the
    other fixtures above, to reproduce that.
    """
    nr_entities = 3
    mock_sensor_entities = []
    for i in range(nr_entities):
        random_value = randint(0, 500)
        mock_sensor_entities.append(
            MockSensor(
                name=f"aqi_sensor_{i}",
                unique_id=f"aqi_sensor_{i}",
                native_value=random_value,
                device_class=SensorDeviceClass.AQI,
            )
        )
    await setup_mock_entities(
        hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: mock_sensor_entities}
    )
    return mock_sensor_entities


@pytest.fixture(name="threshold_config_entry")
def mock_config_entry_threshold() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        AggregateOptions.to_config(
            {
                AggregateOptions.MIN_ENTITIES.key: 1,
                AggregateOptions.ILLUMINANCE_THRESHOLD.key: 600,
                AggregateOptions.ILLUMINANCE_THRESHOLD_HYSTERESIS.key: 10,
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_threshold")
async def setup_integration_threshold(
    hass: HomeAssistant,
    threshold_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with secondary states config."""

    await init_integration(hass, [threshold_config_entry])
    yield
    await shutdown_integration(hass, [threshold_config_entry])


@pytest.fixture(name="entities_sensor_illuminance_multiple")
async def setup_entities_sensor_illuminance_multiple(
    hass: HomeAssistant,
) -> list[MockSensor]:
    """Create multiple mock sensor and setup the system with it."""
    nr_entities = 3
    mock_sensor_entities = []
    for i in range(nr_entities):
        mock_sensor_entities.append(
            MockSensor(
                name=f"illuminance_sensor_{i}",
                unique_id=f"illuminance_sensor_{i}",
                native_value=0.0,
                device_class=SensorDeviceClass.ILLUMINANCE,
                native_unit_of_measurement=LIGHT_LUX,
                unit_of_measurement=LIGHT_LUX,
                extra_state_attributes={
                    "unit_of_measurement": LIGHT_LUX,
                },
            )
        )
    await setup_mock_entities(
        hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: mock_sensor_entities}
    )
    return mock_sensor_entities
