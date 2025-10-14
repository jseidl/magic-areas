"""Area aware media player, media player component."""

import logging

from homeassistant.components.assist_satellite.const import (
    DOMAIN as ASSIST_SATELLITE_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_IDLE, STATE_ON

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.const import (
    CONF_NOTIFICATION_DEVICES,
    CONF_NOTIFY_STATES,
    CONF_ROUTE_NOTIFICATIONS_TO_SATELLITES,
    DEFAULT_NOTIFICATION_DEVICES,
    DEFAULT_NOTIFY_STATES,
    DEFAULT_ROUTE_NOTIFICATIONS_TO_SATELLITES,
    AreaStates,
    MagicAreasFeatureInfoAreaAwareMediaPlayer,
    MagicAreasFeatures,
)

_LOGGER = logging.getLogger(__name__)


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

    def get_assist_satellites_for_area(self, area):
        """Return assist satellites for a given area."""
        if not area.has_entities(ASSIST_SATELLITE_DOMAIN):
            return set()

        entity_ids = [
            entity["entity_id"] for entity in area.entities[ASSIST_SATELLITE_DOMAIN]
        ]

        _LOGGER.debug("%s: Found assist satellites: %s", area.name, entity_ids)
        return set(entity_ids)

    def should_route_notifications_to_satellites(self, area):
        """Check if notifications should be routed to satellites for this area."""
        return area.feature_config(MagicAreasFeatures.AREA_AWARE_MEDIA_PLAYER).get(
            CONF_ROUTE_NOTIFICATIONS_TO_SATELLITES,
            DEFAULT_ROUTE_NOTIFICATIONS_TO_SATELLITES,
        )

    def get_target_devices_for_content(self, area, content_type="media"):
        """Get target devices based on content type and satellite routing setting."""
        route_notifications_to_satellites = (
            self.should_route_notifications_to_satellites(area)
        )
        media_players = self.get_media_players_for_area(area)
        assist_satellites = self.get_assist_satellites_for_area(area)

        _LOGGER.debug(
            "%s: Route notifications to satellites='%s', content_type='%s', media_players=%s, satellites=%s",
            area.name,
            route_notifications_to_satellites,
            content_type,
            media_players,
            assist_satellites,
        )

        # Simple routing logic
        if route_notifications_to_satellites and content_type == "notification":
            # Route notifications to satellites, fallback to media players
            return assist_satellites or media_players

        # Route everything else to media players
        return media_players

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""

        last_state = await self.async_get_last_state()

        if last_state:
            _LOGGER.debug(
                "%s: Nedia Player restored [state=%s]", self.name, last_state.state
            )
            self._state = last_state.state
        else:
            self._state = STATE_IDLE

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
            area_binary_sensor_name = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{area.slug}_area_state"
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

            # Check notification states
            notification_states = area.feature_config(
                MagicAreasFeatures.AREA_AWARE_MEDIA_PLAYER
            ).get(CONF_NOTIFY_STATES, DEFAULT_NOTIFY_STATES)

            # Check sleep
            if area.has_state(AreaStates.SLEEP) and (
                AreaStates.SLEEP not in notification_states
            ):
                continue

            # Check other states
            has_valid_state = False
            for notification_state in notification_states:
                if area.has_state(notification_state):
                    has_valid_state = True

            # Append area
            if has_valid_state:
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
        active_areas = self.get_active_areas()

        # Fail early
        if not active_areas:
            _LOGGER.debug("No areas active. Ignoring.")
            return

        # Determine content type for routing decisions
        content_type = (
            "notification"
            if self._is_notification_content(media_type, media_id)
            else "media"
        )

        # Gather target devices based on routing strategy
        target_devices = []
        assist_satellites = []
        media_players = []

        for area in active_areas:
            devices = self.get_target_devices_for_content(area, content_type)
            target_devices.extend(devices)

            # Separate satellites from media players for appropriate service calls
            for device in devices:
                if device.startswith(ASSIST_SATELLITE_DOMAIN):
                    assist_satellites.append(device)
                else:
                    media_players.append(device)

        if not target_devices:
            _LOGGER.debug(
                "%s: No target devices found for content_type='%s'. Ignoring.",
                self.name,
                content_type,
            )
            return

        # Call appropriate services based on device types
        if assist_satellites:
            # Use assist_satellite announcement service
            await self._announce_to_satellites(assist_satellites, media_id, **kwargs)

        if media_players:
            # Use traditional media_player service
            data = {
                ATTR_MEDIA_CONTENT_ID: media_id,
                ATTR_MEDIA_CONTENT_TYPE: media_type,
                ATTR_ENTITY_ID: media_players,
            }
            if kwargs:
                data.update(kwargs)

            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_PLAY_MEDIA,
                data,
                blocking=True,
                return_response=True,
            )

    def _is_notification_content(self, media_type, media_id):
        """Determine if the content is a notification vs regular media."""
        # Check media_type patterns first
        notification_media_types = [
            "tts",
            "announcement",
            "alert",
        ]

        if any(ntype in media_type.lower() for ntype in notification_media_types):
            return True

        # Check content patterns in media_id
        notification_indicators = [
            "tts",
            "announce",
            "notification",
            "alert",
            "reminder",
            "warning",
            "emergency",
        ]

        return any(
            indicator in media_id.lower() for indicator in notification_indicators
        )

    async def _announce_to_satellites(self, satellites, message, **kwargs):
        """Announce message to assist satellites with improved error handling."""
        successful_announcements = 0

        try:
            # Use the assist_satellite announce service if available
            if self.hass.services.has_service("assist_satellite", "announce"):
                for satellite in satellites:
                    try:
                        await self.hass.services.async_call(
                            "assist_satellite",
                            "announce",
                            {ATTR_ENTITY_ID: satellite, "message": message, **kwargs},
                        )
                        successful_announcements += 1
                        _LOGGER.debug(
                            "%s: Successfully announced to satellite %s",
                            self.name,
                            satellite,
                        )
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        _LOGGER.error(
                            "%s: Failed to announce to satellite %s: %s",
                            self.name,
                            satellite,
                            e,
                        )
            else:
                # Fallback to TTS service
                _LOGGER.debug(
                    "%s: assist_satellite.announce not available, using TTS fallback",
                    self.name,
                )
                await self.hass.services.async_call(
                    "tts",
                    "speak",
                    {ATTR_ENTITY_ID: satellites, "message": message, **kwargs},
                )
                successful_announcements = len(satellites)

        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.error("%s: Failed to announce to satellites: %s", self.name, e)

        _LOGGER.debug(
            "%s: Announced to %d/%d satellites successfully",
            self.name,
            successful_announcements,
            len(satellites),
        )
