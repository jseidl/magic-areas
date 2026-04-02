"""Platform file for Magic Area's switch entities."""

import logging

from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    Features,
    MagicAreasFeatureInfoLightGroups,
)
from custom_components.magic_areas.helpers.area import get_area_from_config_entry
from custom_components.magic_areas.switch.base import SwitchBase
from custom_components.magic_areas.switch.climate_control import ClimateControlSwitch
from custom_components.magic_areas.switch.fan_control import FanControlSwitch
from custom_components.magic_areas.switch.media_player_control import (
    MediaPlayerControlSwitch,
)
from custom_components.magic_areas.switch.presence_hold import PresenceHoldSwitch
from custom_components.magic_areas.util import cleanup_removed_entries

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the area switch config entry."""

    area: MagicArea | None = get_area_from_config_entry(hass, config_entry)
    assert area is not None

    switch_entities = []

    # Setup each feature
    _setup_presence_hold(area, switch_entities)
    _setup_light_control(area, switch_entities)
    _setup_media_player_control(area, switch_entities)
    _setup_fan_control(area, switch_entities)
    _setup_climate_control(area, switch_entities)

    if switch_entities:
        async_add_entities(switch_entities)

    if SWITCH_DOMAIN in area.magic_entities:
        cleanup_removed_entries(
            area.hass, switch_entities, area.magic_entities[SWITCH_DOMAIN]
        )


def _setup_presence_hold(area: MagicArea, switch_entities: list) -> None:
    """Initialize presence hold switch."""
    if not area.has_feature(Features.PRESENCE_HOLD):
        return

    if area.is_meta():
        return

    try:
        switch_entities.append(PresenceHoldSwitch(area))
    except Exception as e:  # pylint: disable=broad-exception-caught
        _LOGGER.error("%s: Error loading presence hold switch: %s", area.name, str(e))


def _setup_light_control(area: MagicArea, switch_entities: list) -> None:
    """Initialize light control switch."""
    if not area.has_feature(Features.LIGHT_GROUPS):
        return

    if area.is_meta():
        return

    try:
        switch_entities.append(LightControlSwitch(area))
    except Exception as e:  # pylint: disable=broad-exception-caught
        _LOGGER.error("%s: Error loading light control switch: %s", area.name, str(e))


def _setup_media_player_control(area: MagicArea, switch_entities: list) -> None:
    """Initialize media player control switch."""
    if not area.has_feature(Features.MEDIA_PLAYER_GROUPS):
        return

    if area.is_meta():
        return

    try:
        switch_entities.append(MediaPlayerControlSwitch(area))
    except Exception as e:  # pylint: disable=broad-exception-caught
        _LOGGER.error(
            "%s: Error loading media player control switch: %s", area.name, str(e)
        )


def _setup_fan_control(area: MagicArea, switch_entities: list) -> None:
    """Initialize fan control switch."""
    if not area.has_feature(Features.FAN_GROUPS):
        return

    if area.is_meta():
        return

    # Check aggregates dependency
    if not area.has_feature(Features.AGGREGATION):
        _LOGGER.warning(
            "%s: Fan Groups feature requires Aggregates feature to be enabled. "
            "Please enable Aggregates in the area configuration.",
            area.name,
        )
        return

    try:
        switch_entities.append(FanControlSwitch(area))
    except Exception as e:  # pylint: disable=broad-exception-caught
        _LOGGER.error("%s: Error loading fan control switch: %s", area.name, str(e))


def _setup_climate_control(area: MagicArea, switch_entities: list) -> None:
    """Initialize climate control switch."""
    if not area.has_feature(Features.CLIMATE_CONTROL):
        return

    try:
        switch_entities.append(ClimateControlSwitch(area))
    except Exception as e:  # pylint: disable=broad-exception-caught
        _LOGGER.error("%s: Error loading climate control switch: %s", area.name, str(e))


class LightControlSwitch(SwitchBase):
    """Switch to enable/disable light control."""

    feature_info = MagicAreasFeatureInfoLightGroups()
    _attr_entity_category = EntityCategory.CONFIG
