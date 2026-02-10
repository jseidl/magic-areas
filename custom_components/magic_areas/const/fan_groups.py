"""Fan groups feature constants."""

import voluptuous as vol
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.helpers import config_validation as cv

from custom_components.magic_areas.const import (
    AreaStates,
    ConfigDomains,
    ConfigOption,
    FeatureOptionSet,
)


class FanGroupOptions(FeatureOptionSet):
    """Fan group feature configuration options."""

    CONFIG_DOMAIN = ConfigDomains.FEATURES
    FEATURE_KEY = "fan_groups"

    REQUIRED_STATE = ConfigOption(
        key="required_state",
        default=AreaStates.EXTENDED,
        title="Required State",
        description="Area state required before fan automation activates",
        translation_key="fan_required_state",
        validator=str,
        selector_type="select",
        selector_config={
            "options": [str(AreaStates.OCCUPIED), str(AreaStates.EXTENDED)],
        },
    )

    TRACKED_DEVICE_CLASS = ConfigOption(
        key="tracked_device_class",
        default=SensorDeviceClass.TEMPERATURE,
        title="Tracked Device Class",
        description="Sensor device class to monitor for fan control",
        translation_key="fan_tracked_device_class",
        validator=str,
        selector_type="select",
        selector_config={"options": []},  # Will be populated dynamically
    )

    SETPOINT = ConfigOption(
        key="setpoint",
        default=0.0,
        title="Setpoint",
        description="Threshold value to activate fan (sensor value must exceed this)",
        translation_key="fan_setpoint",
        validator=float,
        selector_type="number",
        selector_config={
            "min": -100,
            "max": 100,
            "step": 0.5,
        },
    )


FAN_GROUPS_ALLOWED_TRACKED_DEVICE_CLASS = [
    SensorDeviceClass.TEMPERATURE,
    SensorDeviceClass.HUMIDITY,
    SensorDeviceClass.CO,
    SensorDeviceClass.CO2,
    SensorDeviceClass.AQI,
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
    SensorDeviceClass.NITROGEN_DIOXIDE,
    SensorDeviceClass.NITROGEN_MONOXIDE,
    SensorDeviceClass.GAS,
    SensorDeviceClass.OZONE,
    SensorDeviceClass.PM1,
    SensorDeviceClass.PM10,
    SensorDeviceClass.PM25,
    SensorDeviceClass.SULPHUR_DIOXIDE,
]
