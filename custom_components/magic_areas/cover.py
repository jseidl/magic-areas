"""Cover controls for magic areas."""

import logging

from homeassistant.components.cover import (
    DEVICE_CLASSES as COVER_DEVICE_CLASSES,
    CoverDeviceClass,
)
from homeassistant.components.cover.const import DOMAIN as COVER_DOMAIN
from homeassistant.components.group.cover import CoverGroup
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    EMPTY_STRING,
    Features,
    MagicAreasFeatureInfoCoverGroups,
)
from custom_components.magic_areas.helpers.area import get_area_from_config_entry
from custom_components.magic_areas.util import cleanup_removed_entries

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ["magic_areas"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the area cover config entry."""

    area: MagicArea | None = get_area_from_config_entry(hass, config_entry)
    assert area is not None

    # Check feature availability
    if not area.has_feature(Features.COVER_GROUPS):
        return

    # Check if there are any covers
    if not area.has_entities(COVER_DOMAIN):
        _LOGGER.debug("No %s entities for area %s", COVER_DOMAIN, area.name)
        return

    entities_to_add = []

    # Append None to the list of device classes to catch those covers that
    # don't have a device class assigned (and put them in their own group)
    for device_class in [*COVER_DEVICE_CLASSES, None]:
        covers_in_device_class = [
            e["entity_id"]
            for e in area.entities[COVER_DOMAIN]
            if e.get("device_class") == device_class
        ]

        if any(covers_in_device_class):
            _LOGGER.debug(
                "Creating %s cover group for %s with covers: %s",
                device_class,
                area.name,
                covers_in_device_class,
            )
            entities_to_add.append(AreaCoverGroup(area, device_class))

    if entities_to_add:
        async_add_entities(entities_to_add)

    if COVER_DOMAIN in area.magic_entities:
        cleanup_removed_entries(
            area.hass, entities_to_add, area.magic_entities[COVER_DOMAIN]
        )


class AreaCoverGroup(MagicEntity, CoverGroup):
    """Cover group for handling all the covers in the area."""

    feature_info = MagicAreasFeatureInfoCoverGroups()

    def __init__(self, area: MagicArea, device_class: str) -> None:
        """Initialize the cover group."""
        MagicEntity.__init__(
            self, area, domain=COVER_DOMAIN, translation_key=device_class
        )
        sensor_device_class: CoverDeviceClass | None = (
            CoverDeviceClass(device_class) if device_class else None
        )
        self._attr_device_class = sensor_device_class
        self._entities = [
            e
            for e in area.entities[COVER_DOMAIN]
            if e.get("device_class") == device_class
        ]
        CoverGroup.__init__(
            self,
            entities=[e["entity_id"] for e in self._entities],
            name=EMPTY_STRING,
            unique_id=self._attr_unique_id,
        )
        delattr(self, "_attr_name")
