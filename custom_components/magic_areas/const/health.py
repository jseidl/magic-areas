"""Health sensor feature constants."""

from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import STATE_ON, STATE_PROBLEM
from homeassistant.helpers import config_validation as cv

from custom_components.magic_areas.const import (
    ConfigDomains,
    ConfigOption,
    FeatureOptionSet,
)

# Distress sensor classes for health monitoring
DISTRESS_SENSOR_CLASSES = [
    BinarySensorDeviceClass.PROBLEM,
    BinarySensorDeviceClass.SMOKE,
    BinarySensorDeviceClass.MOISTURE,
    BinarySensorDeviceClass.SAFETY,
    BinarySensorDeviceClass.GAS,
]

DISTRESS_STATES = [AlarmControlPanelState.TRIGGERED, STATE_ON, STATE_PROBLEM]


class HealthOptions(FeatureOptionSet):
    """Health sensor feature configuration options."""

    CONFIG_DOMAIN = ConfigDomains.FEATURES
    FEATURE_KEY = "health"

    SENSOR_DEVICE_CLASSES = ConfigOption(
        key="health_binary_sensor_device_classes",
        default=DISTRESS_SENSOR_CLASSES,
        title="Health Sensor Device Classes",
        description="Binary sensor device classes to monitor for health/safety issues",
        translation_key="health_binary_sensor_device_classes",
        validator=cv.ensure_list,
        selector_type="select",
        selector_config={
            "options": DISTRESS_SENSOR_CLASSES,
            "multiple": True,
        },
    )
