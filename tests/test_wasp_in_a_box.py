"""Test for Wasp in a box sensor behavior."""

import asyncio
from collections.abc import AsyncGenerator
import logging
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.binary_sensor.wasp_in_a_box import (
    ATTR_BOX,
    ATTR_WASP,
)
from custom_components.magic_areas.const import DOMAIN, AreaAttributes, CommonAttributes
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.wasp_in_a_box import WaspInABoxOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_attribute,
    assert_in_attribute,
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor

_LOGGER = logging.getLogger(__name__)

# Fixtures


@pytest.fixture(name="wasp_in_a_box_config_entry")
def mock_config_entry_wasp_in_a_box() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    merge_feature_config(
        data,
        WaspInABoxOptions.to_config(
            {
                WaspInABoxOptions.DELAY.key: 0,
                WaspInABoxOptions.WASP_TIMEOUT.key: 1,
            }
        ),
        AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_wasp_in_a_box")
async def setup_integration_wasp_in_a_box(
    hass: HomeAssistant,
    wasp_in_a_box_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with Wasp in a box (and aggregates) config."""

    await init_integration(hass, [wasp_in_a_box_config_entry])
    yield
    await shutdown_integration(hass, [wasp_in_a_box_config_entry])


# Entities


@pytest.fixture(name="entities_wasp_in_a_box")
async def setup_entities_wasp_in_a_box(
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


async def test_wasp_in_a_box_logic(
    hass: HomeAssistant,
    entities_wasp_in_a_box: list[MockBinarySensor],
    _setup_integration_wasp_in_a_box,
) -> None:
    """Test the Wasp in a box sensor logic."""

    motion_sensor_entity_id = entities_wasp_in_a_box[0].entity_id
    door_sensor_entity_id = entities_wasp_in_a_box[1].entity_id

    wasp_in_a_box_entity_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_wasp_in_a_box_{DEFAULT_MOCK_AREA}"
    )
    motion_aggregate_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{DEFAULT_MOCK_AREA}_aggregate_motion"
    door_aggregate_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{DEFAULT_MOCK_AREA}_aggregate_door"

    # Ensure source entities are loaded
    motion_sensor_state = hass.states.get(motion_sensor_entity_id)
    assert_state(motion_sensor_state, STATE_OFF)

    door_sensor_state = hass.states.get(door_sensor_entity_id)
    assert_state(door_sensor_state, STATE_OFF)

    # Ensure aggregates are loaded
    motion_aggregate_state = hass.states.get(motion_aggregate_entity_id)
    assert_state(motion_aggregate_state, STATE_OFF)

    door_aggregate_state = hass.states.get(door_aggregate_entity_id)
    assert_state(door_aggregate_state, STATE_OFF)

    # Ensure Wasp in a box sensor is loaded
    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_WASP, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_BOX, STATE_OFF)

    # Test motion door open behavior
    hass.states.async_set(door_sensor_entity_id, STATE_ON)
    await asyncio.sleep(1)
    await hass.async_block_till_done()

    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_WASP, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_BOX, STATE_ON)

    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_ON)
    assert_attribute(wasp_in_a_box_state, ATTR_WASP, STATE_ON)
    assert_attribute(wasp_in_a_box_state, ATTR_BOX, STATE_ON)

    hass.states.async_set(motion_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_WASP, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_BOX, STATE_ON)

    # Test motion on door closed behavior
    hass.states.async_set(door_sensor_entity_id, STATE_OFF)
    await asyncio.sleep(1)
    await hass.async_block_till_done()

    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_WASP, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_BOX, STATE_OFF)

    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_ON)
    assert_attribute(wasp_in_a_box_state, ATTR_WASP, STATE_ON)
    assert_attribute(wasp_in_a_box_state, ATTR_BOX, STATE_OFF)

    hass.states.async_set(motion_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_ON)
    assert_attribute(wasp_in_a_box_state, ATTR_WASP, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_BOX, STATE_OFF)

    # Test door open releases wasp
    hass.states.async_set(door_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Wait a bit for wasp sensor to trigger
    await asyncio.sleep(1)
    await hass.async_block_till_done()

    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_WASP, STATE_OFF)
    assert_attribute(wasp_in_a_box_state, ATTR_BOX, STATE_ON)


async def test_wasp_in_a_box_as_presence(
    hass: HomeAssistant,
    entities_wasp_in_a_box: list[MockBinarySensor],
    _setup_integration_wasp_in_a_box,
) -> None:
    """Test the Wasp in a box sensor triggers area presence."""

    motion_sensor_entity_id = entities_wasp_in_a_box[0].entity_id
    door_sensor_entity_id = entities_wasp_in_a_box[1].entity_id
    wasp_in_a_box_entity_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_wasp_in_a_box_{DEFAULT_MOCK_AREA}"
    )
    area_state_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA}_area_state"

    # Set initial values
    hass.states.async_set(motion_sensor_entity_id, STATE_OFF)
    hass.states.async_set(door_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Ensure initial values are set
    door_sensor_state = hass.states.get(door_sensor_entity_id)
    assert_state(door_sensor_state, STATE_ON)

    motion_sensor_state = hass.states.get(motion_sensor_entity_id)
    assert_state(motion_sensor_state, STATE_OFF)

    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_OFF)

    area_sensor_state = hass.states.get(area_state_entity_id)
    assert_state(area_sensor_state, STATE_OFF)
    assert_in_attribute(
        area_sensor_state,
        AreaAttributes.PRESENCE_SENSORS.value,
        wasp_in_a_box_entity_id,
    )

    # Test presence tracking
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_ON)

    area_sensor_state = hass.states.get(area_state_entity_id)
    assert_state(area_sensor_state, STATE_ON)
    assert_in_attribute(
        area_sensor_state,
        CommonAttributes.ACTIVE_SENSORS.value,
        wasp_in_a_box_entity_id,
    )

    hass.states.async_set(motion_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    wasp_in_a_box_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wasp_in_a_box_state, STATE_OFF)

    area_sensor_state = hass.states.get(area_state_entity_id)
    assert_state(area_sensor_state, STATE_OFF)


# Wasp Timeout tests


async def test_wasp_timeout_triggers_forget(
    hass: HomeAssistant,
    entities_wasp_in_a_box: list[MockBinarySensor],
    _setup_integration_wasp_in_a_box,
    patch_async_call_later,
) -> None:
    """Test that the wasp timeout triggers the forget function.

    If the wasp sensor goes OFF while the box is closed, the timeout should expire
    and the wasp should be forgotten (the area entity turns off and attributes show off).
    """

    motion_sensor_entity_id = entities_wasp_in_a_box[0].entity_id
    door_sensor_entity_id = entities_wasp_in_a_box[1].entity_id

    wasp_in_a_box_entity_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_wasp_in_a_box_{DEFAULT_MOCK_AREA}"
    )

    # Ensure initial wasp present: motion ON, box closed
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    hass.states.async_set(door_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    wiab_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wiab_state, STATE_ON)
    assert_attribute(wiab_state, ATTR_WASP, STATE_ON)
    assert_attribute(wiab_state, ATTR_BOX, STATE_OFF)

    # Motion stops -> timeout should fire (immediate via patched async_call_later)
    hass.states.async_set(motion_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    final = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(final, STATE_OFF)
    assert_attribute(final, ATTR_WASP, STATE_OFF)
    assert_attribute(final, ATTR_BOX, STATE_OFF)


async def test_open_box_cancels_timer(
    hass: HomeAssistant,
    entities_wasp_in_a_box: list[MockBinarySensor],
    _setup_integration_wasp_in_a_box,
) -> None:
    """Test that opening the box cancels the forget timer.

    If the wasp sensor goes OFF and a timeout is scheduled,
    but then the door (box) opens, the timer should be cancelled
    and the wasp forgotten immediately by box-open logic.
    """
    motion_sensor_entity_id = entities_wasp_in_a_box[0].entity_id
    door_sensor_entity_id = entities_wasp_in_a_box[1].entity_id

    wasp_in_a_box_entity_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_wasp_in_a_box_{DEFAULT_MOCK_AREA}"
    )

    # Initial: wasp present
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    hass.states.async_set(door_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    wiab_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wiab_state, STATE_ON)
    assert_attribute(wiab_state, ATTR_WASP, STATE_ON)
    assert_attribute(wiab_state, ATTR_BOX, STATE_OFF)

    # Motion OFF → schedule timer but capture callback
    fired = {}

    def capture_callback(hass_inner, delay, callback):
        fired["callback"] = callback
        return lambda: None  # dummy cancel

    with patch(
        "custom_components.magic_areas.helpers.timer.async_call_later",
        side_effect=capture_callback,
    ):
        hass.states.async_set(motion_sensor_entity_id, STATE_OFF)
        await hass.async_block_till_done()

    # Door opens → triggers wasp_in_a_box before timer fires
    hass.states.async_set(door_sensor_entity_id, STATE_ON)

    # Let HA propagate the aggregate updates
    for _ in range(2):
        await asyncio.sleep(0)
        await hass.async_block_till_done()

    final = hass.states.get(wasp_in_a_box_entity_id)
    # The box is now open, wasp is off, timer cancelled
    assert_state(final, STATE_OFF)
    assert_attribute(final, ATTR_BOX, STATE_ON)

    # Optionally fire captured timer callback — should have no effect
    if "callback" in fired:
        await fired["callback"](None)
        for _ in range(2):
            await asyncio.sleep(0)
            await hass.async_block_till_done()
        final_after = hass.states.get(wasp_in_a_box_entity_id)
        assert_state(final_after, STATE_OFF)
        assert_attribute(final_after, ATTR_BOX, STATE_ON)


async def test_wasp_seen_cancels_timer(
    hass: HomeAssistant,
    entities_wasp_in_a_box: list[MockBinarySensor],
    _setup_integration_wasp_in_a_box,
    patch_async_call_later,
) -> None:
    """Test that seeing the wasp again cancels the forget timer.

    If the wasp sensor goes OFF and a timeout is scheduled,
    but then it goes back to ON before the timeout expires,
    the timer should be cancelled and the wasp remains present.
    """
    motion_sensor_entity_id = entities_wasp_in_a_box[0].entity_id
    door_sensor_entity_id = entities_wasp_in_a_box[1].entity_id

    wasp_in_a_box_entity_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_wasp_in_a_box_{DEFAULT_MOCK_AREA}"
    )

    # Initial: wasp present
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    hass.states.async_set(door_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    wiab_state = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(wiab_state, STATE_ON)
    assert_attribute(wiab_state, ATTR_WASP, STATE_ON)

    # Motion OFF -> schedule timer
    hass.states.async_set(motion_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    # Motion ON again -> cancels timer, wasp stays present
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    final = hass.states.get(wasp_in_a_box_entity_id)
    assert_state(final, STATE_ON)
    assert_attribute(final, ATTR_WASP, STATE_ON)
