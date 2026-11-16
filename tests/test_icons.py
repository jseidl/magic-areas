"""Tests for icon translations (icons.json)."""

import inspect
import json
import pathlib

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ICON, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er

import custom_components.magic_areas.const as const_module
from custom_components.magic_areas.const import DOMAIN, MagicAreasFeatureInfo
from custom_components.magic_areas.const.light_groups import (
    LightGroupAllLightsConfig,
    LightGroupCustomConfig,
    LightGroupEntryOptions,
    LightGroupOptions,
)

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockLight

ICONS_FILE = pathlib.Path(const_module.__file__).parent.parent / "icons.json"

AREA_STATE_ID = (
    f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state"
)


def _icons() -> dict:
    with open(ICONS_FILE, encoding="utf-8") as icons_file:
        return json.load(icons_file)["entity"]


def _feature_infos() -> list[type[MagicAreasFeatureInfo]]:
    return [
        cls
        for _, cls in inspect.getmembers(const_module, inspect.isclass)
        if issubclass(cls, MagicAreasFeatureInfo) and cls is not MagicAreasFeatureInfo
    ]


def test_feature_info_has_no_static_icons() -> None:
    """Feature info classes must not hardcode icons anymore."""
    for cls in _feature_infos():
        assert not hasattr(cls, "icons"), f"{cls.__name__} still defines icons"


def test_icons_json_matches_translation_keys() -> None:
    """icons.json only describes known entities, and covers the fixed-icon ones."""
    icons = _icons()
    declared = {
        (domain, key)
        for cls in _feature_infos()
        for domain, key in cls.translation_keys.items()
        if key
    }
    declared |= {
        ("light", LightGroupAllLightsConfig.NAME.value),
        ("light", LightGroupCustomConfig.TRANSLATION_KEY.value),
    }

    for domain, keys in icons.items():
        for key, definition in keys.items():
            assert (domain, key) in declared, f"unknown entity {domain}.{key}"
            assert definition["default"].startswith("mdi:")

    for domain, key in declared:
        if key.startswith(("aggregate", "threshold", "health", "cover_group")):
            continue  # Device-class driven, no fixed icon.
        if key in ("media_player_group", "area_aware_media_player", "fan_group"):
            continue  # Use the device/domain default icon.
        assert key in icons.get(domain, {}), f"missing icon for {domain}.{key}"


@pytest.fixture(name="light_group_entry")
async def fixture_light_group_entry(hass: HomeAssistant):
    """Set up an area with a custom light group."""
    lights = [MockLight(name="light_1", state=STATE_OFF, unique_id="light_1")]
    await setup_mock_entities(hass, LIGHT_DOMAIN, {DEFAULT_MOCK_AREA: lights})

    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    merge_feature_config(
        data,
        LightGroupOptions.to_config(
            {
                LightGroupOptions.GROUPS.key: [
                    {
                        LightGroupEntryOptions.NAME.key: "Reading Nook",
                        LightGroupEntryOptions.LIGHTS.key: ["light.light_1"],
                    }
                ]
            }
        ),
    )
    config_entry = MockConfigEntry(domain=DOMAIN, data=data)
    await init_integration(hass, [config_entry])
    yield config_entry
    await shutdown_integration(hass, [config_entry])


async def test_custom_light_group_ids_are_stable(
    hass: HomeAssistant, light_group_entry: MockConfigEntry
) -> None:
    """User-defined groups share one translation key but keep name-based ids."""
    _ = light_group_entry
    registry = er.async_get(hass)
    area = DEFAULT_MOCK_AREA.value

    entry = registry.async_get(f"light.magic_areas_light_groups_{area}_reading_nook")
    assert entry is not None
    assert entry.translation_key == LightGroupCustomConfig.TRANSLATION_KEY.value
    assert entry.unique_id == f"magic_areas_light_groups_light_{area}_reading_nook"

    all_lights = registry.async_get(f"light.magic_areas_light_groups_{area}_all_lights")
    assert all_lights is not None
    assert all_lights.translation_key == LightGroupAllLightsConfig.NAME.value


async def test_presence_sensor_uses_icons_json_default(hass: HomeAssistant) -> None:
    """Without an area icon the entity has no _attr_icon (icons.json applies)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    )
    await init_integration(hass, [config_entry])

    state = hass.states.get(AREA_STATE_ID)
    assert state is not None
    assert ATTR_ICON not in state.attributes

    registry_entry = er.async_get(hass).async_get(AREA_STATE_ID)
    assert registry_entry is not None
    assert registry_entry.translation_key == "area_state"
    await shutdown_integration(hass, [config_entry])


async def test_presence_sensor_area_icon_override(hass: HomeAssistant) -> None:
    """The area's own icon overrides the icons.json default."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    )
    area_registry = ar.async_get(hass)
    area_registry.async_create(name=DEFAULT_MOCK_AREA.value, icon="mdi:sofa")

    await init_integration(hass, [config_entry])

    state = hass.states.get(AREA_STATE_ID)
    assert state is not None
    assert state.attributes[ATTR_ICON] == "mdi:sofa"
    await shutdown_integration(hass, [config_entry])
