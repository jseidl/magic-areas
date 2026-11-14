"""Tests for the binary sensor platform setup (health, aggregates, wasp, BLE)."""

from collections.abc import AsyncGenerator
import logging
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.ble_trackers import BleTrackerOptions
from custom_components.magic_areas.const.health import HealthOptions
from custom_components.magic_areas.const.wasp_in_a_box import WaspInABoxOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor

_LOGGER = logging.getLogger(__name__)

SLUG = DEFAULT_MOCK_AREA.value
HEALTH_ENTITY_ID = f"{BINARY_SENSOR_DOMAIN}.magic_areas_health_{SLUG}_health_problem"
WASP_ENTITY_ID = f"{BINARY_SENSOR_DOMAIN}.magic_areas_wasp_in_a_box_{SLUG}"
BLE_ENTITY_ID = (
    f"{BINARY_SENSOR_DOMAIN}.magic_areas_ble_trackers_{SLUG}_ble_tracker_monitor"
)
MODULE = "custom_components.magic_areas.binary_sensor"


def _aggregate_id(device_class: str) -> str:
    """Return the entity id of a binary sensor aggregate."""
    return (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{SLUG}_aggregate_{device_class}"
    )


def _sensor(device_class: BinarySensorDeviceClass, index: int = 1) -> MockBinarySensor:
    """Create a mock binary sensor of the given device class."""
    return MockBinarySensor(
        name=f"{device_class.value}_{index}",
        unique_id=f"{device_class.value}_{index}",
        device_class=device_class,
    )


async def _setup(
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


@pytest.fixture(name="config_entries_to_unload")
async def fixture_config_entries_to_unload(
    hass: HomeAssistant,
) -> AsyncGenerator[list[MockConfigEntry]]:
    """Unload every entry registered by a test once it is done."""
    entries: list[MockConfigEntry] = []
    yield entries
    await shutdown_integration(hass, entries)


class TestHealthSensor:
    """Test the health binary sensor creation."""

    async def test_health_sensor_tracks_distress_sensors(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test the health sensor groups the distress device classes only."""
        smoke = _sensor(BinarySensorDeviceClass.SMOKE)
        problem = _sensor(BinarySensorDeviceClass.PROBLEM)
        motion = _sensor(BinarySensorDeviceClass.MOTION)

        config_entries_to_unload.append(
            await _setup(hass, [smoke, problem, motion], HealthOptions.to_config({}))
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
            await _setup(
                hass,
                [_sensor(BinarySensorDeviceClass.MOTION)],
                HealthOptions.to_config({}),
            )
        )

        assert hass.states.get(HEALTH_ENTITY_ID) is None

    async def test_no_health_sensor_without_binary_sensors(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test no health sensor is created when the area has no binary sensors."""
        config_entries_to_unload.append(
            await _setup(hass, [], HealthOptions.to_config({}))
        )

        assert hass.states.get(HEALTH_ENTITY_ID) is None

    async def test_health_sensor_creation_error_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test a failing health sensor does not break the platform."""
        with patch(
            f"{MODULE}.AreaHealthBinarySensor", side_effect=RuntimeError("boom")
        ):
            config_entries_to_unload.append(
                await _setup(
                    hass,
                    [_sensor(BinarySensorDeviceClass.SMOKE)],
                    HealthOptions.to_config({}),
                )
            )

        assert hass.states.get(HEALTH_ENTITY_ID) is None
        assert "Error creating area health sensor: boom" in caplog.text


class TestAggregateSensors:
    """Test the binary sensor aggregate creation rules."""

    async def test_aggregate_created_when_minimum_is_met(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test an aggregate exists for a configured device class."""
        config_entries_to_unload.append(
            await _setup(
                hass,
                [
                    _sensor(BinarySensorDeviceClass.MOTION, 1),
                    _sensor(BinarySensorDeviceClass.MOTION, 2),
                ],
                AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 2}),
            )
        )

        assert hass.states.get(_aggregate_id("motion")) is not None

    async def test_aggregate_skipped_below_minimum_entities(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test a device class with too few sensors gets no aggregate."""
        config_entries_to_unload.append(
            await _setup(
                hass,
                [_sensor(BinarySensorDeviceClass.MOTION, 1)],
                AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 2}),
            )
        )

        assert hass.states.get(_aggregate_id("motion")) is None

    async def test_aggregate_skipped_for_unconfigured_device_class(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test a device class that is not configured gets no aggregate."""
        config_entries_to_unload.append(
            await _setup(
                hass,
                [_sensor(BinarySensorDeviceClass.MOTION, 1)],
                AggregateOptions.to_config(
                    {
                        AggregateOptions.MIN_ENTITIES.key: 1,
                        AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key: ["door"],
                    }
                ),
            )
        )

        assert hass.states.get(_aggregate_id("motion")) is None

    async def test_aggregate_ignores_sensors_without_device_class(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test binary sensors with no device class are not aggregated."""
        no_class = MockBinarySensor(
            name="no_class", unique_id="no_class", device_class=None
        )
        config_entries_to_unload.append(
            await _setup(
                hass,
                [no_class],
                AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
            )
        )

        assert hass.states.get(no_class.entity_id) is not None
        for aggregate_class in ("motion", "door", "light", "occupancy", "window"):
            assert hass.states.get(_aggregate_id(aggregate_class)) is None

    async def test_aggregate_creation_error_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test a failing aggregate does not break the platform."""
        with patch(
            f"{MODULE}.AreaAggregateBinarySensor", side_effect=RuntimeError("boom")
        ):
            config_entries_to_unload.append(
                await _setup(
                    hass,
                    [_sensor(BinarySensorDeviceClass.MOTION, 1)],
                    AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
                )
            )

        assert hass.states.get(_aggregate_id("motion")) is None
        assert "Error creating 'motion' aggregate sensor: boom" in caplog.text


class TestWaspInABoxSetup:
    """Test the wasp in a box sensor creation rules."""

    async def test_wasp_requires_aggregates_feature(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test enabling wasp in a box without Aggregates warns and skips it."""
        config_entries_to_unload.append(
            await _setup(
                hass,
                [
                    _sensor(BinarySensorDeviceClass.MOTION),
                    _sensor(BinarySensorDeviceClass.DOOR),
                ],
                WaspInABoxOptions.to_config({}),
            )
        )

        assert hass.states.get(WASP_ENTITY_ID) is None
        assert "Wasp in a Box feature requires Aggregates feature" in caplog.text

    async def test_wasp_created_with_aggregates(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test wasp in a box is created, without a warning, when Aggregates is on."""
        config_entries_to_unload.append(
            await _setup(
                hass,
                [
                    _sensor(BinarySensorDeviceClass.MOTION),
                    _sensor(BinarySensorDeviceClass.DOOR),
                ],
                WaspInABoxOptions.to_config({}),
                AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
            )
        )

        assert hass.states.get(WASP_ENTITY_ID) is not None
        assert "Wasp in a Box feature requires Aggregates feature" not in caplog.text

    async def test_wasp_creation_error_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test a failing wasp in a box sensor does not break the platform."""
        with patch(
            f"{MODULE}.AreaWaspInABoxBinarySensor", side_effect=RuntimeError("boom")
        ):
            config_entries_to_unload.append(
                await _setup(
                    hass,
                    [
                        _sensor(BinarySensorDeviceClass.MOTION),
                        _sensor(BinarySensorDeviceClass.DOOR),
                    ],
                    WaspInABoxOptions.to_config({}),
                    AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
                )
            )

        assert hass.states.get(WASP_ENTITY_ID) is None
        assert "Error creating wasp in a box sensor: boom" in caplog.text


class TestBleTrackerSetup:
    """Test the BLE tracker sensor creation rules."""

    async def test_no_ble_sensor_without_configured_entities(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test the BLE tracker monitor is not created without tracked entities."""
        config_entries_to_unload.append(
            await _setup(hass, [], BleTrackerOptions.to_config({}))
        )

        assert hass.states.get(BLE_ENTITY_ID) is None

    async def test_ble_creation_error_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test a failing BLE tracker sensor does not break the platform."""
        with patch(
            f"{MODULE}.AreaBLETrackerBinarySensor", side_effect=RuntimeError("boom")
        ):
            config_entries_to_unload.append(
                await _setup(
                    hass,
                    [],
                    BleTrackerOptions.to_config(
                        {BleTrackerOptions.ENTITIES.key: ["sensor.ble_tracker_1"]}
                    ),
                )
            )

        assert hass.states.get(BLE_ENTITY_ID) is None
        assert "Error creating BLE tracker sensor: boom" in caplog.text
