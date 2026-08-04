"""Test for the door transition occupancy sensor behavior.

Covers discussion #610: a door (or garage door) sensor transitioning state
(opening or closing) should be treated as an early, short-lived presence
signal -- it typically happens before a motion/PIR sensor can see the
person.
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
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.binary_sensor.door_occupancy import (
    ATTR_LAST_DOOR_ENTITY_ID,
)
from custom_components.magic_areas.const import (
    ATTR_ACTIVE_SENSORS,
    ATTR_PRESENCE_SENSORS,
    CONF_DOOR_TRANSITION_OCCUPANCY_TIMEOUT,
    DOMAIN,
)

from tests.conftest import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_attribute,
    assert_in_attribute,
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor

_LOGGER = logging.getLogger(__name__)

DOOR_TRANSITION_ENTITY_ID = (
    f"{BINARY_SENSOR_DOMAIN}.magic_areas_door_transition_occupancy_{DEFAULT_MOCK_AREA}"
)
AREA_STATE_ENTITY_ID = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA}_area_state"

# Fixtures


@pytest.fixture(name="door_transition_config_entry")
def mock_config_entry_door_transition() -> MockConfigEntry:
    """Fixture for mock configuration entry with door transition occupancy enabled."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update({CONF_DOOR_TRANSITION_OCCUPANCY_TIMEOUT: 5})
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_door_transition")
async def setup_integration_door_transition(
    hass: HomeAssistant,
    door_transition_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with door transition occupancy config."""

    await init_integration(hass, [door_transition_config_entry])
    yield
    await shutdown_integration(hass, [door_transition_config_entry])


@pytest.fixture(name="entities_door_transition")
async def setup_entities_door_transition(
    hass: HomeAssistant,
) -> list[MockBinarySensor]:
    """Create motion and door sensors."""
    mock_binary_sensor_entities = [
        MockBinarySensor(
            name="motion_sensor",
            unique_id="unique_motion",
            device_class=BinarySensorDeviceClass.MOTION,
        ),
        MockBinarySensor(
            name="door_sensor",
            unique_id="unique_door",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
    ]
    await setup_mock_entities(
        hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: mock_binary_sensor_entities}
    )
    return mock_binary_sensor_entities


# Tests


async def test_door_transition_sensor_not_created_when_disabled(
    hass: HomeAssistant,
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_basic,
) -> None:
    """Test that the sensor isn't created when the timeout is 0 (default/disabled)."""

    assert hass.states.get(DOOR_TRANSITION_ENTITY_ID) is None


async def test_door_transition_opens_and_closes_pulse_occupancy(
    hass: HomeAssistant,
    entities_door_transition: list[MockBinarySensor],
    _setup_integration_door_transition,
) -> None:
    """Test that any door transition (open or close) pulses the sensor on."""

    motion_sensor_entity_id = entities_door_transition[0].entity_id
    door_sensor_entity_id = entities_door_transition[1].entity_id

    # Ensure source entities are loaded
    assert_state(hass.states.get(motion_sensor_entity_id), STATE_OFF)
    assert_state(hass.states.get(door_sensor_entity_id), STATE_OFF)

    # Ensure door transition occupancy sensor was created and is off
    door_transition_state = hass.states.get(DOOR_TRANSITION_ENTITY_ID)
    assert_state(door_transition_state, STATE_OFF)

    # It should be registered as a presence sensor for the area
    area_state = hass.states.get(AREA_STATE_ENTITY_ID)
    assert_state(area_state, STATE_OFF)
    assert_in_attribute(
        area_state, ATTR_PRESENCE_SENSORS, DOOR_TRANSITION_ENTITY_ID
    )

    # Open the door -> pulse on, area becomes occupied
    hass.states.async_set(door_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    door_transition_state = hass.states.get(DOOR_TRANSITION_ENTITY_ID)
    assert_state(door_transition_state, STATE_ON)
    assert_attribute(
        door_transition_state, ATTR_LAST_DOOR_ENTITY_ID, door_sensor_entity_id
    )

    area_state = hass.states.get(AREA_STATE_ENTITY_ID)
    assert_state(area_state, STATE_ON)
    assert_in_attribute(area_state, ATTR_ACTIVE_SENSORS, DOOR_TRANSITION_ENTITY_ID)

    # Motion never actually saw anything
    assert_state(hass.states.get(motion_sensor_entity_id), STATE_OFF)

    # Closing the door is *also* a transition and should pulse again
    hass.states.async_set(door_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    door_transition_state = hass.states.get(DOOR_TRANSITION_ENTITY_ID)
    assert_state(door_transition_state, STATE_ON)
    assert_attribute(
        door_transition_state, ATTR_LAST_DOOR_ENTITY_ID, door_sensor_entity_id
    )


async def test_door_transition_pulse_expires_and_area_clears(
    hass: HomeAssistant,
    entities_door_transition: list[MockBinarySensor],
    _setup_integration_door_transition,
    patch_async_call_later,
) -> None:
    """Test that once the pulse timeout expires, the sensor (and area) clear.

    `patch_async_call_later` makes the door-transition pulse timer (a
    ReusableTimer) fire immediately instead of waiting the real 5 seconds.
    The area's own clear_timeout is 0 (test default), so once no presence
    sensor is active it should clear right away too.
    """

    door_sensor_entity_id = entities_door_transition[1].entity_id

    # With the timer patched to fire immediately, the full on->off pulse
    # cycle (and the resulting area clear_timeout=0 re-evaluation) happens
    # within this single state change + block_till_done.
    hass.states.async_set(door_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Let anything scheduled on the loop as a follow-up (e.g. the area's
    # own clear_timeout callback) finish propagating.
    for _ in range(3):
        await asyncio.sleep(0)
        await hass.async_block_till_done()

    door_transition_state = hass.states.get(DOOR_TRANSITION_ENTITY_ID)
    assert_state(door_transition_state, STATE_OFF)

    area_state = hass.states.get(AREA_STATE_ENTITY_ID)
    assert_state(area_state, STATE_OFF)
