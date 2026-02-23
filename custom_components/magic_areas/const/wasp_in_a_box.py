"""Wasp in a box feature constants."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers import config_validation as cv

from custom_components.magic_areas.const import (
    ConfigDomains,
    ConfigOption,
    FeatureOptionSet,
)

# Wasp in a box device class lists
WASP_IN_A_BOX_WASP_DEVICE_CLASSES = [
    BinarySensorDeviceClass.MOTION,
    BinarySensorDeviceClass.OCCUPANCY,
    BinarySensorDeviceClass.PRESENCE,
]

WASP_IN_A_BOX_BOX_DEVICE_CLASSES = [
    BinarySensorDeviceClass.DOOR,
    BinarySensorDeviceClass.GARAGE_DOOR,
]


class WaspInABoxOptions(FeatureOptionSet):
    """Wasp in a box feature configuration options."""

    CONFIG_DOMAIN = ConfigDomains.FEATURES
    FEATURE_KEY = "wasp_in_a_box"

    DELAY = ConfigOption(
        key="delay",
        default=90,
        title="Activation Delay",
        description="Seconds to wait after door/window closes before detecting presence",
        translation_key="wasp_delay",
        validator=cv.positive_int,
        selector_type="number",
        selector_config={
            "min": 0,
            "max": 600,
            "unit_of_measurement": "seconds",
        },
    )

    WASP_TIMEOUT = ConfigOption(
        key="wasp_timeout",
        default=0,
        title="Wasp Timeout",
        description="Minutes before automatically clearing wasp presence (0 = use area clear timeout)",
        translation_key="wasp_timeout",
        validator=cv.positive_int,
        selector_type="number",
        selector_config={
            "min": 0,
            "max": 1440,
            "unit_of_measurement": "minutes",
        },
    )

    WASP_DEVICE_CLASSES = ConfigOption(
        key="wasp_device_classes",
        default=[BinarySensorDeviceClass.MOTION, BinarySensorDeviceClass.OCCUPANCY],
        title="Wasp Device Classes",
        description="Binary sensor device classes to use for detecting presence (the 'wasp')",
        translation_key="wasp_device_classes",
        validator=cv.ensure_list,
        selector_type="select",
        selector_config={
            "options": WASP_IN_A_BOX_WASP_DEVICE_CLASSES,
            "multiple": True,
        },
    )
