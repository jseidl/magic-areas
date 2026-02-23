"""Platform file for Magic Areas threhsold sensors."""

import logging

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.threshold.binary_sensor import ThresholdSensor
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    EMPTY_STRING,
    MagicAreasFeatureInfoThrehsold,
)
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.helpers.aggregates import (
    should_create_threshold_sensor,
)

_LOGGER = logging.getLogger(__name__)


def create_illuminance_threshold(hass: HomeAssistant, area: MagicArea) -> Entity | None:
    """Create threhsold light binary sensor based off illuminance aggregate."""

    # Use shared validation helper
    if not should_create_threshold_sensor(area):
        return None

    illuminance_threshold = area.config.get(AggregateOptions.ILLUMINANCE_THRESHOLD)

    illuminance_threshold_hysteresis_percentage = area.config.get(
        AggregateOptions.ILLUMINANCE_THRESHOLD_HYSTERESIS
    )
    illuminance_threshold_hysteresis = 0

    if illuminance_threshold_hysteresis_percentage > 0:
        illuminance_threshold_hysteresis = illuminance_threshold * (
            illuminance_threshold_hysteresis_percentage / 100
        )

    illuminance_aggregate_entity_id = (
        f"{SENSOR_DOMAIN}.magic_areas_aggregates_{area.slug}_aggregate_illuminance"
    )

    _LOGGER.debug(
        "Creating illuminance threhsold sensor for area '%s': Threhsold: %d, Hysteresis: %d (%d%%)",
        area.slug,
        illuminance_threshold,
        illuminance_threshold_hysteresis,
        illuminance_threshold_hysteresis_percentage,
    )

    try:
        return AreaThresholdSensor(
            hass=hass,
            area=area,
            device_class=BinarySensorDeviceClass.LIGHT,
            entity_id=illuminance_aggregate_entity_id,
            upper=illuminance_threshold,
            hysteresis=illuminance_threshold_hysteresis,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        _LOGGER.error(
            "%s: Error creating calculated light sensor: %s",
            area.slug,
            str(e),
        )
        return None


class AreaThresholdSensor(MagicEntity, ThresholdSensor):
    """Threshold sensor based off aggregates."""

    feature_info = MagicAreasFeatureInfoThrehsold()

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        area: MagicArea,
        device_class: BinarySensorDeviceClass,
        entity_id: str,
        upper: int | None = None,
        lower: int | None = None,
        hysteresis: int = 0,
    ) -> None:
        """Initialize an area sensor group binary sensor."""

        MagicEntity.__init__(
            self, area, domain=BINARY_SENSOR_DOMAIN, translation_key=device_class
        )
        ThresholdSensor.__init__(
            self,
            hass=hass,
            entity_id=entity_id,
            name=EMPTY_STRING,
            unique_id=self.unique_id,
            lower=lower,
            upper=upper,
            hysteresis=hysteresis,
            device_class=device_class,
        )
        delattr(self, "_attr_name")
