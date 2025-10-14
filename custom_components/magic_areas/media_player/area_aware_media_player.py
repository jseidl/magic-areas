"""Area aware media player, media player component."""

import logging

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_IDLE,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import State

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    CONF_NOTIFICATION_DEVICES,
    DEFAULT_NOTIFICATION_DEVICES,
    DOMAIN,
    MagicAreasFeatureInfoAreaAwareMediaPlayer,
    MagicAreasFeatures,
)

INVALID_STATES = [STATE_UNKNOWN, STATE_UNAVAILABLE]

_LOGGER = logging.getLogger(__name__)

"""
    @TODO
    - Consider removing active_areas attribute and tracked entities?
    - If not, consider scanning initially for the smart media routers and use that instead
    - Ignore notification devices as this is now SMR's work
"""


class AreaAwareMediaPlayer(MagicEntity, MediaPlayerEntity):
    """Area-aware media player."""

    feature_info = MagicAreasFeatureInfoAreaAwareMediaPlayer()

    def __init__(self, area, areas):
        """Initialize area-aware media player."""
        MagicEntity.__init__(self, area, domain=MEDIA_PLAYER_DOMAIN)
        MediaPlayerEntity.__init__(self)

        self._attr_extra_state_attributes = {}
        self._state = STATE_IDLE

        self.areas = areas
        self.area = area
        self._tracked_entities = []

        for area_obj in self.areas:
            entity_list = self.get_media_players_for_area(area_obj)
            if entity_list:
                self._tracked_entities.extend(entity_list)

        _LOGGER.debug("AreaAwareMediaPlayer loaded.")

    def update_attributes(self):
        """Update entity attributes."""
        self._attr_extra_state_attributes["areas"] = [
            f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{area.slug}_area_state"
            for area in self.areas
        ]
        self._attr_extra_state_attributes["entity_id"] = self._tracked_entities

    def get_media_players_for_area(self, area):
        """Return media players for a given area."""
        entity_ids = []

        notification_devices = area.feature_config(
            MagicAreasFeatures.AREA_AWARE_MEDIA_PLAYER
        ).get(CONF_NOTIFICATION_DEVICES, DEFAULT_NOTIFICATION_DEVICES)

        _LOGGER.debug("%s: Notification devices: %s", area.name, notification_devices)

        area_media_players = [
            entity["entity_id"] for entity in area.entities[MEDIA_PLAYER_DOMAIN]
        ]

        # Check if media_player entities are notification devices
        for mp in area_media_players:
            if mp in notification_devices:
                entity_ids.append(mp)

        return set(entity_ids)

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""

        await self.restore_state()
        self.set_state()

    @property
    def state(self):
        """Return the state of the media player."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return (
            MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
        )

    def get_active_areas(self):
        """Return areas that are occupied."""
        active_areas = []

        for area in self.areas:
            area_binary_sensor_name = f"{BINARY_SENSOR_DOMAIN}.{DOMAIN}_presence_tracking_{area.slug}_area_state"
            area_binary_sensor_state = self.hass.states.get(area_binary_sensor_name)

            if not area_binary_sensor_state:
                _LOGGER.debug(
                    "%s: No state found for entity '%s'",
                    self.name,
                    area_binary_sensor_name,
                )
                continue

            # Ignore not occupied areas
            if area_binary_sensor_state.state != STATE_ON:
                continue

            active_areas.append(area)

        return active_areas

    def update_state(self):
        """Update entity state and attributes."""
        self.update_attributes()
        self.schedule_update_ha_state()

    def set_state(self, state=None):
        """Set the entity state."""
        if state:
            self._state = state
        self.update_state()

    async def async_play_media(self, media_type, media_id, **kwargs) -> None:
        """Forward a piece of media to appropriate devices in active areas."""

        # Read active areas
        active_areas: list[MagicArea] = self.get_active_areas()

        # Fail early
        if not active_areas:
            _LOGGER.debug("No areas active. Ignoring.")
            return

        # Find Smart Media Routers for each area
        target_routers: list[str] = []

        for area in active_areas:
            if not area.has_feature(MagicAreasFeatures.SMART_MEDIA_ROUTER):
                continue

            router_eid: str = f"{MEDIA_PLAYER_DOMAIN}.{DOMAIN}_{MagicAreasFeatures.SMART_MEDIA_ROUTER}_{area.slug}"

            router_state: State | None = self.hass.states.get(router_eid)

            if not router_state:
                continue

            if router_state.state in INVALID_STATES:
                continue

            target_routers.append(router_state.entity_id)

        if target_routers:
            # Use traditional media_player service
            data = {
                ATTR_MEDIA_CONTENT_ID: media_id,
                ATTR_MEDIA_CONTENT_TYPE: media_type,
                ATTR_ENTITY_ID: target_routers,
            }
            if kwargs:
                data.update(kwargs)

            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA, data
            )
