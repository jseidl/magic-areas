"""Tests for the aggregate conditions that decide the area's light source.

Each scenario fails one condition of the light aggregate or illuminance threshold
sensor, so the area must ignore the (bright) readings below and fall back to
sun.sun, which is below the horizon.
"""

import asyncio
from collections.abc import AsyncGenerator
import logging
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
from homeassistant.components.sun.const import STATE_BELOW_HORIZON
from homeassistant.const import LIGHT_LUX
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN, AreaStates, CommonAttributes
from custom_components.magic_areas.const.aggregates import AggregateOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_in_attribute,
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor, MockSensor

_LOGGER = logging.getLogger(__name__)

AREA_STATE_ID = (
    f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_"
    f"{DEFAULT_MOCK_AREA.value}_area_state"
)


def _light_binary_sensor() -> MockBinarySensor:
    """Create a light binary sensor."""
    return MockBinarySensor(
        name="daylight",
        unique_id="daylight",
        device_class=BinarySensorDeviceClass.LIGHT,
    )


def _illuminance_sensor() -> MockSensor:
    """Create an illuminance sensor."""
    return MockSensor(
        name="lux",
        unique_id="lux",
        native_value=500,
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        unit_of_measurement=LIGHT_LUX,
        extra_state_attributes={"unit_of_measurement": LIGHT_LUX},
    )


@pytest.fixture(name="entries")
async def fixture_entries(hass: HomeAssistant) -> AsyncGenerator[list[MockConfigEntry]]:
    """Unload every entry registered by a test once it is done."""
    registered: list[MockConfigEntry] = []
    yield registered
    await shutdown_integration(hass, registered)


@pytest.mark.parametrize(
    ("binary_sensors", "sensors", "aggregate_options"),
    [
        pytest.param(
            [_light_binary_sensor],
            [],
            {AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key: ["motion"]},
            id="light-class-not-aggregated",
        ),
        pytest.param(
            [_light_binary_sensor],
            [],
            {AggregateOptions.MIN_ENTITIES.key: 2},
            id="too-few-light-sensors",
        ),
        pytest.param(
            [],
            [_illuminance_sensor],
            {
                AggregateOptions.ILLUMINANCE_THRESHOLD.key: 10,
                AggregateOptions.SENSOR_DEVICE_CLASSES.key: ["temperature"],
            },
            id="illuminance-class-not-aggregated",
        ),
        pytest.param(
            [],
            [],
            {
                AggregateOptions.ILLUMINANCE_THRESHOLD.key: 10,
                AggregateOptions.SENSOR_DEVICE_CLASSES.key: ["illuminance"],
            },
            id="threshold-without-any-sensor",
        ),
    ],
)
async def test_unmet_conditions_fall_back_to_the_sun(
    hass: HomeAssistant,
    entries,
    binary_sensors: list[Any],
    sensors: list[Any],
    aggregate_options: dict[str, Any],
) -> None:
    """Test the area ignores an aggregate whose conditions are not met."""
    created_binary = [factory() for factory in binary_sensors]
    created_sensors = [factory() for factory in sensors]
    if created_binary:
        await setup_mock_entities(
            hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: created_binary}
        )
    if created_sensors:
        await setup_mock_entities(
            hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: created_sensors}
        )
    hass.states.async_set("sun.sun", STATE_BELOW_HORIZON)

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
    await asyncio.sleep(0.5)

    assert_in_attribute(
        hass.states.get(AREA_STATE_ID), CommonAttributes.STATES.value, AreaStates.DARK
    )
