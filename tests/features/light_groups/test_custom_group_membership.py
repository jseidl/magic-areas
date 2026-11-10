"""Tests for which lights a custom light group contains."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN, AreaStates
from custom_components.magic_areas.const.light_groups import (
    LightGroupEntryOptions,
    LightGroupOptions,
    LightGroupTurnOffWhen,
    LightGroupTurnOnWhen,
)

from tests.const import DEFAULT_MOCK_AREA, MockAreaIds
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockLight

OTHER_AREA = MockAreaIds.LIVING_ROOM
GROUP_ID = f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_test_group"
LIGHT_NAMES = ["light_1", "light_2", "light_3"]
CONFIGURED_LIGHTS = [f"light.{name}" for name in LIGHT_NAMES]


def _config_entry(exclude_entities: list[str]) -> MockConfigEntry:
    """Area config with a custom group listing all three lights."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data["area"]["exclude_entities"] = exclude_entities
    group = {
        LightGroupEntryOptions.NAME.key: "Test Group",
        LightGroupEntryOptions.LIGHTS.key: CONFIGURED_LIGHTS,
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [LightGroupTurnOnWhen.AREA_OCCUPIED],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [LightGroupTurnOffWhen.AREA_CLEAR],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }
    merge_feature_config(
        data, LightGroupOptions.to_config({LightGroupOptions.GROUPS.key: [group]})
    )
    return MockConfigEntry(domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data)


@pytest.mark.parametrize(
    ("other_area_lights", "exclude_entities", "expected_members"),
    [
        pytest.param([], [], CONFIGURED_LIGHTS, id="all_in_area"),
        pytest.param(
            ["light_3"],
            [],
            ["light.light_1", "light.light_2"],
            id="light_in_other_area",
        ),
        pytest.param(
            [],
            ["light.light_3"],
            ["light.light_1", "light.light_2"],
            id="light_excluded",
        ),
    ],
)
async def test_custom_group_contains_only_lights_in_area(
    hass: HomeAssistant,
    other_area_lights: list[str],
    exclude_entities: list[str],
    expected_members: list[str],
) -> None:
    """A custom group's configured lights that aren't in the area are left out."""
    lights = {
        name: MockLight(name=name, state=STATE_OFF, unique_id=name, dimmable=True)
        for name in LIGHT_NAMES
    }
    area_lights = {
        DEFAULT_MOCK_AREA: [
            light for name, light in lights.items() if name not in other_area_lights
        ]
    }
    if other_area_lights:
        area_lights[OTHER_AREA] = [lights[name] for name in other_area_lights]
    await setup_mock_entities(hass, LIGHT_DOMAIN, area_lights)

    config_entry = _config_entry(exclude_entities)
    await init_integration(hass, [config_entry])
    try:
        group_state = hass.states.get(GROUP_ID)
        assert group_state is not None
        assert group_state.attributes[ATTR_ENTITY_ID] == expected_members
    finally:
        await shutdown_integration(hass, [config_entry])
