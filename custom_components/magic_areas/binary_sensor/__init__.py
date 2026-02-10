"""Binary sensor control for magic areas."""

import logging

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.magic_areas.base.magic import MagicArea, MagicMetaArea
from custom_components.magic_areas.binary_sensor.base import AreaSensorGroupBinarySensor
from custom_components.magic_areas.binary_sensor.ble_tracker import (
    AreaBLETrackerBinarySensor,
)
from custom_components.magic_areas.binary_sensor.presence import (
    AreaStateBinarySensor,
    MetaAreaStateBinarySensor,
)
from custom_components.magic_areas.binary_sensor.wasp_in_a_box import (
    AreaWaspInABoxBinarySensor,
)
from custom_components.magic_areas.const import (
    Features,
    MagicAreasFeatureInfoAggregates,
    MagicAreasFeatureInfoHealth,
)
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.ble_trackers import BleTrackerOptions
from custom_components.magic_areas.const.health import HealthOptions
from custom_components.magic_areas.helpers.area import get_area_from_config_entry
from custom_components.magic_areas.threshold import create_illuminance_threshold
from custom_components.magic_areas.util import cleanup_removed_entries

_LOGGER = logging.getLogger(__name__)

# Classes


class AreaAggregateBinarySensor(AreaSensorGroupBinarySensor):
    """Aggregate sensor for the area."""

    feature_info = MagicAreasFeatureInfoAggregates()


class AreaHealthBinarySensor(AreaSensorGroupBinarySensor):
    """Aggregate sensor for the area."""

    feature_info = MagicAreasFeatureInfoHealth()


# Setup


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the area binary sensor config entry."""

    area: MagicArea | MagicMetaArea | None = get_area_from_config_entry(
        hass, config_entry
    )
    assert area is not None

    entities = []

    # Create main presence sensor
    if area.is_meta() and isinstance(area, MagicMetaArea):
        entities.append(MetaAreaStateBinarySensor(area))
    else:
        entities.append(AreaStateBinarySensor(area))

    # Create extra sensors
    if area.has_feature(Features.AGGREGATION):
        entities.extend(create_aggregate_sensors(area))
        illuminance_threshold_sensor = create_illuminance_threshold(hass, area)
        if illuminance_threshold_sensor:
            entities.append(illuminance_threshold_sensor)

        # Wasp in a box
        if area.has_feature(Features.WASP_IN_A_BOX) and not area.is_meta():
            entities.extend(create_wasp_in_a_box_sensor(area))

    if area.has_feature(Features.HEALTH):
        entities.extend(create_health_sensors(area))

    if area.has_feature(Features.BLE_TRACKERS):
        entities.extend(create_ble_tracker_sensor(area))

    # Add all entities
    async_add_entities(entities)

    # Cleanup
    if BINARY_SENSOR_DOMAIN in area.magic_entities:
        cleanup_removed_entries(
            area.hass, entities, area.magic_entities[BINARY_SENSOR_DOMAIN]
        )


def create_wasp_in_a_box_sensor(
    area: MagicArea,
) -> list[AreaWaspInABoxBinarySensor]:
    """Add the Wasp in a box sensor for the area."""

    if not area.has_feature(Features.WASP_IN_A_BOX) or not area.has_feature(
        Features.AGGREGATION
    ):
        return []

    try:
        return [AreaWaspInABoxBinarySensor(area)]
    except Exception as e:  # pylint: disable=broad-exception-caught
        _LOGGER.error(
            "%s: Error creating wasp in a box sensor: %s",
            area.slug,
            str(e),
        )
        return []


def create_ble_tracker_sensor(area: MagicArea) -> list[AreaBLETrackerBinarySensor]:
    """Add the BLE tracker sensor for the area."""
    if not area.has_feature(Features.BLE_TRACKERS):
        return []

    if not area.config.get(BleTrackerOptions.ENTITIES):
        return []

    try:
        return [
            AreaBLETrackerBinarySensor(
                area,
            )
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        _LOGGER.error(
            "%s: Error creating BLE tracker sensor: %s",
            area.slug,
            str(e),
        )
        return []


def create_health_sensors(area: MagicArea) -> list[AreaHealthBinarySensor]:
    """Add the health sensors for the area."""
    if not area.has_feature(Features.HEALTH):
        return []

    if BINARY_SENSOR_DOMAIN not in area.entities:
        return []

    distress_entities: list[str] = []

    health_sensor_device_classes = area.config.get(HealthOptions.SENSOR_DEVICE_CLASSES)

    for entity in area.entities[BINARY_SENSOR_DOMAIN]:
        if ATTR_DEVICE_CLASS not in entity:
            continue

        if entity[ATTR_DEVICE_CLASS] not in health_sensor_device_classes:
            continue

        distress_entities.append(entity[ATTR_ENTITY_ID])

    if not distress_entities:
        _LOGGER.debug(
            "%s: No binary sensor found for configured device classes: %s.",
            area.name,
            str(health_sensor_device_classes),
        )
        return []

    _LOGGER.debug(
        "%s: Creating health sensor with the following entities: %s",
        area.slug,
        str(distress_entities),
    )

    try:
        return [
            AreaHealthBinarySensor(
                area,
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_ids=distress_entities,
            )
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        _LOGGER.error(
            "%s: Error creating area health sensor: %s",
            area.slug,
            str(e),
        )
        return []


def create_aggregate_sensors(area: MagicArea) -> list[Entity]:
    """Create the aggregate sensors for the area."""
    # Create aggregates
    if not area.has_feature(Features.AGGREGATION):
        return []

    aggregates: list[Entity] = []

    # Check BINARY_SENSOR_DOMAIN entities, count by device_class
    if BINARY_SENSOR_DOMAIN not in area.entities:
        return []

    device_class_entities: dict[str, list[str]] = {}

    for entity in area.entities[BINARY_SENSOR_DOMAIN]:
        if ATTR_DEVICE_CLASS not in entity:
            continue

        if entity[ATTR_DEVICE_CLASS] not in device_class_entities:
            device_class_entities[entity[ATTR_DEVICE_CLASS]] = []

        device_class_entities[entity[ATTR_DEVICE_CLASS]].append(entity["entity_id"])

    for device_class, entity_list in device_class_entities.items():
        if len(entity_list) < area.config.get(AggregateOptions.MIN_ENTITIES):
            continue

        if device_class not in area.config.get(
            AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES
        ):
            continue

        _LOGGER.debug(
            "Creating aggregate sensor for device_class '%s' with %s entities (%s)",
            device_class,
            len(entity_list),
            area.slug,
        )
        try:
            aggregates.append(
                AreaAggregateBinarySensor(area, device_class, entity_list)
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.error(
                "%s: Error creating '%s' aggregate sensor: %s",
                area.slug,
                device_class,
                str(e),
            )

    return aggregates
