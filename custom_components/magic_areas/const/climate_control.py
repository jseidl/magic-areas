"""Climate control feature constants."""

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from custom_components.magic_areas.const import (
    ConfigDomains,
    EMPTY_STRING,
    ConfigOption,
    FeatureOptionSet,
)


class ClimateControlOptions(FeatureOptionSet):
    """Climate control feature configuration options."""

    CONFIG_DOMAIN = ConfigDomains.FEATURES
    FEATURE_KEY = "climate_control"

    ENTITY_ID = ConfigOption(
        key="entity_id",
        default=None,
        title="Climate Entity",
        description="Climate entity to control based on area state",
        translation_key="climate_entity_id",
        validator=cv.entity_id,
        selector_type="entity",
        selector_config={"domain": "climate"},
    )

    PRESET_CLEAR = ConfigOption(
        key="preset_clear",
        default=EMPTY_STRING,
        title="Preset for Clear State",
        description="Climate preset to use when area is clear/unoccupied",
        translation_key="climate_preset_clear",
        validator=str,
        selector_type="select",
        selector_config={
            "options": []
        },  # Populated dynamically from entity capabilities
    )

    PRESET_OCCUPIED = ConfigOption(
        key="preset_occupied",
        default=EMPTY_STRING,
        title="Preset for Occupied State",
        description="Climate preset to use when area is occupied",
        translation_key="climate_preset_occupied",
        validator=str,
        selector_type="select",
        selector_config={"options": []},  # Populated dynamically
    )

    PRESET_EXTENDED = ConfigOption(
        key="preset_extended",
        default=EMPTY_STRING,
        title="Preset for Extended State",
        description="Climate preset to use when area is in extended occupancy",
        translation_key="climate_preset_extended",
        validator=str,
        selector_type="select",
        selector_config={"options": []},  # Populated dynamically
    )

    PRESET_SLEEP = ConfigOption(
        key="preset_sleep",
        default=EMPTY_STRING,
        title="Preset for Sleep State",
        description="Climate preset to use when area is in sleep mode",
        translation_key="climate_preset_sleep",
        validator=str,
        selector_type="select",
        selector_config={"options": []},  # Populated dynamically
    )
