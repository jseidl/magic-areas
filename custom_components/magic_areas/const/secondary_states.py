"""Secondary states configuration constants."""

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from custom_components.magic_areas.const import (
    AreaStates,
    CalculationMode,
    ConfigDomains,
    ConfigOption,
    OptionSet,
)


class SecondaryStateOptions(OptionSet):
    """Secondary state configuration options."""

    CONFIG_DOMAIN = ConfigDomains.SECONDARY_STATES

    DARK_ENTITY = ConfigOption(
        key="dark_entity",
        default="",
        title="Dark Entity",
        description="Binary sensor or illuminance sensor to determine if area is dark",
        translation_key="dark_entity",
        validator=cv.entity_id,
        selector_type="entity",
        selector_config={"domain": ["binary_sensor", "sensor"]},
    )

    ACCENT_ENTITY = ConfigOption(
        key="accent_entity",
        default="",
        title="Accent Entity",
        description="Binary sensor to determine if accent/entertainment mode is active",
        translation_key="accent_entity",
        validator=cv.entity_id,
        selector_type="entity",
        selector_config={"domain": ["binary_sensor", "switch", "input_boolean"]},
    )

    SLEEP_ENTITY = ConfigOption(
        key="sleep_entity",
        default="",
        title="Sleep Entity",
        description="Binary sensor to determine if sleep mode is active",
        translation_key="sleep_entity",
        validator=cv.entity_id,
        selector_type="entity",
        selector_config={"domain": ["binary_sensor", "switch", "input_boolean"]},
    )

    SLEEP_TIMEOUT = ConfigOption(
        key="sleep_timeout",
        default=1,
        title="Sleep Timeout",
        description="Minutes to wait before clearing sleep state",
        translation_key="sleep_timeout",
        validator=cv.positive_int,
        selector_type="number",
        selector_config={
            "min": 0,
            "max": 120,
            "unit_of_measurement": "minutes",
        },
    )

    EXTENDED_TIME = ConfigOption(
        key="extended_time",
        default=5,
        title="Extended Time",
        description="Minutes of continuous presence before area enters extended state",
        translation_key="extended_time",
        validator=cv.positive_int,
        selector_type="number",
        selector_config={
            "min": 0,
            "max": 120,
            "unit_of_measurement": "minutes",
        },
    )

    EXTENDED_TIMEOUT = ConfigOption(
        key="extended_timeout",
        default=10,
        title="Extended Timeout",
        description="Minutes to wait before clearing extended state",
        translation_key="extended_timeout",
        validator=cv.positive_int,
        selector_type="number",
        selector_config={
            "min": 0,
            "max": 120,
            "unit_of_measurement": "minutes",
        },
    )

    CALCULATION_MODE = ConfigOption(
        key="calculation_mode",
        default="majority",
        title="Calculation Mode",
        description="How to aggregate secondary states for meta-areas",
        translation_key="calculation_mode",
        validator=vol.In(["any", "all", "majority"]),
        selector_type="select",
        selector_config={
            "options": ["any", "all", "majority"],
            "translation_key": "calculation_mode",
        },
    )


# Map area states to their entity config keys
CONFIGURABLE_AREA_STATE_MAP = {
    AreaStates.SLEEP: SecondaryStateOptions.SLEEP_ENTITY.key,
    AreaStates.DARK: SecondaryStateOptions.DARK_ENTITY.key,
    AreaStates.ACCENT: SecondaryStateOptions.ACCENT_ENTITY.key,
}
