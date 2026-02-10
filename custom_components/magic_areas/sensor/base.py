"""Base classes for sensor component."""

import logging

from homeassistant.components.group.sensor import ATTR_MEAN, ATTR_SUM, SensorGroup
from homeassistant.components.sensor.const import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import DEFAULT_SENSOR_PRECISION, EMPTY_STRING
from custom_components.magic_areas.const.aggregates import (
    SENSOR_SUM_MODE_CLASSES,
    SENSOR_TOTAL_INCREASING_STATE_CLASSES,
    SENSOR_TOTAL_STATE_CLASSES,
)

_LOGGER = logging.getLogger(__name__)


class AreaSensorGroupSensor(MagicEntity, SensorGroup):
    """Sensor for the magic area, group sensor with all the stuff in it."""

    def __init__(
        self,
        area: MagicArea,
        device_class: str,
        entity_ids: list[str],
        unit_of_measurement: str,
    ) -> None:
        """Initialize an area sensor group sensor."""

        MagicEntity.__init__(
            self, area=area, domain=SENSOR_DOMAIN, translation_key=device_class
        )

        final_unit_of_measurement = None

        # Resolve unit of measurement
        unit_attr_name = f"{device_class}_unit"
        if hasattr(area.hass.config.units, unit_attr_name):
            final_unit_of_measurement = getattr(area.hass.config.units, unit_attr_name)
        else:
            final_unit_of_measurement = unit_of_measurement

        self._attr_suggested_display_precision = DEFAULT_SENSOR_PRECISION

        sensor_device_class: SensorDeviceClass | None = (
            SensorDeviceClass(device_class) if device_class else None
        )
        self.device_class = sensor_device_class

        state_class = SensorStateClass.MEASUREMENT

        if device_class in SENSOR_TOTAL_INCREASING_STATE_CLASSES:
            state_class = SensorStateClass.TOTAL_INCREASING
        elif device_class in SENSOR_TOTAL_STATE_CLASSES:
            state_class = SensorStateClass.TOTAL

        SensorGroup.__init__(
            self,
            hass=area.hass,
            device_class=sensor_device_class,
            entity_ids=entity_ids,
            ignore_non_numeric=True,
            sensor_type=(
                ATTR_SUM if device_class in SENSOR_SUM_MODE_CLASSES else ATTR_MEAN
            ),
            state_class=state_class,
            unit_of_measurement=final_unit_of_measurement,
            name=EMPTY_STRING,
            unique_id=self._attr_unique_id,
        )
        delattr(self, "_attr_name")
