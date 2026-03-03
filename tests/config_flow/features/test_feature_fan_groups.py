"""Tests for fan groups feature handler."""

from collections.abc import AsyncGenerator
from unittest.mock import Mock

import pytest
import voluptuous

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import async_get as async_get_ar

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.config_flow.features.fan_groups import (
    FanGroupsFeature,
)
from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler
from custom_components.magic_areas.config_flow.helpers import (
    SchemaBuilder,
    SelectorBuilder,
    StateOptionsBuilder,
)
from custom_components.magic_areas.const import (
    AreaConfigOptions,
    AreaStates,
    AreaType,
    ConfigDomains,
    ConfigHelper,
)
from custom_components.magic_areas.const.fan_groups import FanGroupOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import get_basic_config_entry_data, setup_mock_entities
from tests.mocks import MockBinarySensor, MockLight, MockMediaPlayer


class TestFanGroupsFeature:
    """Test FanGroupsFeature class."""

    @pytest.fixture
    async def fan_groups_feature_setup(
        self, hass: HomeAssistant
    ) -> AsyncGenerator[dict, None]:
        """Set up fan groups feature for testing."""
        # Setup area and entities
        area_registry = async_get_ar(hass)

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

        # Create area config dict with proper structure
        area_config_data = {
            ConfigDomains.AREA: {
                AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
                AreaConfigOptions.EXCLUDE_ENTITIES.key: [],
                AreaConfigOptions.INCLUDE_ENTITIES.key: [],
            }
        }

        # Create MagicArea with real ConfigHelper
        magic_area = Mock(spec=MagicArea)
        magic_area.id = DEFAULT_MOCK_AREA.value
        magic_area.name = DEFAULT_MOCK_AREA.value
        magic_area.config = ConfigHelper(area_config_data)
        magic_area.secondary_state_entities = {}
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

        # Create feature handler
        handler = FanGroupsFeature(flow)

        yield {
            "hass": hass,
            "config_entry": config_entry,
            "magic_area": magic_area,
            "flow": flow,
            "handler": handler,
            "area_config_data": area_config_data,
        }

    def test_feature_properties(self, fan_groups_feature_setup):
        """Test feature properties."""
        handler = fan_groups_feature_setup["handler"]

        assert handler.feature_id == "fan_groups"
        assert handler.feature_name == "Fan Groups"
        assert handler.is_available is True
        assert handler.requires_configuration is True

    def test_is_available_meta_area(self, fan_groups_feature_setup):
        """Test that fan groups are not available for meta areas."""
        handler = fan_groups_feature_setup["handler"]
        area_config_data = fan_groups_feature_setup["area_config_data"]

        # Test with meta area
        area_config_data[ConfigDomains.AREA][AreaConfigOptions.TYPE.key] = AreaType.META
        assert handler.is_available is False

        # Test with regular area
        area_config_data[ConfigDomains.AREA][
            AreaConfigOptions.TYPE.key
        ] = AreaType.INTERIOR
        assert handler.is_available is True

    def test_get_summary_no_config(self, fan_groups_feature_setup):
        """Test getting summary with no configuration."""
        handler = fan_groups_feature_setup["handler"]

        summary = handler.get_summary({})
        assert summary == "Not configured"

    def test_get_summary_with_config(self, fan_groups_feature_setup):
        """Test getting summary with configuration."""
        handler = fan_groups_feature_setup["handler"]
        config_entry = fan_groups_feature_setup["config_entry"]

        # Set up config
        test_config = {
            FanGroupOptions.REQUIRED_STATE.key: AreaStates.OCCUPIED,
            FanGroupOptions.TRACKED_DEVICE_CLASS.key: "temperature",
            FanGroupOptions.SETPOINT.key: 24.0,
        }
        config_entry.options[ConfigDomains.FEATURES] = {"fan_groups": test_config}

        summary = handler.get_summary(test_config)
        assert "State:" in summary
        assert "temperature" in summary
        assert "24.0" in summary

    async def test_handle_step_main_no_input(self, fan_groups_feature_setup):
        """Test handling main step without input."""
        handler = fan_groups_feature_setup["handler"]

        result = await handler.handle_step("main", None)

        assert result.type == "form"
        assert result.step_id == "main"
        assert result.data_schema is not None

    async def test_handle_step_main_with_input(self, fan_groups_feature_setup):
        """Test handling main step with input."""
        handler = fan_groups_feature_setup["handler"]
        config_entry = fan_groups_feature_setup["config_entry"]

        # Test with valid input
        user_input = {
            FanGroupOptions.REQUIRED_STATE.key: AreaStates.OCCUPIED,
            FanGroupOptions.TRACKED_DEVICE_CLASS.key: "temperature",
            FanGroupOptions.SETPOINT.key: 24.0,
        }

        result = await handler.handle_step("main", user_input)

        assert result.type == "create_entry"
        assert ConfigDomains.FEATURES in config_entry.options
        assert "fan_groups" in config_entry.options[ConfigDomains.FEATURES]
        assert config_entry.options[ConfigDomains.FEATURES]["fan_groups"] == user_input

    def test_auto_generated_schema_with_state_selector_override(
        self, fan_groups_feature_setup
    ):
        """Test that schema is auto-generated with state selector override."""
        handler = fan_groups_feature_setup["handler"]

        # Get current feature config
        feature_config = handler.get_config()

        # Auto-generate base selectors
        selectors = SelectorBuilder.from_option_set(FanGroupOptions)

        # Override: Dynamic state options (only occupied/extended for fans)
        available_states = StateOptionsBuilder.for_fan_groups()
        selectors[FanGroupOptions.REQUIRED_STATE.key] = (
            handler.flow.build_selector_select(available_states)
        )

        # Auto-generate schema with overrides
        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(FanGroupOptions, selector_overrides=selectors)

        assert schema is not None
        assert isinstance(schema, voluptuous.Schema)

    def test_state_selector_override(self, fan_groups_feature_setup):
        """Test that state selector is properly overridden."""
        handler = fan_groups_feature_setup["handler"]

        # Verify that state selector can be overridden
        state_selector = handler.flow.build_selector_select(
            [AreaStates.OCCUPIED, AreaStates.EXTENDED]
        )
        assert state_selector is not None

        available_states = StateOptionsBuilder.for_fan_groups()
        assert AreaStates.OCCUPIED in available_states
        assert AreaStates.EXTENDED in available_states
        assert AreaStates.DARK not in available_states
        assert AreaStates.SLEEP not in available_states

    def test_metadata_driven_configuration(self, fan_groups_feature_setup):
        """Test that configuration is driven by metadata."""
        # This test verifies that the feature uses the metadata from FanGroupOptions
        # rather than hard-coded configuration

        assert hasattr(FanGroupOptions, "REQUIRED_STATE")
        assert hasattr(FanGroupOptions, "TRACKED_DEVICE_CLASS")
        assert hasattr(FanGroupOptions, "SETPOINT")

        # Verify that these options have the expected metadata
        required_state_option = FanGroupOptions.REQUIRED_STATE
        tracked_device_class_option = FanGroupOptions.TRACKED_DEVICE_CLASS
        setpoint_option = FanGroupOptions.SETPOINT

        assert required_state_option.key == "required_state"
        assert tracked_device_class_option.key == "tracked_device_class"
        assert setpoint_option.key == "setpoint"

    def test_area_type_filtering(self, fan_groups_feature_setup):
        """Test that fan groups are properly filtered by area type."""
        handler = fan_groups_feature_setup["handler"]
        area_config_data = fan_groups_feature_setup["area_config_data"]

        # Test with different area types
        test_area_types = [
            AreaType.INTERIOR,
            AreaType.EXTERIOR,
            AreaType.META,
        ]

        for area_type in test_area_types:
            area_config_data[ConfigDomains.AREA][AreaConfigOptions.TYPE.key] = area_type

            # Fan groups should only be available for non-meta areas
            if area_type == AreaType.META:
                assert handler.is_available is False
            else:
                assert handler.is_available is True
