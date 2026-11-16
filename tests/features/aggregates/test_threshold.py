"""Tests for the threshold sensors built on aggregates."""

import logging
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.threshold.const import ATTR_HYSTERESIS, ATTR_UPPER
from homeassistant.const import LIGHT_LUX, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.helpers import assert_state, init_integration, shutdown_integration
from tests.mocks import MockBinarySensor, MockSensor

_LOGGER = logging.getLogger(__name__)


# Tests


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
    await hass.async_block_till_done()

    # Ensure threhsold sensor is cleared
    threshold_sensor_state = hass.states.get(threshold_sensor_id)
    assert_state(threshold_sensor_state, STATE_OFF)


async def test_threshold_sensor_creation_error_is_contained(
    hass: HomeAssistant,
    entities_sensor_illuminance_multiple: list[MockSensor],
    threshold_config_entry: MockConfigEntry,
    caplog,
) -> None:
    """Test a failing threshold sensor does not stop the area from loading."""

    with patch(
        "custom_components.magic_areas.threshold.AreaThresholdSensor",
        side_effect=RuntimeError("boom"),
    ):
        await init_integration(hass, [threshold_config_entry])

    threshold_sensor_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_threshold_kitchen_threshold_light"
    )
    area_sensor_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_kitchen_area_state"
    )

    assert hass.states.get(threshold_sensor_id) is None
    assert hass.states.get(area_sensor_id) is not None
    assert "Error creating calculated light sensor: boom" in caplog.text

    await shutdown_integration(hass, [threshold_config_entry])
