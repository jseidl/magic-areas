"""BLE trackers feature constants."""

from homeassistant.helpers import config_validation as cv

from custom_components.magic_areas.const import (
    ConfigDomains,
    ConfigOption,
    FeatureOptionSet,
)


class BleTrackerOptions(FeatureOptionSet):
    """BLE tracker feature configuration options."""

    CONFIG_DOMAIN = ConfigDomains.FEATURES
    FEATURE_KEY = "ble_trackers"

    ENTITIES = ConfigOption(
        key="ble_tracker_entities",
        default=[],
        title="BLE Tracker Entities",
        description="Sensor entities to monitor for BLE beacon presence",
        translation_key="ble_tracker_entities",
        validator=cv.entity_ids,
        selector_type="entity",
        selector_config={"domain": "sensor", "multiple": True},
    )
