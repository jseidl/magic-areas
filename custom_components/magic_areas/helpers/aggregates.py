"""Helper functions for aggregate sensor validation."""

import logging

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor.const import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.const import ATTR_DEVICE_CLASS

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import Features
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.wasp_in_a_box import (
    WASP_IN_A_BOX_BOX_DEVICE_CLASSES,
    WaspInABoxOptions,
)

_LOGGER = logging.getLogger(__name__)


def should_create_threshold_sensor(area: MagicArea) -> bool:
    """Check if area conditions warrant threshold sensor creation.

    Validation mirrors the logic in create_illuminance_threshold().

    Args:
        area: MagicArea instance to check

    Returns:
        True if threshold sensor should be created, False otherwise

    """
    # Must have aggregates enabled
    if not area.has_feature(Features.AGGREGATION):
        return False

    # Threshold must be configured > 0
    illuminance_threshold = area.config.get(AggregateOptions.ILLUMINANCE_THRESHOLD)
    if illuminance_threshold == 0:
        return False

    # Illuminance must be in sensor device classes
    if SensorDeviceClass.ILLUMINANCE not in area.config.get(
        AggregateOptions.SENSOR_DEVICE_CLASSES
    ):
        return False

    # Must have sensor entities
    if SENSOR_DOMAIN not in area.entities:
        return False

    # Must have at least one illuminance sensor
    illuminance_sensors = [
        sensor
        for sensor in area.entities[SENSOR_DOMAIN]
        if ATTR_DEVICE_CLASS in sensor
        and sensor[ATTR_DEVICE_CLASS] == SensorDeviceClass.ILLUMINANCE
    ]

    return len(illuminance_sensors) > 0


def should_create_light_aggregate(area: MagicArea) -> bool:
    """Check if area conditions warrant light aggregate creation.

    Validation mirrors the logic in create_aggregate_sensors().

    Args:
        area: MagicArea instance to check

    Returns:
        True if light aggregate should be created, False otherwise

    """
    # Must have aggregates enabled
    if not area.has_feature(Features.AGGREGATION):
        return False

    # Must have binary sensor entities
    if BINARY_SENSOR_DOMAIN not in area.entities:
        return False

    # Light must be in configured device classes
    if BinarySensorDeviceClass.LIGHT not in area.config.get(
        AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES
    ):
        return False

    # Count light binary sensors
    light_sensors = [
        entity
        for entity in area.entities[BINARY_SENSOR_DOMAIN]
        if ATTR_DEVICE_CLASS in entity
        and entity[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.LIGHT
    ]

    # Must have at least one light sensor
    if len(light_sensors) == 0:
        return False

    # Must meet minimum entities requirement
    min_entities = area.config.get(AggregateOptions.MIN_ENTITIES)
    if len(light_sensors) < min_entities:
        return False

    return True


def get_binary_sensor_aggregate_device_classes(area: MagicArea) -> set[str]:
    """Return the binary sensor device classes which will get an aggregate.

    Works from the area's entities and configuration (not from the state
    machine), so the answer doesn't depend on whether the aggregate entities
    have been created yet. Mirrors the logic in create_aggregate_sensors().

    Args:
        area: MagicArea instance to check

    Returns:
        Set of device classes with an aggregate (empty if aggregates disabled)

    """
    if not area.has_feature(Features.AGGREGATION):
        return set()

    configured_classes = area.config.get(AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES)
    min_entities = area.config.get(AggregateOptions.MIN_ENTITIES)

    class_counts: dict[str, int] = {}
    for entity in area.entities.get(BINARY_SENSOR_DOMAIN, []):
        device_class = entity.get(ATTR_DEVICE_CLASS)
        if device_class is None:
            continue
        class_counts[device_class] = class_counts.get(device_class, 0) + 1

    return {
        device_class
        for device_class, count in class_counts.items()
        if count >= min_entities and device_class in configured_classes
    }


def get_wasp_in_a_box_available_device_classes(
    area: MagicArea,
) -> tuple[list[str], list[str]]:
    """Return the (wasp, box) device classes which will get an aggregate.

    Only classes configured for Wasp in a Box are considered: the configured
    wasp device classes and the built-in box (door) device classes.

    Args:
        area: MagicArea instance to check

    Returns:
        Tuple of (available wasp device classes, available box device classes)

    """
    aggregate_classes = get_binary_sensor_aggregate_device_classes(area)

    wasp = [
        device_class
        for device_class in area.config.get(WaspInABoxOptions.WASP_DEVICE_CLASSES)
        if device_class in aggregate_classes
    ]
    box = [
        device_class
        for device_class in WASP_IN_A_BOX_BOX_DEVICE_CLASSES
        if device_class in aggregate_classes
    ]
    return wasp, box
