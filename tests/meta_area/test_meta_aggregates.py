"""Test for aggregates on meta areas."""

import logging

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.const import MockAreaIds
from tests.helpers import assert_state
from tests.mocks import MockBinarySensor

_LOGGER = logging.getLogger(__name__)


# Tests
async def test_meta_aggregates_binary_sensor(
    hass: HomeAssistant,
    entities_binary_sensor_motion_all_areas_with_meta: dict[
        MockAreaIds, list[MockBinarySensor]
    ],
    _setup_integration_all_areas_with_meta,
) -> None:
    """Test aggregation of binary sensor states."""

    # Entity Ids
    interior_aggregate_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{MockAreaIds.INTERIOR.value}_aggregate_motion"
    exterior_aggregate_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{MockAreaIds.EXTERIOR.value}_aggregate_motion"
    global_aggregate_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{MockAreaIds.GLOBAL.value}_aggregate_motion"
    ground_level_aggregate_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{MockAreaIds.GROUND_LEVEL.value}_aggregate_motion"
    first_floor_aggregate_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{MockAreaIds.FIRST_FLOOR.value}_aggregate_motion"
    second_floor_aggregate_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{MockAreaIds.SECOND_FLOOR.value}_aggregate_motion"

    # First Floor + Interior + Global
    kitchen_motion_sensor_id = entities_binary_sensor_motion_all_areas_with_meta[
        MockAreaIds.KITCHEN
    ][0].entity_id

    # > On

    hass.states.async_set(kitchen_motion_sensor_id, STATE_ON)
    await hass.async_block_till_done()

    kitchen_motion_sensor_state = hass.states.get(kitchen_motion_sensor_id)
    assert_state(kitchen_motion_sensor_state, STATE_ON)

    first_floor_motion_sensor_state = hass.states.get(
        first_floor_aggregate_sensor_entity_id
    )
    assert_state(first_floor_motion_sensor_state, STATE_ON)

    interior_motion_sensor_state = hass.states.get(interior_aggregate_sensor_entity_id)
    assert_state(interior_motion_sensor_state, STATE_ON)

    global_motion_sensor_state = hass.states.get(global_aggregate_sensor_entity_id)
    assert_state(global_motion_sensor_state, STATE_ON)

    # > Off

    hass.states.async_set(kitchen_motion_sensor_id, STATE_OFF)
    await hass.async_block_till_done()

    kitchen_motion_sensor_state = hass.states.get(kitchen_motion_sensor_id)
    assert_state(kitchen_motion_sensor_state, STATE_OFF)

    first_floor_motion_sensor_state = hass.states.get(
        first_floor_aggregate_sensor_entity_id
    )
    assert_state(first_floor_motion_sensor_state, STATE_OFF)

    interior_motion_sensor_state = hass.states.get(interior_aggregate_sensor_entity_id)
    assert_state(interior_motion_sensor_state, STATE_OFF)

    global_motion_sensor_state = hass.states.get(global_aggregate_sensor_entity_id)
    assert_state(global_motion_sensor_state, STATE_OFF)

    # Second Floor
    master_bedroom_motion_sensor_id = entities_binary_sensor_motion_all_areas_with_meta[
        MockAreaIds.MASTER_BEDROOM
    ][0].entity_id

    # > On

    hass.states.async_set(master_bedroom_motion_sensor_id, STATE_ON)
    await hass.async_block_till_done()

    master_bedroom_motion_sensor_state = hass.states.get(
        master_bedroom_motion_sensor_id
    )
    assert_state(master_bedroom_motion_sensor_state, STATE_ON)

    second_floor_motion_sensor_state = hass.states.get(
        second_floor_aggregate_sensor_entity_id
    )
    assert_state(second_floor_motion_sensor_state, STATE_ON)

    # Off

    hass.states.async_set(master_bedroom_motion_sensor_id, STATE_OFF)
    await hass.async_block_till_done()

    master_bedroom_motion_sensor_state = hass.states.get(
        master_bedroom_motion_sensor_id
    )
    assert_state(master_bedroom_motion_sensor_state, STATE_OFF)

    second_floor_motion_sensor_state = hass.states.get(
        second_floor_aggregate_sensor_entity_id
    )
    assert_state(second_floor_motion_sensor_state, STATE_OFF)

    # Exterior + Ground Level
    backyard_motion_sensor_id = entities_binary_sensor_motion_all_areas_with_meta[
        MockAreaIds.BACKYARD
    ][0].entity_id

    # > On

    hass.states.async_set(backyard_motion_sensor_id, STATE_ON)
    await hass.async_block_till_done()

    backyard_motion_sensor_state = hass.states.get(backyard_motion_sensor_id)
    assert_state(backyard_motion_sensor_state, STATE_ON)

    ground_level_motion_sensor_state = hass.states.get(
        ground_level_aggregate_sensor_entity_id
    )
    assert_state(ground_level_motion_sensor_state, STATE_ON)

    exterior_motion_sensor_state = hass.states.get(exterior_aggregate_sensor_entity_id)
    assert_state(exterior_motion_sensor_state, STATE_ON)

    # > Off

    hass.states.async_set(backyard_motion_sensor_id, STATE_OFF)
    await hass.async_block_till_done()

    backyard_motion_sensor_state = hass.states.get(backyard_motion_sensor_id)
    assert_state(backyard_motion_sensor_state, STATE_OFF)

    ground_level_motion_sensor_state = hass.states.get(
        ground_level_aggregate_sensor_entity_id
    )
    assert_state(ground_level_motion_sensor_state, STATE_OFF)

    exterior_motion_sensor_state = hass.states.get(exterior_aggregate_sensor_entity_id)
    assert_state(exterior_motion_sensor_state, STATE_OFF)
