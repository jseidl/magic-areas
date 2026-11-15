"""Tests for the BLE Tracker feature."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN, AreaAttributes, CommonAttributes
from custom_components.magic_areas.const.ble_trackers import BleTrackerOptions

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

# Fixtures


@pytest.fixture(name="ble_tracker_config_entry")
def mock_config_entry_ble_tracker() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        BleTrackerOptions.to_config(
            {
                BleTrackerOptions.ENTITIES.key: ["sensor.ble_tracker_1"],
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_ble_tracker")
async def setup_integration_ble_tracker(
    hass: HomeAssistant,
    ble_tracker_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with BLE tracker config."""

    await init_integration(hass, [ble_tracker_config_entry])
    yield
    await shutdown_integration(hass, [ble_tracker_config_entry])


# Entities


@pytest.fixture(name="entities_ble_sensor_one")
async def setup_entities_ble_sensor_one(
    hass: HomeAssistant,
) -> list[MockSensor]:
    """Create one mock sensor and setup the system with it."""
    mock_ble_sensor_entities = [
        MockSensor(
            name="ble_sensor_1",
            unique_id="unique_ble_sensor",
            device_class=None,
        )
    ]
    await setup_mock_entities(
        hass, SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: mock_ble_sensor_entities}
    )
    return mock_ble_sensor_entities


# Tests


async def test_ble_tracker_presence_sensor(
    hass: HomeAssistant,
    entities_ble_sensor_one: list[MockSensor],
    _setup_integration_ble_tracker,
) -> None:
    """Test BLE tracker monitor functionality."""

    ble_sensor_entity_id = "sensor.ble_tracker_1"
    ble_tracker_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_ble_trackers_{DEFAULT_MOCK_AREA.value}_ble_tracker_monitor"
    area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state"

    hass.states.async_set(ble_sensor_entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()

    ble_sensor_state = hass.states.get(ble_sensor_entity_id)

    assert ble_sensor_state is not None
    assert ble_sensor_state.state is not None

    ble_tracker_state = hass.states.get(ble_tracker_entity_id)
    assert ble_tracker_state is not None
    assert ble_tracker_state.state == STATE_OFF
    assert ble_sensor_entity_id in ble_tracker_state.attributes[ATTR_ENTITY_ID]

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert area_sensor_state is not None
    assert area_sensor_state.state == STATE_OFF
    assert (
        ble_tracker_entity_id
        in area_sensor_state.attributes[AreaAttributes.PRESENCE_SENSORS.value]
    )

    # Set BLE sensor to DEFAULT_MOCK_AREA
    hass.states.async_set(ble_sensor_entity_id, DEFAULT_MOCK_AREA.value)
    await hass.async_block_till_done()

    ble_sensor_state = hass.states.get(ble_sensor_entity_id)
    assert_state(ble_sensor_state, DEFAULT_MOCK_AREA.value)

    ble_tracker_state = hass.states.get(ble_tracker_entity_id)
    assert_state(ble_tracker_state, STATE_ON)

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_ON)
    assert_in_attribute(
        area_sensor_state, CommonAttributes.ACTIVE_SENSORS.value, ble_tracker_entity_id
    )

    # Set BLE sensor to something else
    hass.states.async_set(ble_sensor_entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)

    ble_sensor_state = hass.states.get(ble_sensor_entity_id)
    assert_state(ble_sensor_state, STATE_UNKNOWN)

    ble_tracker_state = hass.states.get(ble_tracker_entity_id)
    assert_state(ble_tracker_state, STATE_OFF)

    area_sensor_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_sensor_state, STATE_OFF)


SLUG = DEFAULT_MOCK_AREA.value


BLE_ENTITY_ID = (
    f"{BINARY_SENSOR_DOMAIN}.magic_areas_ble_trackers_{SLUG}_ble_tracker_monitor"
)


BINARY_SENSOR_MODULE = "custom_components.magic_areas.binary_sensor"


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


@pytest.fixture(name="config_entries_to_unload")
async def fixture_config_entries_to_unload(
    hass: HomeAssistant,
) -> AsyncGenerator[list[MockConfigEntry]]:
    """Unload every entry registered by a test once it is done."""
    entries: list[MockConfigEntry] = []
    yield entries
    await shutdown_integration(hass, entries)


class TestBleTrackerSetup:
    """Test the BLE tracker sensor creation rules."""

    async def test_no_ble_sensor_without_configured_entities(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test the BLE tracker monitor is not created without tracked entities."""
        config_entries_to_unload.append(
            await _setup_binary_area(hass, [], BleTrackerOptions.to_config({}))
        )

        assert hass.states.get(BLE_ENTITY_ID) is None

    async def test_ble_creation_error_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test a failing BLE tracker sensor does not break the platform."""
        with patch(
            f"{BINARY_SENSOR_MODULE}.AreaBLETrackerBinarySensor",
            side_effect=RuntimeError("boom"),
        ):
            config_entries_to_unload.append(
                await _setup_binary_area(
                    hass,
                    [],
                    BleTrackerOptions.to_config(
                        {BleTrackerOptions.ENTITIES.key: ["sensor.ble_tracker_1"]}
                    ),
                )
            )

        assert hass.states.get(BLE_ENTITY_ID) is None
        assert "Error creating BLE tracker sensor: boom" in caplog.text
