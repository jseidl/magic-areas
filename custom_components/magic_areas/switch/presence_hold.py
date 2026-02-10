"""Presence hold switch."""

from homeassistant.const import EntityCategory

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import MagicAreasFeatureInfoPresenceHold
from custom_components.magic_areas.const.presence_hold import PresenceHoldOptions
from custom_components.magic_areas.switch.base import ResettableSwitchBase


class PresenceHoldSwitch(ResettableSwitchBase):
    """Switch to enable/disable presence hold."""

    feature_info = MagicAreasFeatureInfoPresenceHold()
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, area: MagicArea) -> None:
        """Initialize the switch."""

        timeout = area.config.get(PresenceHoldOptions.TIMEOUT)

        ResettableSwitchBase.__init__(self, area, timeout=timeout)
