"""Test for the logic on automatically reloading areas."""

import asyncio
from datetime import datetime
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import (
    EVENT_ENTITY_REGISTRY_UPDATED,
    _EventEntityRegistryUpdatedData_CreateRemove,
    _EventEntityRegistryUpdatedData_Update,
)

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    DATA_AREA_OBJECT,
    MODULE_DATA,
    MetaAreaAutoReloadSettings,
)

from tests.const import MockAreaIds
from tests.mocks import MockBinarySensor

# Total time to wait for the full reload cascade to complete:
# regular area (DELAY) → non-global meta-areas (DELAY) → global (GLOBAL_DELAY)
# In practice the debounce windows overlap, so GLOBAL_DELAY covers the full chain.
_CASCADE_WAIT = MetaAreaAutoReloadSettings.GLOBAL_DELAY + 1

_LOGGER = logging.getLogger(__name__)

# Constants

NORMAL_AREAS = [
    MockAreaIds.KITCHEN.value,
    MockAreaIds.BACKYARD.value,
    MockAreaIds.MASTER_BEDROOM.value,
]
REGULAR_META_AREAS = [
    MockAreaIds.GLOBAL.value,
    MockAreaIds.INTERIOR.value,
    MockAreaIds.EXTERIOR.value,
]
FLOOR_META_AREAS = [
    MockAreaIds.GROUND_LEVEL.value,
    MockAreaIds.FIRST_FLOOR.value,
    MockAreaIds.SECOND_FLOOR.value,
]
ALL_AREAS = NORMAL_AREAS + REGULAR_META_AREAS + FLOOR_META_AREAS

# Helpers


def get_config_entry_by_area_name(hass: HomeAssistant, area_name: str) -> str | None:
    """Fetch config_entry_id from an area's name."""
    ma_data = hass.data[MODULE_DATA]
    for entry_id, entry_data in ma_data.items():
        area_data = entry_data[DATA_AREA_OBJECT]
        if area_data.id == area_name.lower():
            return entry_id

    return None


def get_entry_by_area_name(hass: HomeAssistant, area_name: str) -> MagicArea | None:
    """Fetch MagicArea object from an area's name."""
    config_entry_id = get_config_entry_by_area_name(hass, area_name)
    if not config_entry_id:
        return None

    ma_data = hass.data[MODULE_DATA]

    if config_entry_id not in ma_data:
        return None

    return ma_data[config_entry_id][DATA_AREA_OBJECT]


# Tests


async def test_reload_on_entity_area_change(
    hass: HomeAssistant,
    entities_binary_sensor_motion_all_areas_with_meta: dict[
        MockAreaIds, list[MockBinarySensor]
    ],
    _setup_integration_all_areas_with_meta,
) -> None:
    """Test that only corresponding areas reload when an entity changes state."""

    # Check all areas' timestamp
    area_timestamp_map: dict[str, datetime] = {}
    for area in NORMAL_AREAS:
        area_object = get_entry_by_area_name(hass, area)
        assert area_object
        area_timestamp_map[area] = area_object.timestamp

    # Simulate entity changing area_id (this triggers "all areas reload" logic in MagicArea)
    event_data: _EventEntityRegistryUpdatedData_Update = {
        "action": "update",
        "entity_id": "sensor.test",
        "changes": {"area_id": MockAreaIds.KITCHEN.value},
    }
    hass.bus.async_fire(EVENT_ENTITY_REGISTRY_UPDATED, event_data)
    await hass.async_block_till_done()

    # Sleep so we handle the reload delay
    await asyncio.sleep(_CASCADE_WAIT)

    # Check all areas' timestamp against the previous map
    for area in NORMAL_AREAS:
        area_object = get_entry_by_area_name(hass, area)
        assert area_object
        if area == MockAreaIds.KITCHEN.value:
            assert area_timestamp_map[area] != area_object.timestamp
        else:
            assert area_timestamp_map[area] == area_object.timestamp


async def test_meta_reload_from_single_reload(
    hass: HomeAssistant,
    entities_binary_sensor_motion_all_areas_with_meta: dict[
        MockAreaIds, list[MockBinarySensor]
    ],
    _setup_integration_all_areas_with_meta,
) -> None:
    """Test that the corresponding meta-areas reload when a child area reloads."""

    # Check all areas' timestamp
    area_timestamp_map: dict[str, datetime] = {}
    for area in ALL_AREAS:
        area_object = get_entry_by_area_name(hass, area)
        assert area_object
        area_timestamp_map[area] = area_object.timestamp

    # Simulate entity changing area_id (this triggers "all areas reload" logic in MagicArea)
    kitchen_motion_sensor_id = entities_binary_sensor_motion_all_areas_with_meta[
        MockAreaIds.KITCHEN
    ][0].entity_id

    event_data: _EventEntityRegistryUpdatedData_CreateRemove = {
        "action": "remove",
        "entity_id": kitchen_motion_sensor_id,
    }
    hass.bus.async_fire(EVENT_ENTITY_REGISTRY_UPDATED, event_data)
    await hass.async_block_till_done()

    def _assert_has_reloaded(area_name: str):
        area_object = get_entry_by_area_name(hass, area_name)
        assert area_object
        assert area_object.timestamp != area_timestamp_map[area_name]

    def _assert_has_not_reloaded(area_name: str):
        area_object = get_entry_by_area_name(hass, area_name)
        assert area_object
        assert area_object.timestamp == area_timestamp_map[area_name]

    # Sleep so we handle the full reload cascade (regular → non-global meta → global)
    await asyncio.sleep(_CASCADE_WAIT)

    # Check corresponding area reloaded
    _assert_has_reloaded(MockAreaIds.KITCHEN.value)

    # Check corresponding meta-areas reloaded
    _assert_has_reloaded(MockAreaIds.INTERIOR.value)
    _assert_has_reloaded(MockAreaIds.GLOBAL.value)
    _assert_has_reloaded(MockAreaIds.FIRST_FLOOR.value)

    # Check other areas didn't reload
    _assert_has_not_reloaded(MockAreaIds.MASTER_BEDROOM.value)
    _assert_has_not_reloaded(MockAreaIds.BACKYARD.value)
    _assert_has_not_reloaded(MockAreaIds.EXTERIOR.value)
    _assert_has_not_reloaded(MockAreaIds.SECOND_FLOOR.value)
    _assert_has_not_reloaded(MockAreaIds.GROUND_LEVEL.value)
