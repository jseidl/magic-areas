"""Tests for floor meta-areas: following area floor changes, and reserved floor ids."""

from typing import Any
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    floor_registry as fr,
    issue_registry as ir,
)

from custom_components.magic_areas.base.magic import MagicArea, MagicMetaArea
from custom_components.magic_areas.const import (
    CONF_AREA_ID,
    DOMAIN,
    ISSUE_RESERVED_FLOOR_ID,
)

from tests.const import MockAreaIds, MockFloorIds
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    shutdown_integration,
)

AREA = MockAreaIds.KITCHEN  # on MockFloorIds.FIRST_FLOOR
OLD_FLOOR_META = MockAreaIds.FIRST_FLOOR
NEW_FLOOR_META = MockAreaIds.SECOND_FLOOR

RESERVED_FLOOR_ISSUE = f"{ISSUE_RESERVED_FLOOR_ID}_exterior"


def _config_entry(area: MockAreaIds) -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, data=get_basic_config_entry_data(area))


def _magic_area(hass: HomeAssistant, config_entry: MockConfigEntry) -> Any:
    return config_entry.runtime_data


async def _setup_area_and_floor_metas(
    hass: HomeAssistant,
) -> dict[MockAreaIds, MockConfigEntry]:
    # init_integration only creates floors that its areas are on.
    fr.async_get(hass).async_create(MockFloorIds.SECOND_FLOOR.value)

    config_entries = {
        area: _config_entry(area) for area in (AREA, OLD_FLOOR_META, NEW_FLOOR_META)
    }
    await init_integration(hass, list(config_entries.values()), areas=[AREA])
    return config_entries


async def test_area_floor_change_reloads_area(hass: HomeAssistant) -> None:
    """Moving an area to another floor reloads it, so floors see the move."""
    config_entries = await _setup_area_and_floor_metas(hass)
    try:
        area: MagicArea = _magic_area(hass, config_entries[AREA])
        old_meta: MagicMetaArea = _magic_area(hass, config_entries[OLD_FLOOR_META])
        new_meta: MagicMetaArea = _magic_area(hass, config_entries[NEW_FLOOR_META])
        assert area.floor_id == MockFloorIds.FIRST_FLOOR.value
        assert AREA.value in old_meta.get_child_areas()
        assert AREA.value not in new_meta.get_child_areas()

        ar.async_get(hass).async_update(
            AREA.value, floor_id=MockFloorIds.SECOND_FLOOR.value
        )
        await hass.async_block_till_done()

        reloaded_area: MagicArea = _magic_area(hass, config_entries[AREA])
        assert reloaded_area is not area
        assert reloaded_area.floor_id == MockFloorIds.SECOND_FLOOR.value
        assert AREA.value in new_meta.get_child_areas()
        assert AREA.value not in old_meta.get_child_areas()
    finally:
        await shutdown_integration(hass, list(config_entries.values()))


async def test_floor_meta_reloads_when_area_joins_its_floor(
    hass: HomeAssistant,
) -> None:
    """A floor meta-area reloads when an area that isn't a child yet reports its floor."""
    config_entries = await _setup_area_and_floor_metas(hass)
    try:
        new_meta: MagicMetaArea = _magic_area(hass, config_entries[NEW_FLOOR_META])
        assert AREA.value not in new_meta.child_areas

        # pylint: disable=protected-access
        with patch.object(new_meta, "_delayed_reload", AsyncMock()) as reload:
            # Another floor: not ours, and not a child.
            await new_meta._handle_loaded_area(
                "interior", MockFloorIds.FIRST_FLOOR.value, AREA.value
            )
            await hass.async_block_till_done()
            reload.assert_not_awaited()

            # Our floor: the area has just moved here.
            await new_meta._handle_loaded_area(
                "interior", MockFloorIds.SECOND_FLOOR.value, AREA.value
            )
            await hass.async_block_till_done()
            reload.assert_awaited_once()
    finally:
        await shutdown_integration(hass, list(config_entries.values()))


async def test_area_update_without_floor_change_does_not_reload(
    hass: HomeAssistant,
) -> None:
    """Area updates that don't change the floor leave the area alone."""
    config_entries = await _setup_area_and_floor_metas(hass)
    try:
        area: MagicArea = _magic_area(hass, config_entries[AREA])

        ar.async_get(hass).async_update(AREA.value, aliases={"Cooking area"})
        await hass.async_block_till_done()

        assert _magic_area(hass, config_entries[AREA]) is area
    finally:
        await shutdown_integration(hass, list(config_entries.values()))


async def test_reserved_floor_id_repair_issue(hass: HomeAssistant) -> None:
    """A floor with a meta-area's id raises a repair issue, cleared when it's gone."""
    floor_registry = fr.async_get(hass)
    issue_registry = ir.async_get(hass)

    # A floor first created as "Exterior" keeps the id "exterior" when renamed.
    floor = floor_registry.async_create("Exterior")
    assert floor.floor_id == "exterior"
    floor_registry.async_update(floor.floor_id, name="Outside")

    config_entry = _config_entry(AREA)
    await init_integration(hass, [config_entry])
    try:
        issue = issue_registry.async_get_issue(DOMAIN, RESERVED_FLOOR_ISSUE)
        assert issue is not None
        assert issue.severity == ir.IssueSeverity.WARNING
        assert not issue.is_fixable
        assert issue.translation_key == ISSUE_RESERVED_FLOOR_ID
        assert issue.translation_placeholders == {
            "floor_name": "Outside",
            "floor_id": "exterior",
            "meta_area": "Exterior",
        }

        # Renaming the floor updates the issue.
        floor_registry.async_update(floor.floor_id, name="Out back")
        await hass.async_block_till_done()
        issue = issue_registry.async_get_issue(DOMAIN, RESERVED_FLOOR_ISSUE)
        assert issue is not None
        assert issue.translation_placeholders
        assert issue.translation_placeholders["floor_name"] == "Out back"

        # Deleting the floor clears it.
        floor_registry.async_delete(floor.floor_id)
        await hass.async_block_till_done()
        assert issue_registry.async_get_issue(DOMAIN, RESERVED_FLOOR_ISSUE) is None
    finally:
        await shutdown_integration(hass, [config_entry])


async def test_no_repair_issue_without_reserved_floor(hass: HomeAssistant) -> None:
    """Ordinary floors don't raise the issue."""
    config_entry = _config_entry(AREA)
    await init_integration(hass, [config_entry])
    try:
        assert not [
            issue_id
            for (domain, issue_id) in ir.async_get(hass).issues
            if domain == DOMAIN
        ]
    finally:
        await shutdown_integration(hass, [config_entry])


async def test_config_flow_skips_reserved_floor(hass: HomeAssistant) -> None:
    """The config flow doesn't offer floors whose id is a meta-area's."""
    floor_registry = fr.async_get(hass)
    reserved = floor_registry.async_create("Exterior")
    floor_registry.async_update(reserved.floor_id, name="Outside")
    floor_registry.async_create("Outbuildings")

    config_entry = _config_entry(AREA)
    await init_integration(hass, [config_entry])
    try:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == "form"
        choices = result["data_schema"].schema[CONF_AREA_ID].container

        assert choices["outbuildings"] == "(Meta) Outbuildings"
        assert "(Meta) Outside" not in choices.values()
        assert choices["exterior"] == "(Meta) Exterior"  # the built-in meta-area

        hass.config_entries.flow.async_abort(result["flow_id"])
    finally:
        await shutdown_integration(hass, [config_entry])
