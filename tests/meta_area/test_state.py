"""Test for meta area changes and how the system handles it."""

import logging

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sun.const import STATE_ABOVE_HORIZON
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.base.magic import MagicMetaArea
from custom_components.magic_areas.const import (
    DOMAIN,
    AreaStates,
    CommonAttributes,
    ConfigDomains,
)
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions
from custom_components.magic_areas.const.user_defined_states import (
    UserDefinedStateEntryOptions,
    UserDefinedStateOptions,
)

from tests.const import MockAreaIds
from tests.helpers import (
    assert_in_attribute,
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    safe_set_state,
    setup_mock_entities,
    shutdown_integration,
    trigger_occupancy,
)
from tests.mocks import MockBinarySensor

_LOGGER = logging.getLogger(__name__)


# Tests


async def test_meta_area_primary_state_change(
    hass: HomeAssistant,
    entities_binary_sensor_motion_all_areas_with_meta: dict[
        MockAreaIds, list[MockBinarySensor]
    ],
    _setup_integration_all_areas_with_meta,
) -> None:
    """Test primary state changes between meta areas."""

    # Test initialization
    for (
        area_id,
        entity_list,
    ) in entities_binary_sensor_motion_all_areas_with_meta.items():
        assert entity_list is not None
        assert len(entity_list) == 1

        entity_ids = [entity.entity_id for entity in entity_list]

        # Check area sensor is created
        area_sensor_entity_id = (
            f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{area_id}_area_state"
        )
        area_binary_sensor = hass.states.get(area_sensor_entity_id)
        assert area_binary_sensor is not None
        assert area_binary_sensor.state == STATE_OFF
        assert set(entity_ids).issubset(
            set(area_binary_sensor.attributes["presence_sensors"])
        )
        assert AreaStates.CLEAR in area_binary_sensor.attributes["states"]

    # Entity Ids
    kitchen_area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{MockAreaIds.KITCHEN.value}_area_state"
    backyard_area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{MockAreaIds.BACKYARD.value}_area_state"
    master_bedroom_area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{MockAreaIds.MASTER_BEDROOM.value}_area_state"
    interior_area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{MockAreaIds.INTERIOR.value}_area_state"
    exterior_area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{MockAreaIds.EXTERIOR.value}_area_state"
    global_area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{MockAreaIds.GLOBAL.value}_area_state"
    ground_level_area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{MockAreaIds.GROUND_LEVEL.value}_area_state"
    first_floor_area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{MockAreaIds.FIRST_FLOOR.value}_area_state"
    second_floor_area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{MockAreaIds.SECOND_FLOOR.value}_area_state"

    # Toggle interior area and check interior meta area
    kitchen_motion_sensor_id = entities_binary_sensor_motion_all_areas_with_meta[
        MockAreaIds.KITCHEN
    ][0].entity_id

    await trigger_occupancy(hass, kitchen_motion_sensor_id, occupied=True)

    kitchen_motion_sensor_state = hass.states.get(kitchen_motion_sensor_id)
    assert_state(kitchen_motion_sensor_state, STATE_ON)

    kitchen_area_sensor_state = hass.states.get(kitchen_area_sensor_entity_id)
    assert_state(kitchen_area_sensor_state, STATE_ON)

    interior_area_sensor_state = hass.states.get(interior_area_sensor_entity_id)
    assert_state(interior_area_sensor_state, STATE_ON)

    exterior_area_sensor_state = hass.states.get(exterior_area_sensor_entity_id)
    assert_state(exterior_area_sensor_state, STATE_OFF)

    global_area_sensor_state = hass.states.get(global_area_sensor_entity_id)
    assert_state(global_area_sensor_state, STATE_ON)

    await trigger_occupancy(hass, kitchen_motion_sensor_id, occupied=False)

    kitchen_motion_sensor_state = hass.states.get(kitchen_motion_sensor_id)
    assert_state(kitchen_motion_sensor_state, STATE_OFF)

    kitchen_area_sensor_state = hass.states.get(kitchen_area_sensor_entity_id)
    assert_state(kitchen_area_sensor_state, STATE_OFF)

    interior_area_sensor_state = hass.states.get(interior_area_sensor_entity_id)
    assert_state(interior_area_sensor_state, STATE_OFF)

    exterior_area_sensor_state = hass.states.get(exterior_area_sensor_entity_id)
    assert_state(exterior_area_sensor_state, STATE_OFF)

    global_area_sensor_state = hass.states.get(global_area_sensor_entity_id)
    assert_state(global_area_sensor_state, STATE_OFF)

    # Toggle exterior area
    backyard_motion_sensor_id = entities_binary_sensor_motion_all_areas_with_meta[
        MockAreaIds.BACKYARD
    ][0].entity_id

    await trigger_occupancy(hass, backyard_motion_sensor_id, occupied=True)

    backyard_motion_sensor_state = hass.states.get(backyard_motion_sensor_id)
    assert_state(backyard_motion_sensor_state, STATE_ON)

    backyard_area_sensor_state = hass.states.get(backyard_area_sensor_entity_id)
    assert_state(backyard_area_sensor_state, STATE_ON)

    interior_area_sensor_state = hass.states.get(interior_area_sensor_entity_id)
    assert_state(interior_area_sensor_state, STATE_OFF)

    exterior_area_sensor_state = hass.states.get(exterior_area_sensor_entity_id)
    assert_state(exterior_area_sensor_state, STATE_ON)

    global_area_sensor_state = hass.states.get(global_area_sensor_entity_id)
    assert_state(global_area_sensor_state, STATE_ON)

    await trigger_occupancy(hass, backyard_motion_sensor_id, occupied=False)

    backyard_motion_sensor_state = hass.states.get(kitchen_motion_sensor_id)
    assert_state(backyard_motion_sensor_state, STATE_OFF)

    backyard_area_sensor_state = hass.states.get(backyard_area_sensor_entity_id)
    assert_state(backyard_area_sensor_state, STATE_OFF)

    interior_area_sensor_state = hass.states.get(interior_area_sensor_entity_id)
    assert_state(interior_area_sensor_state, STATE_OFF)

    exterior_area_sensor_state = hass.states.get(exterior_area_sensor_entity_id)
    assert_state(exterior_area_sensor_state, STATE_OFF)

    global_area_sensor_state = hass.states.get(global_area_sensor_entity_id)
    assert_state(global_area_sensor_state, STATE_OFF)

    # Floors
    ground_level_area_sensor_state = hass.states.get(ground_level_area_sensor_entity_id)
    assert_state(ground_level_area_sensor_state, STATE_OFF)

    await trigger_occupancy(hass, backyard_motion_sensor_id, occupied=True)

    ground_level_area_sensor_state = hass.states.get(ground_level_area_sensor_entity_id)
    assert_state(ground_level_area_sensor_state, STATE_ON)

    await trigger_occupancy(hass, backyard_motion_sensor_id, occupied=False)

    ground_level_area_sensor_state = hass.states.get(ground_level_area_sensor_entity_id)
    assert_state(ground_level_area_sensor_state, STATE_OFF)

    first_floor_area_sensor_state = hass.states.get(first_floor_area_sensor_entity_id)
    assert_state(first_floor_area_sensor_state, STATE_OFF)

    await trigger_occupancy(hass, kitchen_motion_sensor_id, occupied=True)

    first_floor_area_sensor_state = hass.states.get(first_floor_area_sensor_entity_id)
    assert_state(first_floor_area_sensor_state, STATE_ON)

    await trigger_occupancy(hass, kitchen_motion_sensor_id, occupied=False)

    first_floor_area_sensor_state = hass.states.get(first_floor_area_sensor_entity_id)
    assert_state(first_floor_area_sensor_state, STATE_OFF)

    second_floor_area_sensor_state = hass.states.get(second_floor_area_sensor_entity_id)
    assert_state(second_floor_area_sensor_state, STATE_OFF)

    await trigger_occupancy(hass, master_bedroom_area_sensor_entity_id, occupied=True)

    second_floor_area_sensor_state = hass.states.get(second_floor_area_sensor_entity_id)
    assert_state(second_floor_area_sensor_state, STATE_ON)

    await trigger_occupancy(hass, master_bedroom_area_sensor_entity_id, occupied=False)

    second_floor_area_sensor_state = hass.states.get(second_floor_area_sensor_entity_id)
    assert_state(second_floor_area_sensor_state, STATE_OFF)


# Meta area secondary state calculation

CHILD_AREAS = [MockAreaIds.KITCHEN, MockAreaIds.LIVING_ROOM, MockAreaIds.DINING_ROOM]
INTERIOR_SENSOR_ID = (
    f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_"
    f"{MockAreaIds.INTERIOR.value}_area_state"
)
KITCHEN_SENSOR_ID = (
    f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_"
    f"{MockAreaIds.KITCHEN.value}_area_state"
)

# Whether the meta area gains the state with 0, 1, 2 and 3 of its 3 child areas
# in that state, for each calculation mode.
EXPECTED_BY_MODE = {
    "any": [False, True, True, True],
    "all": [False, False, False, True],
    "majority": [False, False, True, True],
}


async def _setup_interior_with_children(
    hass: HomeAssistant, mode: str, kind: str
) -> tuple[list[MockConfigEntry], list[MockBinarySensor]]:
    """Set up three interior areas and the interior meta area.

    Each child area gets one sensor that drives either its sleep state or a
    user-defined state called "Movie Time" (kind is "sleep" or "movie_time").
    """
    sensors = {
        area: MockBinarySensor(
            name=f"{kind}_sensor_{area.value}",
            unique_id=f"{kind}_sensor_{area.value}",
            device_class=None,
        )
        for area in CHILD_AREAS
    }
    await setup_mock_entities(
        hass,
        BINARY_SENSOR_DOMAIN,
        {area: [sensor] for area, sensor in sensors.items()},
    )

    entries: list[MockConfigEntry] = []
    for area, sensor in sensors.items():
        data = get_basic_config_entry_data(area)
        if kind == "sleep":
            data.update(
                SecondaryStateOptions.to_config(
                    {SecondaryStateOptions.SLEEP_ENTITY.key: sensor.entity_id}
                )
            )
        else:
            data[ConfigDomains.USER_DEFINED_STATES.value] = {
                UserDefinedStateOptions.STATES.key: [
                    {
                        UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                        UserDefinedStateEntryOptions.ENTITY.key: sensor.entity_id,
                    }
                ]
            }
        entries.append(MockConfigEntry(domain=DOMAIN, data=data))

    meta_data = get_basic_config_entry_data(MockAreaIds.INTERIOR)
    meta_data.update(
        SecondaryStateOptions.to_config(
            {SecondaryStateOptions.CALCULATION_MODE.key: mode}
        )
    )
    entries.append(MockConfigEntry(domain=DOMAIN, data=meta_data))

    await init_integration(hass, entries, areas=CHILD_AREAS)
    return entries, list(sensors.values())


# The state as shown in the area's "states" attribute: user-defined states are
# reported by their friendly name, built-in ones by their slug.
STATE_SHOWN_FOR_KIND = {"sleep": "sleep", "movie_time": "Movie Time"}


@pytest.mark.parametrize("kind", ["sleep", "movie_time"])
@pytest.mark.parametrize("mode", list(EXPECTED_BY_MODE))
async def test_meta_area_calculates_secondary_states(
    hass: HomeAssistant, mode: str, kind: str
) -> None:
    """Test each calculation mode decides when the meta area gains a state."""
    entries, sensors = await _setup_interior_with_children(hass, mode, kind)
    try:
        for active_children, expected in enumerate(EXPECTED_BY_MODE[mode]):
            if active_children > 0:
                await safe_set_state(hass, sensors[active_children - 1], True)

            assert_in_attribute(
                hass.states.get(INTERIOR_SENSOR_ID),
                CommonAttributes.STATES.value,
                STATE_SHOWN_FOR_KIND[kind],
                negate=not expected,
            )
    finally:
        await shutdown_integration(hass, entries)


async def test_meta_area_ignores_children_without_a_states_attribute(
    hass: HomeAssistant,
) -> None:
    """Test a child area that reports no states does not count towards the meta area."""
    entries, sensors = await _setup_interior_with_children(hass, "any", "sleep")
    try:
        await safe_set_state(hass, sensors[0], True)
        assert_in_attribute(
            hass.states.get(INTERIOR_SENSOR_ID),
            CommonAttributes.STATES.value,
            "sleep",
        )

        # Replace the kitchen's state with one that has no attributes at all.
        hass.states.async_set(KITCHEN_SENSOR_ID, STATE_OFF)
        await hass.async_block_till_done()

        assert_in_attribute(
            hass.states.get(INTERIOR_SENSOR_ID),
            CommonAttributes.STATES.value,
            "sleep",
            negate=True,
        )
    finally:
        await shutdown_integration(hass, entries)


async def test_meta_area_ignores_children_without_a_state_entity(
    hass: HomeAssistant,
) -> None:
    """Test a child area whose state entity is gone does not count towards the meta area."""
    entries, sensors = await _setup_interior_with_children(hass, "any", "sleep")
    try:
        hass.states.async_remove(KITCHEN_SENSOR_ID)
        await hass.async_block_till_done()

        await safe_set_state(hass, sensors[1], True)

        assert_in_attribute(
            hass.states.get(INTERIOR_SENSOR_ID),
            CommonAttributes.STATES.value,
            "sleep",
        )
    finally:
        await shutdown_integration(hass, entries)


async def test_meta_area_is_bright_when_its_children_are_not_dark(
    hass: HomeAssistant,
) -> None:
    """Test the meta area reports bright once no child area is dark."""
    hass.states.async_set("sun.sun", STATE_ABOVE_HORIZON)
    entries, _ = await _setup_interior_with_children(hass, "any", "sleep")
    try:
        interior_state = hass.states.get(INTERIOR_SENSOR_ID)

        assert_in_attribute(
            interior_state, CommonAttributes.STATES.value, AreaStates.BRIGHT
        )
        assert_in_attribute(
            interior_state, CommonAttributes.STATES.value, AreaStates.DARK, negate=True
        )
    finally:
        await shutdown_integration(hass, entries)


class _UnprintableArea:
    """A child area entry that cannot be turned into an entity id."""

    def __format__(self, format_spec: str) -> str:
        raise ValueError("cannot format")

    def __str__(self) -> str:
        return "unprintable"


async def test_meta_area_active_areas_follow_the_area_entities(
    hass: HomeAssistant,
) -> None:
    """get_active_areas lists the occupied children and skips ones without an entity."""
    entries, _ = await _setup_interior_with_children(hass, "any", "sleep")
    try:
        meta_area = entries[-1].runtime_data
        assert isinstance(meta_area, MagicMetaArea)
        assert meta_area.get_active_areas() == []

        # NOTE: get_active_areas looks children up as binary_sensor.area_<slug>,
        # which is not the id of the area state sensors Magic Areas creates.
        hass.states.async_set("binary_sensor.area_kitchen", STATE_ON)
        hass.states.async_set("binary_sensor.area_living_room", STATE_OFF)
        assert meta_area.get_active_areas() == [MockAreaIds.KITCHEN.value]
    finally:
        await shutdown_integration(hass, entries)


async def test_meta_area_active_areas_survive_a_broken_child(
    hass: HomeAssistant,
) -> None:
    """get_active_areas logs a child it cannot read and carries on with the rest."""
    entries, _ = await _setup_interior_with_children(hass, "any", "sleep")
    try:
        meta_area = entries[-1].runtime_data
        assert isinstance(meta_area, MagicMetaArea)
        hass.states.async_set("binary_sensor.area_kitchen", STATE_ON)
        meta_area.child_areas = [_UnprintableArea(), MockAreaIds.KITCHEN.value]  # type: ignore[list-item]

        assert meta_area.get_active_areas() == [MockAreaIds.KITCHEN.value]
    finally:
        await shutdown_integration(hass, entries)


async def test_meta_area_initialize_is_idempotent(hass: HomeAssistant) -> None:
    """Initializing an already initialized meta-area leaves it as it was."""
    entries, _ = await _setup_interior_with_children(hass, "any", "sleep")
    try:
        meta_area = entries[-1].runtime_data
        assert meta_area.initialized
        entities_before = {
            domain: list(entities) for domain, entities in meta_area.entities.items()
        }

        await meta_area.initialize()

        assert meta_area.entities == entities_before
    finally:
        await shutdown_integration(hass, entries)
