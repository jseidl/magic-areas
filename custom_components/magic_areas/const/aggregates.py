"""Aggregates feature constants."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.helpers import config_validation as cv

from custom_components.magic_areas.const import (
    ConfigDomains,
    ConfigOption,
    FeatureOptionSet,
)


class AggregateOptions(FeatureOptionSet):
    """Aggregate feature configuration options."""

    CONFIG_DOMAIN = ConfigDomains.FEATURES
    FEATURE_KEY = "aggregates"

    MIN_ENTITIES = ConfigOption(
        key="aggregates_min_entities",
        default=1,
        title="Minimum Entities",
        description="Minimum number of entities required to create an aggregate sensor",
        translation_key="aggregates_min_entities",
        validator=cv.positive_int,
        selector_type="number",
        selector_config={
            "min": 1,
            "max": 50,
            "unit_of_measurement": "entities",
        },
    )

    BINARY_SENSOR_DEVICE_CLASSES = ConfigOption(
        key="aggregates_binary_sensor_device_classes",
        default=[
            BinarySensorDeviceClass.DOOR,
            BinarySensorDeviceClass.LIGHT,
            BinarySensorDeviceClass.MOTION,
            BinarySensorDeviceClass.OCCUPANCY,
            BinarySensorDeviceClass.WINDOW,
        ],
        title="Binary Sensor Device Classes",
        description="Binary sensor device classes to aggregate",
        translation_key="aggregates_binary_sensor_device_classes",
        validator=cv.ensure_list,
        selector_type="select",
        selector_config={
            "options": [cls.value for cls in BinarySensorDeviceClass],
            "multiple": True,
        },
    )

    SENSOR_DEVICE_CLASSES = ConfigOption(
        key="aggregates_sensor_device_classes",
        default=[
            SensorDeviceClass.HUMIDITY,
            SensorDeviceClass.ILLUMINANCE,
            SensorDeviceClass.TEMPERATURE,
        ],
        title="Sensor Device Classes",
        description="Sensor device classes to aggregate",
        translation_key="aggregates_sensor_device_classes",
        validator=cv.ensure_list,
        selector_type="select",
        selector_config={
            "options": [cls.value for cls in SensorDeviceClass],
            "multiple": True,
        },
    )

    ILLUMINANCE_THRESHOLD = ConfigOption(
        key="aggregates_illuminance_threshold",
        default=0,
        title="Illuminance Threshold",
        description="Illuminance threshold for binary light sensor (0 = disabled)",
        translation_key="aggregates_illuminance_threshold",
        validator=cv.positive_int,
        selector_type="number",
        selector_config={
            "min": 0,
            "max": 1000,
            "unit_of_measurement": "lx",
            "mode": "slider",
        },
    )

    ILLUMINANCE_THRESHOLD_HYSTERESIS = ConfigOption(
        key="aggregates_illuminance_threshold_hysteresis",
        default=0,
        title="Illuminance Threshold Hysteresis",
        description="Percentage hysteresis for illuminance threshold to prevent flapping",
        translation_key="aggregates_illuminance_threshold_hysteresis",
        validator=cv.positive_int,
        selector_type="number",
        selector_config={
            "min": 0,
            "max": 100,
            "unit_of_measurement": "%",
            "mode": "slider",
        },
    )


# Aggregate device class lists
AGGREGATE_BINARY_SENSOR_CLASSES = [
    BinarySensorDeviceClass.WINDOW,
    BinarySensorDeviceClass.DOOR,
    BinarySensorDeviceClass.MOTION,
    BinarySensorDeviceClass.MOISTURE,
    BinarySensorDeviceClass.LIGHT,
]

# Binary sensor device classes that use "all" aggregation mode (all must be on)
BINARY_SENSOR_ALL_MODE_CLASSES = [
    BinarySensorDeviceClass.CONNECTIVITY,
    BinarySensorDeviceClass.PLUG,
]

AGGREGATE_SENSOR_CLASSES = (
    SensorDeviceClass.CURRENT,
    SensorDeviceClass.ENERGY,
    SensorDeviceClass.HUMIDITY,
    SensorDeviceClass.ILLUMINANCE,
    SensorDeviceClass.POWER,
    SensorDeviceClass.TEMPERATURE,
)

# Sensor device classes that use sum aggregation mode
SENSOR_SUM_MODE_CLASSES = [
    SensorDeviceClass.POWER,
    SensorDeviceClass.CURRENT,
    SensorDeviceClass.ENERGY,
]

# Sensor device classes that use TOTAL state class
SENSOR_TOTAL_STATE_CLASSES = [
    SensorDeviceClass.ENERGY,
]

# Sensor device classes that use TOTAL_INCREASING state class
SENSOR_TOTAL_INCREASING_STATE_CLASSES = [
    SensorDeviceClass.GAS,
    SensorDeviceClass.WATER,
]
