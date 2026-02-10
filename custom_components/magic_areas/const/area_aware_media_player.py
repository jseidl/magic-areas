"""Area aware media player feature constants."""

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from custom_components.magic_areas.const import (
    AreaStates,
    ConfigDomains,
    ConfigOption,
    FeatureOptionSet,
)


class AreaAwareMediaPlayerOptions(FeatureOptionSet):
    """Area aware media player feature configuration options."""

    CONFIG_DOMAIN = ConfigDomains.FEATURES
    FEATURE_KEY = "area_aware_media_player"

    NOTIFICATION_DEVICES = ConfigOption(
        key="notification_devices",
        default=[],
        title="Notification Devices",
        description="Media player entities to use for notifications in this area",
        translation_key="notification_devices",
        validator=cv.entity_ids,
        selector_type="entity",
        selector_config={"domain": "media_player", "multiple": True},
    )

    NOTIFY_STATES = ConfigOption(
        key="notification_states",
        default=[AreaStates.EXTENDED],
        title="Notify States",
        description="Area states when notifications should be sent to this area",
        translation_key="notification_states",
        validator=cv.ensure_list,
        selector_type="select",
        selector_config={"multiple": True},  # Options populated dynamically
    )
