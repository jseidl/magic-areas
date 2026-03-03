"""Integration tests for automatic dark state detection.

Tests the resolve_light_entity() cascade and is_area_dark() behavior using
real Home Assistant instances with minimal mocking (following light_groups test pattern).
"""

# pylint: disable=redefined-outer-name`

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.components.sun.const import STATE_ABOVE_HORIZON, STATE_BELOW_HORIZON
from homeassistant.const import (
    LIGHT_LUX,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import (
    DOMAIN,
    AreaConfigOptions,
    AreaStates,
    CommonAttributes,
)
from custom_components.magic_areas.const.aggregates import AggregateOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_in_attribute,
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor, MockSensor

ILLUMINANCE_SENSOR_OFF_VALUE: float = 0.0
ILLUMINANCE_SENSOR_ON_VALUE: float = 100.0

# Helper Functions


async def set_illuminance_sensor_state(
    hass: HomeAssistant,
    sensor: MockSensor,
    number: float = ILLUMINANCE_SENSOR_OFF_VALUE,
) -> None:
    """Set value safely for illuminance sensor."""
    hass.states.async_set(
        sensor.entity_id, str(number), attributes={"unit_of_measurement": LIGHT_LUX}
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)  # Event propagation delay


async def trigger_light_sensor_state(
    hass: HomeAssistant, sensor: MockBinarySensor, bright: bool = True
) -> None:
    """Trigger light sensor state change (ON=bright, OFF=dark for light sensors)."""
    state = STATE_ON if bright else STATE_OFF
    hass.states.async_set(sensor.entity_id, state)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)  # Event propagation delay


async def set_sun_state(hass: HomeAssistant, above_horizon: bool = True) -> None:
    """Set sun.sun state."""
    state = STATE_ABOVE_HORIZON if above_horizon else STATE_BELOW_HORIZON
    hass.states.async_set("sun.sun", state)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)


# Fixtures


@pytest.fixture
async def setup_area_with_threshold(
    hass: HomeAssistant,
) -> AsyncGenerator[dict[str, Any]]:
    """Sets-up area with threshold sensor (aggregates enabled)."""

    # Create threshold binary sensor
    illuminance_sensor = MockSensor(
        name="mock_illuminance_sensor",
        unique_id="mock_illuminance_sensor",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_value=ILLUMINANCE_SENSOR_OFF_VALUE,
        native_unit_of_measurement=LIGHT_LUX,
        unit_of_measurement=LIGHT_LUX,
        extra_state_attributes={
            "unit_of_measurement": LIGHT_LUX,
        },
    )

    # Register sensor
    await setup_mock_entities(
        hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [illuminance_sensor]}
    )

    # Setup config entry with aggregates
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    merge_feature_config(
        data,
        AggregateOptions.to_config(
            {
                AggregateOptions.MIN_ENTITIES.key: 1,
                AggregateOptions.SENSOR_DEVICE_CLASSES.key: [
                    SensorDeviceClass.ILLUMINANCE.value
                ],
                AggregateOptions.ILLUMINANCE_THRESHOLD.key: 10,
            }
        ),
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data
    )
    await init_integration(hass, [config_entry])

    yield {
        "illuminance_sensor": illuminance_sensor,
        "threshold_aggregate_id": f"binary_sensor.magic_areas_threshold_{DEFAULT_MOCK_AREA.value}_threshold_light",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
        "config_entry": config_entry,
        "area_id": DEFAULT_MOCK_AREA.value,
    }

    await shutdown_integration(hass, [config_entry])


@pytest.fixture
async def setup_area_with_light_aggregate(
    hass: HomeAssistant,
) -> AsyncGenerator[dict[str, Any]]:
    """Sets-up area with light aggregate (no threshold)."""

    # Create binary light sensor
    light_sensor = MockBinarySensor(
        name="light_sensor",
        unique_id="light_sensor",
        device_class=BinarySensorDeviceClass.LIGHT,
    )

    await setup_mock_entities(
        hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [light_sensor]}
    )

    # Create the light aggregate entity that Magic Areas would create
    light_aggregate_id = f"binary_sensor.magic_areas_aggregates_{DEFAULT_MOCK_AREA.value}_aggregate_light"
    hass.states.async_set(light_aggregate_id, STATE_OFF)

    # Setup config entry with aggregates (but no threshold)
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        AggregateOptions.to_config(
            {
                AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key: [
                    BinarySensorDeviceClass.LIGHT.value
                ],
            }
        )
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data
    )
    await init_integration(hass, [config_entry])

    yield {
        "light_aggregate_id": light_aggregate_id,
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
        "config_entry": config_entry,
        "area_id": DEFAULT_MOCK_AREA.value,
    }

    await shutdown_integration(hass, [config_entry])


@pytest.fixture
async def setup_windowless_area(
    hass: HomeAssistant,
) -> AsyncGenerator[dict[str, Any]]:
    """Sets-up windowless area."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    # Update area config with windowless flag
    area_config = data.get("area", {})
    area_config[AreaConfigOptions.WINDOWLESS.key] = True
    data["area"] = area_config

    config_entry = MockConfigEntry(
        domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data
    )
    await init_integration(hass, [config_entry])

    yield {
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
        "config_entry": config_entry,
        "area_id": DEFAULT_MOCK_AREA.value,
    }

    await shutdown_integration(hass, [config_entry])


@pytest.fixture
async def setup_basic_area_no_aggregates(
    hass: HomeAssistant,
) -> AsyncGenerator[dict[str, Any]]:
    """Sets-up basic area without aggregates (sun.sun fallback)."""

    # Create sun.sun entity
    hass.states.async_set("sun.sun", STATE_BELOW_HORIZON)

    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    # No aggregates in config

    config_entry = MockConfigEntry(
        domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data
    )
    await init_integration(hass, [config_entry])

    yield {
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
        "config_entry": config_entry,
        "area_id": DEFAULT_MOCK_AREA.value,
    }

    await shutdown_integration(hass, [config_entry])


# Tests


class TestLightEntityResolution:
    """Test automatic light entity resolution cascade."""

    async def test_area_illuminance_sensor_priority(
        self, hass: HomeAssistant, setup_area_with_threshold: dict
    ):
        """Test that area's threshold sensor is resolved first (priority 1)."""
        threshold_sensor_id = setup_area_with_threshold["threshold_aggregate_id"]
        area_state_id = setup_area_with_threshold["area_state_id"]

        # Threshold sensor is OFF by default (dark)
        threshold_state = hass.states.get(threshold_sensor_id)
        assert_state(threshold_state, STATE_OFF)

        # Area should have DARK state
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)

    async def test_area_light_aggregate_fallback(
        self, hass: HomeAssistant, setup_area_with_light_aggregate: dict
    ):
        """Test fallback to light aggregate when no threshold (priority 2)."""
        light_aggregate_id = setup_area_with_light_aggregate["light_aggregate_id"]
        area_state_id = setup_area_with_light_aggregate["area_state_id"]

        # Light aggregate is OFF by default (dark)
        light_aggregate_state = hass.states.get(light_aggregate_id)
        assert_state(light_aggregate_state, STATE_OFF)

        # Area should have DARK state
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)

    async def test_windowless_area_no_light_sensor(
        self, hass: HomeAssistant, setup_windowless_area: dict
    ):
        """Test windowless area has None for light sensor (priority 3)."""
        area_state_id = setup_windowless_area["area_state_id"]

        # Windowless area should always be dark
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)

    async def test_sun_fallback_no_aggregates(
        self, hass: HomeAssistant, setup_basic_area_no_aggregates: dict
    ):
        """Test sun.sun fallback when no aggregates (priority 6)."""
        area_state_id = setup_basic_area_no_aggregates["area_state_id"]

        # sun.sun is below horizon by default (dark)
        sun_state = hass.states.get("sun.sun")
        assert_state(sun_state, STATE_BELOW_HORIZON)

        # Area should have DARK state
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)


class TestDarknessDetection:
    """Test is_area_dark() behavior with different sensors."""

    async def test_illuminance_sensor_off_means_dark(
        self, hass: HomeAssistant, setup_area_with_threshold: dict
    ):
        """Test area is dark when threshold sensor is OFF."""
        illuminance_sensor = setup_area_with_threshold["illuminance_sensor"]
        area_state_id = setup_area_with_threshold["area_state_id"]

        # Make threshold sensor OFF (dark)
        await set_illuminance_sensor_state(
            hass, illuminance_sensor, ILLUMINANCE_SENSOR_OFF_VALUE
        )

        # Verify area has DARK state
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)

    async def test_illuminance_sensor_on_means_bright(
        self, hass: HomeAssistant, setup_area_with_threshold: dict
    ):
        """Test area is bright when threshold sensor is ON."""
        illuminance_sensor = setup_area_with_threshold["illuminance_sensor"]
        area_state_id = setup_area_with_threshold["area_state_id"]

        # Make threshold sensor ON (bright)
        await set_illuminance_sensor_state(
            hass, illuminance_sensor, ILLUMINANCE_SENSOR_ON_VALUE
        )

        # Verify area has BRIGHT state (not DARK)
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, AreaStates.DARK, negate=True
        )
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, AreaStates.BRIGHT
        )

    async def test_windowless_always_dark(
        self, hass: HomeAssistant, setup_windowless_area: dict
    ):
        """Test windowless area is always dark."""
        area_state_id = setup_windowless_area["area_state_id"]

        # Verify area has DARK state
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)

        # Even with sun.sun above horizon, should stay dark
        await set_sun_state(hass, above_horizon=True)

        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)

    async def test_sun_below_horizon_means_dark(
        self, hass: HomeAssistant, setup_basic_area_no_aggregates: dict
    ):
        """Test sun.sun below_horizon means dark."""
        area_state_id = setup_basic_area_no_aggregates["area_state_id"]

        # Set sun to below horizon
        await set_sun_state(hass, above_horizon=False)

        # Verify area is dark
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)

    async def test_sun_above_horizon_means_bright(
        self, hass: HomeAssistant, setup_basic_area_no_aggregates: dict
    ):
        """Test sun.sun above_horizon means bright."""
        area_state_id = setup_basic_area_no_aggregates["area_state_id"]

        # Set sun to above horizon
        await set_sun_state(hass, above_horizon=True)

        # Verify area is bright
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, AreaStates.DARK, negate=True
        )
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, AreaStates.BRIGHT
        )

    async def test_unavailable_sensor_defaults_dark(
        self, hass: HomeAssistant, setup_area_with_threshold: dict
    ):
        """Test unavailable sensor defaults to dark (safe default)."""
        illuminance_sensor = setup_area_with_threshold["illuminance_sensor"]
        area_state_id = setup_area_with_threshold["area_state_id"]

        # Make sensor unavailable
        hass.states.async_set(
            illuminance_sensor.entity_id,
            STATE_UNAVAILABLE,
            attributes={"unit_of_measurement": LIGHT_LUX},
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.5)

        # Should default to dark
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)

    async def test_unknown_sensor_defaults_dark(
        self, hass: HomeAssistant, setup_area_with_threshold: dict
    ):
        """Test unknown sensor state defaults to dark (safe default)."""
        illuminance_sensor = setup_area_with_threshold["illuminance_sensor"]
        area_state_id = setup_area_with_threshold["area_state_id"]

        # Make sensor unknown
        hass.states.async_set(
            illuminance_sensor.entity_id,
            STATE_UNKNOWN,
            attributes={"unit_of_measurement": LIGHT_LUX},
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.5)

        # Should default to dark
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)


class TestStateChangeListeners:
    """Test that light sensor state changes update area state."""

    async def test_light_sensor_change_updates_area_state(
        self, hass: HomeAssistant, setup_area_with_threshold: dict
    ):
        """Test that light sensor state changes update area state."""
        illuminance_sensor = setup_area_with_threshold["illuminance_sensor"]
        area_state_id = setup_area_with_threshold["area_state_id"]

        # Start dark
        await set_illuminance_sensor_state(
            hass, illuminance_sensor, ILLUMINANCE_SENSOR_OFF_VALUE
        )

        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)

        # Change to bright
        await set_illuminance_sensor_state(
            hass, illuminance_sensor, ILLUMINANCE_SENSOR_ON_VALUE
        )

        # Verify area updated to bright
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, AreaStates.DARK, negate=True
        )
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, AreaStates.BRIGHT
        )

    async def test_windowless_ignores_sun_changes(
        self, hass: HomeAssistant, setup_windowless_area: dict
    ):
        """Test windowless area doesn't respond to sun.sun changes."""
        area_state_id = setup_windowless_area["area_state_id"]

        # Verify starts dark
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)

        # Change sun state
        await set_sun_state(hass, above_horizon=True)

        # Area should stay dark (no listener on sun for windowless)
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.DARK)
