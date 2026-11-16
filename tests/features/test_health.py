"""Tests for the health binary sensor."""

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN
from custom_components.magic_areas.const.health import HealthOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
)
from tests.mocks import MockBinarySensor

SLUG = DEFAULT_MOCK_AREA.value


HEALTH_ENTITY_ID = f"{BINARY_SENSOR_DOMAIN}.magic_areas_health_{SLUG}_health_problem"


BINARY_SENSOR_MODULE = "custom_components.magic_areas.binary_sensor"


def _make_binary_sensor(
    device_class: BinarySensorDeviceClass, index: int = 1
) -> MockBinarySensor:
    """Create a mock binary sensor of the given device class."""
    return MockBinarySensor(
        name=f"{device_class.value}_{index}",
        unique_id=f"{device_class.value}_{index}",
        device_class=device_class,
    )


async def _setup_binary_area(
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


class TestHealthSensor:
    """Test the health binary sensor creation."""

    async def test_health_sensor_tracks_distress_sensors(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test the health sensor groups the distress device classes only."""
        smoke = _make_binary_sensor(BinarySensorDeviceClass.SMOKE)
        problem = _make_binary_sensor(BinarySensorDeviceClass.PROBLEM)
        motion = _make_binary_sensor(BinarySensorDeviceClass.MOTION)

        config_entries_to_unload.append(
            await _setup_binary_area(
                hass, [smoke, problem, motion], HealthOptions.to_config({})
            )
        )

        health_state = hass.states.get(HEALTH_ENTITY_ID)
        assert health_state is not None
        assert_state(health_state, STATE_OFF)
        assert set(health_state.attributes["entity_id"]) == {
            smoke.entity_id,
            problem.entity_id,
        }

        hass.states.async_set(smoke.entity_id, STATE_ON)
        await hass.async_block_till_done()

        assert_state(hass.states.get(HEALTH_ENTITY_ID), STATE_ON)

    async def test_no_health_sensor_without_matching_device_class(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test no health sensor is created when no distress sensor exists."""
        config_entries_to_unload.append(
            await _setup_binary_area(
                hass,
                [_make_binary_sensor(BinarySensorDeviceClass.MOTION)],
                HealthOptions.to_config({}),
            )
        )

        assert hass.states.get(HEALTH_ENTITY_ID) is None

    async def test_no_health_sensor_without_binary_sensors(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test no health sensor is created when the area has no binary sensors."""
        config_entries_to_unload.append(
            await _setup_binary_area(hass, [], HealthOptions.to_config({}))
        )

        assert hass.states.get(HEALTH_ENTITY_ID) is None

    async def test_health_sensor_creation_error_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test a failing health sensor does not break the platform."""
        with patch(
            f"{BINARY_SENSOR_MODULE}.AreaHealthBinarySensor",
            side_effect=RuntimeError("boom"),
        ):
            config_entries_to_unload.append(
                await _setup_binary_area(
                    hass,
                    [_make_binary_sensor(BinarySensorDeviceClass.SMOKE)],
                    HealthOptions.to_config({}),
                )
            )

        assert hass.states.get(HEALTH_ENTITY_ID) is None
        assert "Error creating area health sensor: boom" in caplog.text
