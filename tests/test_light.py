"""Test for light groups."""

import asyncio
from collections.abc import AsyncGenerator
import logging
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import DATA_DISPATCHER

from custom_components.magic_areas.const import (
    CONF_ENABLED_FEATURES,
    CONF_FEATURE_LIGHT_GROUPS,
    CONF_OVERHEAD_LIGHTS,
    CONF_OVERHEAD_LIGHTS_ACT_ON,
    CONF_OVERHEAD_LIGHTS_STATES,
    DOMAIN,
    EVENT_MAGICAREAS_AREA_STATE_CHANGED,
    LIGHT_GROUP_ACT_ON_OCCUPANCY_CHANGE,
    AreaStates,
)

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_in_attribute,
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor, MockLight

_LOGGER = logging.getLogger(__name__)


# Fixtures


@pytest.fixture(name="light_groups_config_entry")
def mock_config_entry_light_groups() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        {
            CONF_ENABLED_FEATURES: {
                CONF_FEATURE_LIGHT_GROUPS: {
                    CONF_OVERHEAD_LIGHTS: ["light.mock_light_1"],
                    CONF_OVERHEAD_LIGHTS_ACT_ON: [LIGHT_GROUP_ACT_ON_OCCUPANCY_CHANGE],
                    CONF_OVERHEAD_LIGHTS_STATES: [AreaStates.OCCUPIED],
                },
            }
        }
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_light_groups")
async def setup_integration_light_groups(
    hass: HomeAssistant,
    light_groups_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with BLE tracker config."""

    await init_integration(hass, [light_groups_config_entry])
    yield
    await shutdown_integration(hass, [light_groups_config_entry])


# Entities


@pytest.fixture(name="entities_light_one")
async def setup_entities_light_one(
    hass: HomeAssistant,
) -> list[MockLight]:
    """Create one mock light and setup the system with it."""
    mock_light_entities = [
        MockLight(
            name="mock_light_1",
            state="off",
            unique_id="unique_light",
        )
    ]
    await setup_mock_entities(
        hass, LIGHT_DOMAIN, {DEFAULT_MOCK_AREA: mock_light_entities}
    )
    return mock_light_entities


# Tests


async def test_light_group_basic(
    hass: HomeAssistant,
    entities_light_one: list[MockLight],
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_light_groups,
) -> None:
    """Test light group."""

    mock_light_entity_id = entities_light_one[0].entity_id
    mock_motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id
    light_group_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_overhead_lights"
    )
    light_control_entity_id = (
        f"{SWITCH_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_light_control"
    )
    area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA}_area_state"

    # Test mock entity created
    mock_light_state = hass.states.get(mock_light_entity_id)
    assert_state(mock_light_state, STATE_OFF)

    # Test light group created
    light_group_state = hass.states.get(light_group_entity_id)
    assert_state(light_group_state, STATE_OFF)
    assert_in_attribute(light_group_state, ATTR_ENTITY_ID, mock_light_entity_id)

    # Test light control switch created
    light_control_state = hass.states.get(light_control_entity_id)
    assert_state(light_control_state, STATE_OFF)

    # Test motion sensor created
    motion_sensor_state = hass.states.get(mock_motion_sensor_entity_id)
    assert_state(motion_sensor_state, STATE_OFF)

    # Test area state
    area_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_state, STATE_OFF)

    # Turn on light control
    hass.states.async_set(light_control_entity_id, STATE_ON)
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: light_control_entity_id}
    )
    await hass.async_block_till_done()

    # Test light control switch state turned on
    light_control_state = hass.states.get(light_control_entity_id)
    assert_state(light_control_state, STATE_ON)

    # Turn motion sensor on
    hass.states.async_set(mock_motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    motion_sensor_state = hass.states.get(mock_motion_sensor_entity_id)
    assert_state(motion_sensor_state, STATE_ON)

    # Test area state is STATE_ON
    area_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_state, STATE_ON)

    await asyncio.sleep(1)

    # Check light group is on
    light_group_state = hass.states.get(light_group_entity_id)
    assert_state(light_group_state, STATE_ON)

    # Turn motion sensor off
    hass.states.async_set(mock_motion_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    # Test area state is STATE_OFF
    area_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_state, STATE_OFF)

    # Check light group is off
    light_group_state = hass.states.get(light_group_entity_id)
    assert_state(light_group_state, STATE_OFF)


async def test_light_group_releases_listeners_on_reload(
    hass: HomeAssistant,
    entities_light_one: list[MockLight],
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    light_groups_config_entry: MockConfigEntry,
    _setup_integration_light_groups,
) -> None:
    """Test that light groups unsubscribe from the area state dispatcher on reload.

    A leaked subscription keeps the previous AreaLightGroup instance alive and
    reacting to area state changes. That instance holds the MagicArea object
    from before the reload, whose states are frozen, so it acts on state the
    area no longer has.
    """

    def subscriber_count() -> int:
        dispatchers = hass.data.get(DATA_DISPATCHER, {})
        return len(dispatchers.get(EVENT_MAGICAREAS_AREA_STATE_CHANGED, {}))

    subscribers_before = subscriber_count()
    assert subscribers_before > 0

    for _ in range(3):
        await hass.config_entries.async_reload(light_groups_config_entry.entry_id)
        await hass.async_block_till_done()

        assert subscriber_count() == subscribers_before
