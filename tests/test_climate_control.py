"""Tests for the BLE Tracker feature."""

from collections.abc import AsyncGenerator
import logging
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate.const import (
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_PRESET_MODE,
    HVACMode,
)
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN
from custom_components.magic_areas.const.climate_control import ClimateControlOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_attribute,
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
    trigger_occupancy,
)
from tests.mocks import MockBinarySensor, MockClimate

_LOGGER = logging.getLogger(__name__)


# Constants

MOCK_CLIMATE_ENTITY_ID = f"{CLIMATE_DOMAIN}.mock_climate"
CLIMATE_CONTROL_SWITCH_ENTITY_ID = (
    f"{SWITCH_DOMAIN}.magic_areas_climate_control_{DEFAULT_MOCK_AREA}"
)
AREA_SENSOR_ENTITY_ID = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA}_area_state"


# Fixtures


@pytest.fixture(name="climate_control_config_entry")
def mock_config_entry_climate_control() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        ClimateControlOptions.to_config(
            {
                ClimateControlOptions.ENTITY_ID.key: MOCK_CLIMATE_ENTITY_ID,
                ClimateControlOptions.PRESET_OCCUPIED.key: PRESET_NONE,
                ClimateControlOptions.PRESET_CLEAR.key: PRESET_AWAY,
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_climate_control")
async def setup_integration_climate_control(
    hass: HomeAssistant,
    climate_control_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with BLE tracker config."""

    await init_integration(hass, [climate_control_config_entry])
    yield
    await shutdown_integration(hass, [climate_control_config_entry])


# Entities


@pytest.fixture(name="entities_climate_one")
async def setup_entities_climate_one(
    hass: HomeAssistant,
) -> list[MockClimate]:
    """Create one mock climate and setup the system with it."""
    mock_climate_entities = [
        MockClimate(
            name="mock_climate",
            unique_id="unique_mock_climate",
        )
    ]
    await setup_mock_entities(
        hass, CLIMATE_DOMAIN, {DEFAULT_MOCK_AREA: mock_climate_entities}
    )
    return mock_climate_entities


# Tests


async def test_climate_control_init(
    hass: HomeAssistant,
    entities_climate_one: list[MockClimate],
    _setup_integration_climate_control,
) -> None:
    """Test climate control."""

    area_sensor_state = hass.states.get(AREA_SENSOR_ENTITY_ID)
    assert_state(area_sensor_state, STATE_OFF)

    climate_control_switch_state = hass.states.get(CLIMATE_CONTROL_SWITCH_ENTITY_ID)
    assert_state(climate_control_switch_state, STATE_OFF)

    climate_state = hass.states.get(MOCK_CLIMATE_ENTITY_ID)
    assert_state(climate_state, STATE_OFF)

    # Turn on the climate device
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MOCK_CLIMATE_ENTITY_ID}
    )
    await hass.async_block_till_done()

    climate_state = hass.states.get(MOCK_CLIMATE_ENTITY_ID)
    assert_state(climate_state, HVACMode.AUTO)

    # Reset preset mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: MOCK_CLIMATE_ENTITY_ID, ATTR_PRESET_MODE: PRESET_ECO},
    )
    await hass.async_block_till_done()

    climate_state = hass.states.get(MOCK_CLIMATE_ENTITY_ID)
    assert_attribute(climate_state, ATTR_PRESET_MODE, PRESET_ECO)


async def test_climate_control_logic(
    hass: HomeAssistant,
    entities_climate_one: list[MockClimate],
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_climate_control,
) -> None:
    """Test climate control logic."""

    motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id
    motion_sensor_state = hass.states.get(motion_sensor_entity_id)
    assert_state(motion_sensor_state, STATE_OFF)

    # Turn on the climate device
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MOCK_CLIMATE_ENTITY_ID}
    )
    await hass.async_block_till_done()

    climate_state = hass.states.get(MOCK_CLIMATE_ENTITY_ID)
    assert_state(climate_state, HVACMode.AUTO)

    # Set initial preset to something we don't use, so we know we changed from it
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: MOCK_CLIMATE_ENTITY_ID, ATTR_PRESET_MODE: PRESET_ECO},
    )
    await hass.async_block_till_done()

    climate_state = hass.states.get(MOCK_CLIMATE_ENTITY_ID)
    assert_attribute(climate_state, ATTR_PRESET_MODE, PRESET_ECO)

    # @TODO test control off, ensure nothing happens

    # Turn on climate control
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: CLIMATE_CONTROL_SWITCH_ENTITY_ID},
    )
    await hass.async_block_till_done()

    # Area occupied, preset should be PRESET_NONE
    await trigger_occupancy(hass, motion_sensor_entity_id, occupied=True)

    motion_sensor_state = hass.states.get(motion_sensor_entity_id)
    assert_state(motion_sensor_state, STATE_ON)

    area_sensor_state = hass.states.get(AREA_SENSOR_ENTITY_ID)
    assert_state(area_sensor_state, STATE_ON)

    climate_state = hass.states.get(MOCK_CLIMATE_ENTITY_ID)
    assert_attribute(climate_state, ATTR_PRESET_MODE, PRESET_NONE)

    # Area clear, preset should be PRESET_AWAY
    await trigger_occupancy(hass, motion_sensor_entity_id, occupied=False)

    motion_sensor_state = hass.states.get(motion_sensor_entity_id)
    assert_state(motion_sensor_state, STATE_OFF)

    area_sensor_state = hass.states.get(AREA_SENSOR_ENTITY_ID)
    assert_state(area_sensor_state, STATE_OFF)

    climate_state = hass.states.get(MOCK_CLIMATE_ENTITY_ID)
    assert_attribute(climate_state, ATTR_PRESET_MODE, PRESET_AWAY)
