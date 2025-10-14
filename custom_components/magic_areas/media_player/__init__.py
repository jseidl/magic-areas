"""Platform file for Magic Area's media_player entities."""

import logging

from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    CONF_FEATURE_AREA_AWARE_MEDIA_PLAYER,
    CONF_FEATURE_MEDIA_PLAYER_GROUPS,
    CONF_NOTIFICATION_DEVICES,
    DATA_AREA_OBJECT,
    META_AREA_GLOBAL,
    MODULE_DATA,
)
from custom_components.magic_areas.helpers.area import get_area_from_config_entry
from custom_components.magic_areas.media_player.area_aware_media_player import (
    AreaAwareMediaPlayer,
)
from custom_components.magic_areas.media_player.media_player_group import (
    AreaMediaPlayerGroup,
)
from custom_components.magic_areas.util import cleanup_removed_entries

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the area media player config entry."""

    area: MagicArea | None = get_area_from_config_entry(hass, config_entry)
    assert area is not None

    entities_to_add: list[AreaAwareMediaPlayer | AreaMediaPlayerGroup] = []

    # Media Player Groups
    if area.has_feature(CONF_FEATURE_MEDIA_PLAYER_GROUPS):
        _LOGGER.debug("%s: Setting up media player groups.", area.name)
        entities_to_add.extend(setup_media_player_group(area))

    # Check if we are the Global Meta Area
    if area.is_meta() and area.id == META_AREA_GLOBAL.lower():
        # Try to setup AAMP
        _LOGGER.debug("%s: Setting up Area-Aware media player", area.name)
        entities_to_add.extend(setup_area_aware_media_player(area))

    if entities_to_add:
        async_add_entities(entities_to_add)

    if MEDIA_PLAYER_DOMAIN in area.magic_entities:
        cleanup_removed_entries(
            area.hass, entities_to_add, area.magic_entities[MEDIA_PLAYER_DOMAIN]
        )


def setup_media_player_group(area):
    """Create the media player groups."""
    # Check if there are any media player devices
    if not area.has_entities(MEDIA_PLAYER_DOMAIN):
        _LOGGER.debug("%s: No %s entities.", area.name, MEDIA_PLAYER_DOMAIN)
        return []

    media_player_entities = [e["entity_id"] for e in area.entities[MEDIA_PLAYER_DOMAIN]]

    return [AreaMediaPlayerGroup(area, media_player_entities)]


def setup_area_aware_media_player(area):
    """Create Area-aware media player."""
    ma_data = area.hass.data[MODULE_DATA]

    # Check if we have areas with MEDIA_PLAYER_DOMAIN entities
    areas_with_media_players = []

    for entry in ma_data.values():
        current_area = entry[DATA_AREA_OBJECT]

        # Skip meta areas
        if current_area.is_meta():
            _LOGGER.debug("%s: Is meta-area, skipping.", current_area.name)
            continue

        # Skip areas with feature not enabled
        if not current_area.has_feature(CONF_FEATURE_AREA_AWARE_MEDIA_PLAYER):
            _LOGGER.debug(
                "%s: Does not have Area-aware media player feature enabled, skipping.",
                current_area.name,
            )
            continue

        # Skip areas without media player entities
        if not current_area.has_entities(MEDIA_PLAYER_DOMAIN):
            _LOGGER.debug(
                "%s: Has no media player entities, skipping.", current_area.name
            )
            continue

        # Skip areas without notification devices set
        notification_devices = current_area.feature_config(
            CONF_FEATURE_AREA_AWARE_MEDIA_PLAYER
        ).get(CONF_NOTIFICATION_DEVICES)

        if not notification_devices:
            _LOGGER.debug(
                "%s: Has no notification devices, skipping.", current_area.name
            )
            continue

        # If all passes, we add this valid area to the list
        areas_with_media_players.append(current_area)

    if not areas_with_media_players:
        _LOGGER.debug(
            "No areas with %s entities. Skipping creation of area-aware-media-player",
            MEDIA_PLAYER_DOMAIN,
        )
        return []

    area_names = [i.name for i in areas_with_media_players]

    _LOGGER.debug(
        "%s: Setting up area-aware media player with areas: %s", area.name, area_names
    )

    return [AreaAwareMediaPlayer(area, areas_with_media_players)]
