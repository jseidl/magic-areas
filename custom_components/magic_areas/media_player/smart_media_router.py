"""Smart Media Router component."""

import logging
from enum import StrEnum, auto
from typing import Any

from custom_components.magic_areas.base.entities import MagicEntity
from homeassistant.core import State
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.components.group.media_player import MediaPlayerGroup
from homeassistant.helpers.entity_registry import (
    async_get as entityreg_async_get,
    RegistryEntry,
)
from homeassistant.helpers.device_registry import (
    async_get as devicereg_async_get,
    DeviceEntry,
)
from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ANNOUNCE,
    MediaType,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    SERVICE_PLAY_MEDIA,
    MediaPlayerState,
)
from custom_components.magic_areas.const import (
    MagicAreasFeatureInfoMediaPlayerGroups,
    EMPTY_STRING,
    MEDIA_PLAYER_DOMAIN,
    INVALID_STATES,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)

"""
    @TODO LIST
    - move AAMP configuration into here
    - remove media player group from non-meta areas
    - fall back to interrupting playing devices if no other are available
"""

# Types & Constants

TTS_MEDIA_SOURCE_PREFIX: str = "media-source://tts"
MEDIA_PLAYER_AVAILABLE_STATES = [
    MediaPlayerState.OFF,
    MediaPlayerState.IDLE,
    MediaPlayerState.STANDBY,
]

PLATFORM_ALEXA_MEDIA = "alexa_media"
MANUFACTURER_GOOGLE = "Google Inc."

AUDIO_DEVICE_CLASSES = [MediaPlayerDeviceClass.SPEAKER, MediaPlayerDeviceClass.RECEIVER]
VIDEO_DEVICE_CLASSES = [MediaPlayerDeviceClass.TV]

SMART_SPEAKER_MODELS: dict[str, list[str]] = {
    MANUFACTURER_GOOGLE: ["Google Home Mini", "Google Nest Mini", "Google Nest Hub"]
}


class ContentTypeRoutingGroup(StrEnum):
    """Routing groups for media types."""

    VIDEO = auto()
    NOTIFICATION = auto()
    AUDIO = auto()
    GENERIC = auto()


MEDIA_TYPE_MAP_AUDIO_VIDEO: dict[ContentTypeRoutingGroup, list[MediaType]] = {
    ContentTypeRoutingGroup.VIDEO: [
        MediaType.VIDEO,
        MediaType.CHANNEL,
        MediaType.TVSHOW,
        MediaType.MOVIE,
        MediaType.IMAGE,
        MediaType.GAME,
        MediaType.APP,
        MediaType.APPS,
    ],
    ContentTypeRoutingGroup.AUDIO: [
        MediaType.ALBUM,
        MediaType.COMPOSER,
        MediaType.MUSIC,
        MediaType.TRACK,
        MediaType.PODCAST,
        MediaType.PLAYLIST,
    ],
}

ROUTING_GROUP_PRIORITY_MAP: dict[
    ContentTypeRoutingGroup, list[ContentTypeRoutingGroup]
] = {
    ContentTypeRoutingGroup.NOTIFICATION: [
        ContentTypeRoutingGroup.NOTIFICATION,
        ContentTypeRoutingGroup.AUDIO,
        ContentTypeRoutingGroup.VIDEO,
    ],
    ContentTypeRoutingGroup.AUDIO: [
        ContentTypeRoutingGroup.AUDIO,
        ContentTypeRoutingGroup.VIDEO,
    ],
}


class SmartMediaRouter(MagicEntity, MediaPlayerGroup):
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
        self.classified_devices: dict[str, set] = {
            eid: self.classify_device(eid) for eid in entities
        }

    async def async_play_media(
        self, media_type: MediaType, media_id: str, **kwargs
    ) -> None:
        """Forward a piece of media to appropriate devices in the area."""

        _LOGGER.warning(
            "Received play request: MT=%s, MID=%s, KWARGS=%s",
            media_type,
            media_id,
            str(kwargs),
        )

        routing_group: ContentTypeRoutingGroup = self.get_routing_group_for_request(
            media_type, media_id, kwargs
        )

        _LOGGER.warning("Selected routing group: %s", routing_group)

        targeted_media_player: str | None = await self.route_request(
            routing_group, media_type, media_id, kwargs
        )
        _LOGGER.warning("Selected device: %s", targeted_media_player)

    async def route_request(
        self,
        routing_group: ContentTypeRoutingGroup,
        media_type: MediaType,
        media_id: str,
        extra_attributes: dict[str, Any],
    ) -> str | None:
        """Route request to target device, falling back to other candidates when needed."""

        target_devices: list[str] = self.get_target_devices_for_content(routing_group)

        _LOGGER.warning("Elected candidate devices: %s", str(target_devices))

        # Run full checks
        for dev in target_devices:
            device_state: State | None = self.hass.states.get(dev)
            if not device_state:
                continue
            if device_state.state in INVALID_STATES:
                continue
            if device_state.state not in MEDIA_PLAYER_AVAILABLE_STATES:
                continue

            if await self.forward_request(dev, media_type, media_id, extra_attributes):
                return dev

        # @TODO fall back to interrupting playing devices if no other are available

        # Fallback, no devices available or succeeded
        return None

    async def forward_request(
        self,
        media_player_entity_id: str,
        media_type: MediaType,
        media_id: str,
        extra_attributes: dict[str, Any],
    ) -> bool:
        """Forward request to appropriate media player device."""
        _LOGGER.warning("MT=%s", media_type)
        data: dict[str, Any] = {
            ATTR_MEDIA_CONTENT_ID: media_id,
            ATTR_MEDIA_CONTENT_TYPE: MediaType(media_type).value,
            ATTR_ENTITY_ID: media_player_entity_id,
        }
        if extra_attributes:
            data.update(extra_attributes)

        _LOGGER.warning("Forwarding request: %s", str(data))

        # return True

        try:
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_PLAY_MEDIA,
                data,
            )
            return True
        except Exception as e:  # pylint disable=broad-exception-caught
            _LOGGER.error("Error forwarding call: %s", str(e))
            return False

    def get_routing_group_for_request(
        self, media_type: MediaType, media_id: str, extra_arguments: dict[str, Any]
    ) -> ContentTypeRoutingGroup:
        """Get routing group for a given request."""

        # Notification
        if media_id.startswith(TTS_MEDIA_SOURCE_PREFIX):
            return ContentTypeRoutingGroup.NOTIFICATION
        if (
            ATTR_MEDIA_ANNOUNCE in extra_arguments
            and extra_arguments[ATTR_MEDIA_ANNOUNCE]
        ):
            return ContentTypeRoutingGroup.NOTIFICATION

        # Video
        if media_type in MEDIA_TYPE_MAP_AUDIO_VIDEO[ContentTypeRoutingGroup.VIDEO]:
            return ContentTypeRoutingGroup.VIDEO

        # Audio
        if media_type in MEDIA_TYPE_MAP_AUDIO_VIDEO[ContentTypeRoutingGroup.AUDIO]:
            return ContentTypeRoutingGroup.AUDIO

        # Fallback
        return ContentTypeRoutingGroup.GENERIC

    def get_target_devices_for_content(
        self, routing_group: ContentTypeRoutingGroup
    ) -> list[str]:
        """Return the entity_id of a media player device suitable and available for a given content."""

        candidates: list[str] = []
        seen_devices: set = set()

        priority_groups: list[ContentTypeRoutingGroup] = ROUTING_GROUP_PRIORITY_MAP.get(
            routing_group, []
        )

        # Fetch device list, orderd by priority group
        for priority_group in priority_groups:
            # Devices belonging to this group
            group_devices: list[str] = [
                eid
                for eid, groups in self.classified_devices.items()
                if priority_group in groups
            ]

            # Exclusive before multi-role
            exclusive: list[str] = [
                eid for eid in group_devices if len(self.classified_devices[eid]) == 1
            ]
            multi: list[str] = [
                eid for eid in group_devices if len(self.classified_devices[eid]) > 1
            ]

            for eid in exclusive + multi:
                if eid not in seen_devices:
                    seen_devices.add(eid)
                    candidates.append(eid)

        return candidates

    def classify_device(self, entity_id: str) -> set[str]:
        """Return routing groups that the device is suitable for."""

        groups: set[str] = set()

        if self.is_notification_device(entity_id):
            groups.add(ContentTypeRoutingGroup.NOTIFICATION)

        if self.is_audio_device(entity_id):
            groups.add(ContentTypeRoutingGroup.AUDIO)

        if self.is_video_device(entity_id):
            groups.add(ContentTypeRoutingGroup.VIDEO)

        return groups

    def is_notification_device(self, entity_id: str) -> bool:
        """Check if the entity is suitable for notifications."""

        # Inspect devices
        entity_registry = entityreg_async_get(self.hass)
        device_registry = devicereg_async_get(self.hass)

        entity_entry: RegistryEntry | None = entity_registry.async_get(entity_id)

        if not entity_entry:
            return False

        # Platform checks
        ## Alexa
        if entity_entry.platform == PLATFORM_ALEXA_MEDIA:
            return True

        # Device checks
        if entity_entry.device_id:
            device_entry: DeviceEntry | None = device_registry.async_get(
                entity_entry.device_id
            )

            if not device_entry:
                return False

            # Google
            if (
                device_entry.manufacturer == MANUFACTURER_GOOGLE
                and device_entry.model in SMART_SPEAKER_MODELS[MANUFACTURER_GOOGLE]
            ):
                return True

        return False

    def is_audio_device(self, entity_id: str) -> bool:
        """Check if the entity is suitable for audio."""

        # Inspect entity
        entity_registry = entityreg_async_get(self.hass)

        entity_entry: RegistryEntry | None = entity_registry.async_get(entity_id)

        if not entity_entry:
            return False

        _LOGGER.warning(
            "Entity %s device class %s",
            entity_id,
            entity_entry.device_class,
        )
        _LOGGER.warning("Entity dump %s", str(entity_entry))

        if (
            entity_entry.device_class
            and entity_entry.device_class in AUDIO_DEVICE_CLASSES
        ) or (
            entity_entry.original_device_class
            and entity_entry.original_device_class in AUDIO_DEVICE_CLASSES
        ):
            return True

        return False

    def is_video_device(self, entity_id: str) -> bool:
        """Check if the entity is suitable for video."""

        # Inspect devices
        entity_registry = entityreg_async_get(self.hass)

        entity_entry: RegistryEntry | None = entity_registry.async_get(entity_id)

        if not entity_entry:
            return False

        if (
            entity_entry.device_class
            and entity_entry.device_class in VIDEO_DEVICE_CLASSES
        ) or (
            entity_entry.original_device_class
            and entity_entry.original_device_class in VIDEO_DEVICE_CLASSES
        ):
            return True

        return False
