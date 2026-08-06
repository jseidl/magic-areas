"""Test for aggregate (group) sensor behavior."""

import asyncio
from collections.abc import AsyncGenerator
import inspect
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
from homeassistant.components.threshold.binary_sensor import ThresholdSensor
from homeassistant.components.threshold.const import ATTR_HYSTERESIS, ATTR_UPPER
from homeassistant.const import LIGHT_LUX, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import (
    CONF_AGGREGATES_ILLUMINANCE_THRESHOLD,
    CONF_AGGREGATES_ILLUMINANCE_THRESHOLD_HYSTERESIS,
    CONF_AGGREGATES_MIN_ENTITIES,
    CONF_ENABLED_FEATURES,
    CONF_FEATURE_AGGREGATION,
    DOMAIN,
)
from custom_components.magic_areas.threshold import THRESHOLD_SENSOR_ACCEPTS_HASS

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


@pytest.fixture(name="threshold_config_entry")
def mock_config_entry_threshold() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        {
            CONF_ENABLED_FEATURES: {
                CONF_FEATURE_AGGREGATION: {
                    CONF_AGGREGATES_MIN_ENTITIES: 1,
                    CONF_AGGREGATES_ILLUMINANCE_THRESHOLD: 600,
                    CONF_AGGREGATES_ILLUMINANCE_THRESHOLD_HYSTERESIS: 10,
                },
            }
        }
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


# Entities


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


# Tests


def test_threshold_sensor_arguments_bind_to_core() -> None:
    """Ensure the arguments we hand ThresholdSensor match the running core.

    Core changes this signature from time to time — 2026.8 (core#177598) dropped
    `hass` — and AreaThresholdSensor's failure is swallowed by a broad except,
    so the only symptom is a missing threshold sensor and areas silently stuck
    in the `bright` state. Bind the call site here so a mismatch fails loudly.
    """

    arguments = {
        "entity_id": "sensor.magic_areas_aggregates_kitchen_aggregate_illuminance",
        "name": "",
        "unique_id": "test",
        "lower": None,
        "upper": 600,
        "hysteresis": 60,
        "device_class": BinarySensorDeviceClass.LIGHT,
    }
    if THRESHOLD_SENSOR_ACCEPTS_HASS:
        arguments["hass"] = None

    # Raises TypeError if the call in AreaThresholdSensor.__init__ is no longer valid.
    inspect.signature(ThresholdSensor.__init__).bind(object(), **arguments)


async def test_threshold_sensor_light(
    hass: HomeAssistant,
    entities_sensor_illuminance_multiple: list[MockBinarySensor],
    _setup_integration_threshold,
) -> None:
    """Test the light from illuminance threshold sensor."""

    threshold_sensor_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_threshold_kitchen_threshold_light"
    )

    aggregate_sensor_id = (
        f"{SENSOR_DOMAIN}.magic_areas_aggregates_kitchen_aggregate_illuminance"
    )

    # Ensure aggregate sensor was created
    aggregate_sensor_state = hass.states.get(aggregate_sensor_id)
    assert aggregate_sensor_state is not None
    assert float(aggregate_sensor_state.state) == 0.0

    # Ensure threhsold sensor was created
    threshold_sensor_state = hass.states.get(threshold_sensor_id)
    assert threshold_sensor_state is not None
    assert threshold_sensor_state.state == STATE_OFF
    assert hasattr(threshold_sensor_state, "attributes")
    assert ATTR_UPPER in threshold_sensor_state.attributes
    assert ATTR_HYSTERESIS in threshold_sensor_state.attributes

    sensor_threhsold_upper = int(threshold_sensor_state.attributes[ATTR_UPPER])
    sensor_hysteresis = int(threshold_sensor_state.attributes[ATTR_HYSTERESIS])

    assert sensor_threhsold_upper == 600
    assert sensor_hysteresis == 600 / 10  # 10%, configured value

    # Set illuminance sensor values to over the threhsold upper value (incl. hysteresis)
    for mock_entity in entities_sensor_illuminance_multiple:
        hass.states.async_set(
            mock_entity.entity_id,
            str(sensor_threhsold_upper + sensor_hysteresis + 1),
            attributes={"unit_of_measurement": LIGHT_LUX},
        )
    await hass.async_block_till_done()

    # Wait a bit for threshold sensor to trigger
    await asyncio.sleep(1)
    await hass.async_block_till_done()

    # Ensure threhsold sensor is triggered
    threshold_sensor_state = hass.states.get(threshold_sensor_id)
    assert_state(threshold_sensor_state, STATE_ON)

    # Reset illuminance sensor values to 0
    for mock_entity in entities_sensor_illuminance_multiple:
        hass.states.async_set(
            mock_entity.entity_id,
            str(0.0),
            attributes={"unit_of_measurement": LIGHT_LUX},
        )
    await hass.async_block_till_done()

    # Wait a bit for threshold sensor to trigger
    await asyncio.sleep(1)
    await hass.async_block_till_done()

    # Ensure threhsold sensor is cleared
    threshold_sensor_state = hass.states.get(threshold_sensor_id)
    assert_state(threshold_sensor_state, STATE_OFF)
