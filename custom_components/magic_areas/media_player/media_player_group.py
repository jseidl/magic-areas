"""Media player groups component."""

import logging

from custom_components.magic_areas.base.entities import MagicEntity
from homeassistant.components.group.media_player import MediaPlayerGroup

from custom_components.magic_areas.const import (
    MagicAreasFeatureInfoMediaPlayerGroups,
    EMPTY_STRING,
    MEDIA_PLAYER_DOMAIN,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)

# Classes


class AreaMediaPlayerGroup(MagicEntity, MediaPlayerGroup):
    """Media player group."""

    feature_info = MagicAreasFeatureInfoMediaPlayerGroups()

    def __init__(self, area, entities):
        """Initialize media player group."""
        MagicEntity.__init__(self, area, domain=MEDIA_PLAYER_DOMAIN)
        MediaPlayerGroup.__init__(
            self,
            name=EMPTY_STRING,
            unique_id=self._attr_unique_id,
            entities=entities,
        )
