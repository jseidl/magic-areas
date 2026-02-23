"""Tests for config_flow.features.base module."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import async_get as async_get_ar
from homeassistant.helpers.entity_registry import async_get as async_get_er

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.config_flow.features.base import (
    FeatureHandler,
    StepResult,
)
from custom_components.magic_areas.config_flow.features.presence_hold import (
    PresenceHoldFeature,
)
from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler
from custom_components.magic_areas.const import (
    AreaConfigOptions,
    AreaStates,
    AreaType,
    CONF_AREA_ID,
    ConfigDomains,
    CONF_TYPE,
    DOMAIN,
)
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.area_aware_media_player import (
    AreaAwareMediaPlayerOptions,
)
from custom_components.magic_areas.const.ble_trackers import BleTrackerOptions
from custom_components.magic_areas.const.climate_control import ClimateControlOptions
from custom_components.magic_areas.const.fan_groups import FanGroupOptions
from custom_components.magic_areas.const.health import HealthOptions
from custom_components.magic_areas.const.light_groups import LightGroupOptions
from custom_components.magic_areas.const.presence_hold import PresenceHoldOptions
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions
from custom_components.magic_areas.const.wasp_in_a_box import WaspInABoxOptions

from tests.const import DEFAULT_MOCK_AREA, MOCK_AREAS, MockAreaIds
from tests.helpers import get_basic_config_entry_data, init_integration
from tests.mocks import MockBinarySensor, MockLight, MockMediaPlayer


class TestFeatureHandler:
    """Test FeatureHandler base class."""

    @pytest.fixture
    async def feature_handler_setup(
        self, hass: HomeAssistant
    ) -> AsyncGenerator[dict, None]:
        """Set up feature handler for testing."""
        # Setup area and entities
        area_registry = async_get_ar(hass)
        entity_registry = async_get_er(hass)

        if not area_registry.async_get_area_by_name(DEFAULT_MOCK_AREA.value):
            area_registry.async_create(name=DEFAULT_MOCK_AREA.value)

        # Create test entities
        test_entities = [
            MockBinarySensor(
                name="motion_sensor",
                unique_id="test_motion_sensor",
                device_class=BinarySensorDeviceClass.MOTION,
            ),
            MockLight(
                name="test_light",
                state="off",
                unique_id="test_light",
                dimmable=True,
            ),
            MockMediaPlayer(
                name="test_media_player",
                state="off",
                unique_id="test_media_player",
            ),
        ]

        from tests.helpers import setup_mock_entities

        await setup_mock_entities(
            hass,
            BINARY_SENSOR_DOMAIN,
            {DEFAULT_MOCK_AREA: [test_entities[0]]},
        )
        await setup_mock_entities(
            hass,
            LIGHT_DOMAIN,
            {DEFAULT_MOCK_AREA: [test_entities[1]]},
        )
        await setup_mock_entities(
            hass,
            MEDIA_PLAYER_DOMAIN,
            {DEFAULT_MOCK_AREA: [test_entities[2]]},
        )

        # Create config entry
        config_entry = Mock()
        config_entry.options = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

        # Create MagicArea
        magic_area = Mock(spec=MagicArea)
        magic_area.id = DEFAULT_MOCK_AREA.value
        magic_area.name = DEFAULT_MOCK_AREA.value
        magic_area.config = {
            AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
            AreaConfigOptions.EXCLUDE_ENTITIES.key: [],
            AreaConfigOptions.INCLUDE_ENTITIES.key: [],
        }
        magic_area.is_meta.return_value = False
        magic_area.get_presence_sensors.return_value = ["binary_sensor.motion_sensor"]

        # Create flow
        flow = Mock(spec=OptionsFlowHandler)
        flow.hass = hass
        flow.config_entry = config_entry
        flow.area = magic_area
        flow.area_options = config_entry.options
        flow.all_entities = ["binary_sensor.motion_sensor", "light.test_light"]
        flow.area_entities = ["binary_sensor.motion_sensor", "light.test_light"]
        flow.all_area_entities = ["binary_sensor.motion_sensor", "light.test_light"]
        flow.all_lights = ["light.test_light"]
        flow.all_media_players = ["media_player.test_media_player"]
        flow.all_binary_entities = ["binary_sensor.motion_sensor"]
        flow.all_light_tracking_entities = ["binary_sensor.motion_sensor"]

        # Create feature handler - use concrete implementation to test base class
        handler = PresenceHoldFeature(flow)

        yield {
            "hass": hass,
            "config_entry": config_entry,
            "magic_area": magic_area,
            "flow": flow,
            "handler": handler,
        }

    def test_feature_handler_initialization(self, feature_handler_setup):
        """Test FeatureHandler initialization via concrete implementation."""
        handler = feature_handler_setup["handler"]

        assert handler.flow == feature_handler_setup["flow"]
        assert handler.feature_id == "presence_hold"
        assert handler.feature_name == "Presence Hold"
        assert handler.is_available is True
        assert handler.requires_configuration is True
        assert handler._state == {}
        assert hasattr(handler, "_validator")

    def test_feature_handler_properties(self, feature_handler_setup):
        """Test FeatureHandler properties."""
        handler = feature_handler_setup["handler"]

        # Test property access
        assert handler.hass == feature_handler_setup["hass"]
        assert handler.area_options == feature_handler_setup["config_entry"].options
        assert handler.area == feature_handler_setup["magic_area"]
        assert handler.all_lights == ["light.test_light"]
        assert handler.all_entities == [
            "binary_sensor.motion_sensor",
            "light.test_light",
        ]
        assert handler.all_media_players == ["media_player.test_media_player"]
        assert handler.all_binary_entities == ["binary_sensor.motion_sensor"]

    def test_get_config(self, feature_handler_setup):
        """Test getting feature configuration."""
        handler = feature_handler_setup["handler"]
        config_entry = feature_handler_setup["config_entry"]

        # Test with no existing config
        config = handler.get_config()
        assert config == {}

        # Test with existing config
        config_entry.options[ConfigDomains.FEATURES] = {
            "presence_hold": {"test": "value"}
        }
        config = handler.get_config()
        assert config == {"test": "value"}

    def test_save_config(self, feature_handler_setup):
        """Test saving feature configuration."""
        handler = feature_handler_setup["handler"]
        config_entry = feature_handler_setup["config_entry"]

        # Test saving config
        test_config = {"test": "value", "number": 42}
        handler.save_config(test_config)

        assert ConfigDomains.FEATURES in config_entry.options
        assert "presence_hold" in config_entry.options[ConfigDomains.FEATURES]
        assert (
            config_entry.options[ConfigDomains.FEATURES]["presence_hold"] == test_config
        )

    def test_build_schema(self, feature_handler_setup):
        """Test building schema."""
        handler = feature_handler_setup["handler"]

        # Test with basic options
        options = [("field1", "default1", str), ("field2", "default2", int)]
        selectors = {"field1": Mock()}

        schema = handler.build_schema(options, selectors)
        assert schema is not None

    def test_cleanup(self, feature_handler_setup):
        """Test cleanup method."""
        handler = feature_handler_setup["handler"]
        handler._state = {"test": "value"}

        handler.cleanup()

        assert handler._state == {}

    def test_get_initial_step(self, feature_handler_setup):
        """Test getting initial step."""
        handler = feature_handler_setup["handler"]

        initial_step = handler.get_initial_step()
        assert initial_step == "main"

    def test_get_summary(self, feature_handler_setup):
        """Test getting summary via concrete implementation."""
        handler = feature_handler_setup["handler"]

        # Test with no config
        summary = handler.get_summary({})
        assert summary == "Not configured"

        # Test with presence_hold config (matching PresenceHoldFeature's expectations)
        from custom_components.magic_areas.const.presence_hold import (
            PresenceHoldOptions,
        )

        summary = handler.get_summary({PresenceHoldOptions.TIMEOUT.key: 300})
        assert "300" in summary  # PresenceHoldFeature includes timeout in summary

    async def test_handle_step_implemented(self, feature_handler_setup):
        """Test that concrete handler implements handle_step."""
        handler = feature_handler_setup["handler"]

        # PresenceHoldFeature implements handle_step, so it should work
        result = await handler.handle_step("main", None)

        # Should return a form result for configuration
        assert result.type == "form"
        assert result.step_id == "main"


class TestStepResult:
    """Test StepResult dataclass."""

    def test_step_result_creation(self):
        """Test creating StepResult instances."""
        # Test form result
        form_result = StepResult(
            type="form",
            step_id="main",
            data_schema=Mock(),
            errors={"field": "error"},
        )

        assert form_result.type == "form"
        assert form_result.step_id == "main"
        assert form_result.data_schema is not None
        assert form_result.errors == {"field": "error"}
        assert form_result.save_data is None

        # Test create_entry result
        create_result = StepResult(
            type="create_entry",
            save_data={"config": "value"},
        )

        assert create_result.type == "create_entry"
        assert create_result.save_data == {"config": "value"}
        assert create_result.step_id is None

        # Test menu result
        menu_result = StepResult(
            type="menu",
            menu_options=["option1", "option2"],
        )

        assert menu_result.type == "menu"
        assert menu_result.menu_options == ["option1", "option2"]
        assert menu_result.step_id is None

        # Test abort result
        abort_result = StepResult(
            type="abort",
            description_placeholders={"reason": "test"},
        )

        assert abort_result.type == "abort"
        assert abort_result.description_placeholders == {"reason": "test"}
        assert abort_result.step_id is None
