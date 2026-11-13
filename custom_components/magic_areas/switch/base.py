"""Base classes for switch."""

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.event import async_call_later

from custom_components.magic_areas.base.entities import MagicEntity
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import ONE_MINUTE


class SwitchBase(MagicEntity, SwitchEntity):
    """The base class for all the switches."""

    _attr_state: str

    def __init__(self, area: MagicArea) -> None:
        """Initialize the base switch bits, basic just a mixin for the two types."""
        MagicEntity.__init__(self, area, domain=SWITCH_DOMAIN)
        SwitchEntity.__init__(self)
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_should_poll = False
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Restore state
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_is_on = last_state.state == STATE_ON
            self._attr_extra_state_attributes = dict(last_state.attributes)

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on presence hold."""
        self._attr_state = STATE_ON
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off presence hold."""
        self._attr_state = STATE_OFF
        self._attr_is_on = False
        self.async_write_ha_state()


class ResettableSwitchBase(SwitchBase):
    """Control the presense/state from being changed for the device."""

    timeout: int

    def __init__(self, area: MagicArea, timeout: int = 0) -> None:
        """Initialize the switch."""
        super().__init__(area)

        self.timeout = timeout
        self._timeout_callback = None

        self.async_on_remove(self._clear_timers)

    def _clear_timers(self) -> None:
        """Remove the timer on entity removal."""
        if self._timeout_callback:
            self._timeout_callback()

    async def _timeout_turn_off(self, next_interval):
        """Turn off the presence hold after the timeout."""
        if self._attr_state == STATE_ON:
            await self.async_turn_off()

    async def async_turn_on(self, **kwargs):
        """Turn on presence hold."""
        self._attr_state = STATE_ON
        self._attr_is_on = True
        self.async_write_ha_state()

        if self.timeout and not self._timeout_callback:
            self._timeout_callback = async_call_later(
                self.hass, self.timeout * ONE_MINUTE, self._timeout_turn_off
            )

    async def async_turn_off(self, **kwargs):
        """Turn off presence hold."""
        self._attr_state = STATE_OFF
        self._attr_is_on = False
        self.async_write_ha_state()

        if self._timeout_callback:
            self._timeout_callback()
            self._timeout_callback = None
