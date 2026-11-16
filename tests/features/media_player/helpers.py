"""Shared constants and helpers for the media player feature tests."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN

from custom_components.magic_areas.const import DOMAIN

from tests.const import DEFAULT_MOCK_AREA, MockAreaIds
from tests.helpers import get_basic_config_entry_data, merge_feature_config

SLUG = DEFAULT_MOCK_AREA.value

GROUP_ID = (
    f"{MEDIA_PLAYER_DOMAIN}.magic_areas_media_player_groups_{SLUG}_media_player_group"
)

AREA_STATE_ID = (
    f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{SLUG}_area_state"
)


def make_entry(
    area: MockAreaIds, *feature_configs: dict, features=()
) -> MockConfigEntry:
    """Build a config entry with the given features enabled."""
    data = get_basic_config_entry_data(area)
    merge_feature_config(data, *feature_configs)
    for feature in features:
        data["features"].setdefault(feature, {})
    return MockConfigEntry(domain=DOMAIN, data=data)
