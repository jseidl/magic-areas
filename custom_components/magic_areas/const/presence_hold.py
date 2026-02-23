"""Presence hold feature constants."""

from homeassistant.helpers import config_validation as cv

from custom_components.magic_areas.const import (
    ConfigDomains,
    ConfigOption,
    FeatureOptionSet,
)


class PresenceHoldOptions(FeatureOptionSet):
    """Presence hold feature configuration options."""

    CONFIG_DOMAIN = ConfigDomains.FEATURES
    FEATURE_KEY = "presence_hold"

    TIMEOUT = ConfigOption(
        key="presence_hold_timeout",
        default=0,
        title="Presence Hold Timeout",
        description="Minutes after which presence hold automatically turns off (0 = never)",
        translation_key="timeout",
        validator=cv.positive_int,
        selector_type="number",
        selector_config={
            "min": 0,
            "max": 1440,
            "unit_of_measurement": "minutes",
        },
    )
