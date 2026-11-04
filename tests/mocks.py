"""Fake light for testing with."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import cached_property
import logging
from typing import Any, Final, Literal
from unittest.mock import AsyncMock

import voluptuous as vol

from homeassistant import data_entry_flow, loader
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    PRESET_SLEEP,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_PLAYING,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry, DeviceInfo
from homeassistant.helpers.entity import Entity, ToggleEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

TURN_ON_ARG_TO_COLOR_MODE = {
    "hs_color": ColorMode.HS,
    "xy_color": ColorMode.XY,
    "rgb_color": ColorMode.RGB,
    "rgbw_color": ColorMode.RGBW,
    "rgbww_color": ColorMode.RGBWW,
    "color_temp_kelvin": ColorMode.COLOR_TEMP,
}

# If no name is specified
DEVICE_DEFAULT_NAME: Final = "Unnamed Device"


class MockEntity(Entity):
    """Mock Entity class."""

    def __init__(self, **values: Any) -> None:
        """Initialize an entity."""
        self._values = values

        if "entity_id" in values:
            self.entity_id = values["entity_id"]

    @cached_property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._handle("available")

    @property
    def capability_attributes(self) -> dict[str, Any] | None:  # type: ignore
        """Info about capabilities."""
        return self._handle("capability_attributes")

    @cached_property
    def device_class(self) -> str | None:
        """Info how device should be classified."""
        return self._handle("device_class")

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Info how it links to a device."""
        return self._handle("device_info")

    @cached_property
    def entity_category(self) -> EntityCategory | None:
        """Return the entity category."""
        return self._handle("entity_category")

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        return self._handle("extra_state_attributes")

    @cached_property
    def has_entity_name(self) -> bool:
        """Return the has_entity_name name flag."""
        return self._handle("has_entity_name")

    @cached_property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._handle("entity_registry_enabled_default")

    @cached_property
    def entity_registry_visible_default(self) -> bool:
        """Return if the entity should be visible when first added to the entity registry."""
        return self._handle("entity_registry_visible_default")

    @cached_property
    def icon(self) -> str | None:
        """Return the suggested icon."""
        return self._handle("icon")

    @cached_property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._handle("name")

    @cached_property
    def should_poll(self) -> bool:
        """Return the ste of the polling."""
        return self._handle("should_poll")

    @cached_property
    def supported_features(self) -> int | None:
        """Info about supported features."""
        return self._handle("supported_features")

    @cached_property
    def translation_key(self) -> str | None:
        """Return the translation key."""
        return self._handle("translation_key")

    @cached_property
    def unique_id(self) -> str | None:
        """Return the unique ID of the entity."""
        return self._handle("unique_id")

    @cached_property
    def unit_of_measurement(self) -> str | None:
        """Info on the units the entity state is in."""
        return self._handle("unit_of_measurement")

    def _handle(self, attr: str) -> Any:
        """Return attribute value."""
        if attr in self._values:
            return self._values[attr]
        return getattr(super(), attr)


class MockModule:
    """Representation of a fake module."""

    def __init__(
        self,
        domain: str,
        *,
        dependencies: list[str] | None = None,
        setup: Callable[[], data_entry_flow.FlowHandler] | None = None,
        requirements: list[str] | None = None,
        config_schema: vol.Schema | None = None,
        platform_schema: vol.Schema | None = None,
        platform_schema_base: vol.Schema | None = None,
        async_setup: Callable[[], Awaitable[data_entry_flow.FlowHandler]] | None = None,
        async_setup_entry: (
            Callable[[HomeAssistant, ConfigEntry, AddEntitiesCallback], Awaitable[None]]
            | None
        ) = None,
        async_unload_entry: (
            Callable[[HomeAssistant, ConfigEntry], Awaitable[bool]] | None
        ) = None,
        async_migrate_entry: (
            Callable[[HomeAssistant, ConfigEntry], Awaitable[bool]] | None
        ) = None,
        async_remove_entry: (
            Callable[[HomeAssistant, ConfigEntry], Awaitable[bool]] | None
        ) = None,
        partial_manifest: dict[str, str] | None = None,
        async_remove_config_entry_device: (
            Callable[[HomeAssistant, ConfigEntry, DeviceEntry], Awaitable[bool]] | None
        ) = None,
    ) -> None:
        """Initialize the mock module."""
        self.__name__ = f"homeassistant.components.{domain}"
        self.__file__ = f"homeassistant/components/{domain}"
        self.DOMAIN = domain  # pylint: disable=invalid-name
        self.DEPENDENCIES = dependencies or []  # pylint: disable=invalid-name
        self.REQUIREMENTS = requirements or []  # pylint: disable=invalid-name
        # Overlay to be used when generating manifest from this module
        self._partial_manifest = partial_manifest

        if config_schema is not None:
            self.CONFIG_SCHEMA = config_schema  # pylint: disable=invalid-name

        if platform_schema is not None:
            self.PLATFORM_SCHEMA = platform_schema  # pylint: disable=invalid-name

        if platform_schema_base is not None:
            # pylint: disable-next=invalid-name
            self.PLATFORM_SCHEMA_BASE = platform_schema_base

        if setup:
            # We run this in executor, wrap it in function
            # pylint: disable-next=unnecessary-lambda
            self.setup: Callable[[], data_entry_flow.FlowHandler] = lambda: setup()

        if async_setup is not None:
            self.async_setup = async_setup

        if setup is None and async_setup is None:
            self.async_setup = AsyncMock(return_value=True)

        if async_setup_entry is not None:
            self.async_setup_entry = async_setup_entry

        if async_unload_entry is not None:
            self.async_unload_entry = async_unload_entry

        if async_migrate_entry is not None:
            self.async_migrate_entry = async_migrate_entry

        if async_remove_entry is not None:
            self.async_remove_entry = async_remove_entry

        if async_remove_config_entry_device is not None:
            self.async_remove_config_entry_device = async_remove_config_entry_device

    def mock_manifest(self):
        """Generate a mock manifest to represent this module."""
        return {
            **loader.manifest_from_legacy_module(self.DOMAIN, self),
            **(self._partial_manifest or {}),
        }


class MockPlatform:
    """Provide a fake platform."""

    __name__ = "homeassistant.components.light.bla"
    __file__ = "homeassistant/components/blah/light"

    def __init__(
        self,
        *,
        setup_platform: (
            Callable[
                [
                    HomeAssistant,
                    ConfigType,
                    AddEntitiesCallback,
                    DiscoveryInfoType | None,
                ],
                None,
            ]
            | None
        ) = None,
        dependencies: list[str] | None = None,
        platform_schema: vol.Schema | None = None,
        async_setup_platform: (
            Callable[
                [
                    HomeAssistant,
                    ConfigType,
                    AddEntitiesCallback,
                    DiscoveryInfoType | None,
                ],
                Awaitable[None],
            ]
            | None
        ) = None,
        async_setup_entry: (
            Callable[[HomeAssistant, ConfigEntry, AddEntitiesCallback], Awaitable[None]]
            | None
        ) = None,
        scan_interval: int | None = None,
    ) -> None:
        """Initialize the platform."""
        # pylint: disable-next=invalid-name
        self.DEPENDENCIES = dependencies or []

        if platform_schema is not None:
            self.PLATFORM_SCHEMA = platform_schema  # pylint: disable=invalid-name

        if scan_interval is not None:
            self.SCAN_INTERVAL = scan_interval  # pylint: disable=invalid-name

        if setup_platform is not None:
            # We run this in executor, wrap it in function
            self.setup_platform = setup_platform

        if async_setup_platform is not None:
            self.async_setup_platform = async_setup_platform

        if async_setup_entry is not None:
            self.async_setup_entry = async_setup_entry

        if setup_platform is None and async_setup_platform is None:
            self.async_setup_platform = AsyncMock(return_value=None)


class MockToggleEntity(MockEntity, ToggleEntity):
    """Provide a mock toggle device."""

    def __init__(self, name: str, state: str, unique_id: str | None = None) -> None:
        """Initialize the mock entity."""
        MockEntity.__init__(self)
        ToggleEntity.__init__(self)
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self._attr_unique_id = unique_id
        self.calls: list[tuple[str, dict[str, Any]]] = []

    @cached_property
    def name(self) -> str:
        """Return the name of the entity if any."""
        self.calls.append(("name", {}))
        return self._name

    @property
    # pylint: disable-next=overridden-final-method
    def state(
        self,
    ) -> Literal["on", "off"] | None:
        """Return the state of the entity if any."""
        self.calls.append(("state", {}))
        return self._state

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        self.calls.append(("is_on", {}))
        return self._state == STATE_ON

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.calls.append(("turn_on", kwargs))
        self._state = STATE_ON

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.calls.append(("turn_off", kwargs))
        self._state = STATE_OFF

    def last_call(self, method: str | None = None) -> tuple[str, dict[str, Any]] | None:
        """Return the last call."""
        if not self.calls:
            return None
        if method is None:
            return self.calls[-1]
        try:
            return next(call for call in reversed(self.calls) if call[0] == method)
        except StopIteration:
            return None


class MockLight(MockToggleEntity, LightEntity):
    """Mock light class."""

    _attr_max_color_temp_kelvin = 6500
    _attr_min_color_temp_kelvin = 2000

    def __init__(
        self,
        name: str,
        state: str,
        unique_id: str | None = None,
        dimmable: bool | None = None,
    ) -> None:
        """Initialize the mock light."""
        super().__init__(name, state, unique_id)
        if dimmable:
            self._attr_supported_color_modes = {ColorMode.RGBWW}
            self._attr_color_mode = ColorMode.RGBWW
            self._attr_brightness = 255
            self.hs_color = None  # Should be ignored
            self.rgb_color = None  # Should be ignored
            self.rgbw_color = None  # Should be ignored
            self.rgbww_color = (1, 2, 3, 4, 5)
            self.xy_color = None  # Should be ignored
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        super().turn_on(**kwargs)
        for key, value in kwargs.items():
            if key == "brightness":
                self._attr_brightness = value
            elif key in [
                "hs_color",
                "xy_color",
                "rgb_color",
                "rgbw_color",
                "rgbww_color",
                "color_temp_kelvin",
            ]:
                setattr(self, key, value)
            if key == "white":
                self._attr_brightness = value
            if key in TURN_ON_ARG_TO_COLOR_MODE:
                self._attr_color_mode = TURN_ON_ARG_TO_COLOR_MODE[key]
        self.schedule_update_ha_state()


class MockBinarySensor(MockEntity, BinarySensorEntity):
    """Mock Binary Sensor class."""

    _state = STATE_OFF

    @property
    def is_on(self) -> bool:  # pylint: disable=overridden-final-method
        """Return true if the binary sensor is on."""
        return self._state == STATE_ON

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._state = STATE_ON
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._state = STATE_OFF
        self.schedule_update_ha_state()

    @cached_property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the class of this sensor."""
        return self._handle("device_class")


class MockFan(MockEntity, FanEntity):
    """Mock Binary Sensor class."""

    _state = STATE_OFF
    _attr_supported_features: FanEntityFeature = (
        FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state == STATE_ON

    # pylint: disable-next=arguments-differ
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._state = STATE_ON
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._state = STATE_OFF
        self.schedule_update_ha_state()


class MockSensor(MockEntity, SensorEntity):
    """Mock Sensor class."""

    @cached_property
    def device_class(self) -> SensorDeviceClass:
        """Return the class of this sensor."""
        return self._handle("device_class")

    @cached_property
    def last_reset(self) -> datetime:
        """Return the last_reset of this sensor."""
        return self._handle("last_reset")

    @cached_property
    def suggested_display_precision(self) -> int:
        """Return the number of digits after the decimal point."""
        return self._handle("suggested_display_precision")

    @cached_property
    def native_unit_of_measurement(self) -> str:
        """Return the native unit_of_measurement of this sensor."""
        return self._handle("native_unit_of_measurement")

    @cached_property
    def native_value(self) -> Any:
        """Return the native value of this sensor."""
        return self._handle("native_value")

    @cached_property
    def options(self) -> list[str]:
        """Return the options for this sensor."""
        return self._handle("options")

    @cached_property
    def state_class(self) -> str:
        """Return the state class of this sensor."""
        return self._handle("state_class")

    @cached_property
    def suggested_unit_of_measurement(self) -> str:
        """Return the state class of this sensor."""
        return self._handle("suggested_unit_of_measurement")

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""

        await super().async_added_to_hass()
        self.async_write_ha_state()


class MockCover(MockEntity, CoverEntity):
    """Mock Cover class."""

    _reports_opening_closing = False

    @property
    def supported_features(
        self,
    ) -> CoverEntityFeature:  # pylint: disable=overridden-final-method
        """Return the supported features of the cover."""
        if "supported_feautes" in self._values:
            return self._values["supported_features"]
        return CoverEntity.supported_features.fget(
            self
        )  # pylint: disable=overridden-final-method

    @cached_property
    def is_closed(self) -> bool:
        """Return if the cover is closed or not."""
        if "state" in self._values and self._values["state"] == STATE_CLOSED:
            return True

        return self.current_cover_position == 0

    @cached_property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        if "state" in self._values:
            return self._values["state"] == STATE_OPENING

        return False

    @cached_property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        if "state" in self._values:
            return self._values["state"] == STATE_CLOSING

        return False

    def open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        if self._reports_opening_closing:
            self._values["state"] = STATE_OPENING
        else:
            self._values["state"] = STATE_OPEN

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        if self._reports_opening_closing:
            self._values["state"] = STATE_CLOSING
        else:
            self._values["state"] = STATE_CLOSED

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop cover."""
        assert CoverEntityFeature.STOP in self.supported_features
        self._values["state"] = STATE_CLOSED if self.is_closed else STATE_OPEN

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""

        await super().async_added_to_hass()
        self.async_write_ha_state()


class MockMediaPlayer(MockEntity, MediaPlayerEntity):
    """Mock Media Player class."""

    _attr_state = STATE_OFF

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._attr_state == STATE_ON

    # pylint: disable-next=arguments-differ
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._attr_state = STATE_ON
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_state = STATE_OFF
        self.schedule_update_ha_state()

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return (
            MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.TURN_OFF
        )

    def play_media(self, media_type, media_id, **kwargs):
        """Handle play service calls."""
        self._attr_state = STATE_PLAYING
        self.schedule_update_ha_state()
        return True

    def media_stop(self):
        """Handle stop service calls."""
        self._attr_state = STATE_IDLE
        self.schedule_update_ha_state()
        return True


class MockClimate(MockEntity, ClimateEntity):
    """Mock Climate class."""

    _attr_state = STATE_OFF
    _attr_hvac_mode = HVACMode.OFF
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT_COOL, HVACMode.OFF]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature = 70
    _attr_current_temperature = 70
    _attr_supported_features = (
        ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = [
        PRESET_NONE,
        PRESET_HOME,
        PRESET_AWAY,
        PRESET_SLEEP,
        PRESET_ECO,
    ]
    _attr_preset_mode = PRESET_NONE

    def __init__(
        self,
        name: str,
        unique_id: str | None = None,
        preset_modes: list[str] | None = None,
    ) -> None:
        """Initialize the mock climate."""
        super().__init__()
        self._attr_name = name
        self._attr_unique_id = unique_id
        if preset_modes is not None:
            self._attr_preset_modes = preset_modes

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        self._attr_preset_mode = preset_mode

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.set_hvac_mode(HVACMode.AUTO)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.set_hvac_mode(HVACMode.OFF)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""

        self._attr_hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            self._attr_state = STATE_OFF
        else:
            self._attr_state = STATE_ON
        self.schedule_update_ha_state()
