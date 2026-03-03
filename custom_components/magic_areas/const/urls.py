"""URL constants for Magic Areas documentation and external references."""

from enum import StrEnum


class UrlDescriptionPlaceholders(StrEnum):
    """Placeholder keys used in description_placeholders dicts for config flow steps."""

    AREA_STATES = "url_area_states"
    META_AREAS = "url_meta_areas"
    PRESENCE_SENSING = "url_presence_sensing"
    THRESHOLD_HYSTERESIS = "url_threshold_hysteresis"
    ROOM_ASSISTANT = "url_room_assistant"
    BERMUDA = "url_bermuda"
    ESPRESENSE = "url_espresense"


class MagicAreasDocumentationUrls(StrEnum):
    """Magic Areas wiki/documentation URLs."""

    AREA_STATES = "https://github.com/jseidl/hass-magic_areas/wiki/Area-State"
    META_AREAS = "https://github.com/jseidl/hass-magic_areas/wiki/Meta-Areas"
    PRESENCE_SENSING = (
        "https://github.com/jseidl/hass-magic_areas/wiki/Presence-Sensing"
    )


# Third-party and external documentation URLs
URL_HA_DOCUMENTATION_THRESHOLD_HYSTERESIS = (
    "https://www.home-assistant.io/integrations/threshold/#hysteresis"
)
URL_ROOM_ASSISTANT = "https://github.com/mKeRix/room-assistant"
URL_BERMUDA = "https://github.com/agittins/bermuda"
URL_ESPRESENSE = "https://github.com/ESPresense/ESPresense"
