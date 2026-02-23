"""Tests for wasp in a box feature handler."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock

import voluptuous

from custom_components.magic_areas.config_flow.helpers import SelectorBuilder
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
from custom_components.magic_areas.config_flow.features.wasp_in_a_box import (
    WaspInABoxFeature,
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
from custom_components.magic_areas.const.wasp_in_a_box import WaspInABoxOptions

from tests.const import DEFAULT_MOCK_AREA, MOCK_AREAS, MockAreaIds
from tests.helpers import get_basic_config_entry_data, init_integration
from tests.mocks import MockBinarySensor, MockLight, MockMediaPlayer


class TestWaspInABoxFeature:
    """Test WaspInABoxFeature class."""

    @pytest.fixture
    async def wasp_in_a_box_feature_setup(
        self, hass: HomeAssistant
    ) -> AsyncGenerator[dict, None]:
        """Set up wasp in a box feature for testing."""
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

        # Create feature handler
        handler = WaspInABoxFeature(flow)

        yield {
            "hass": hass,
            "config_entry": config_entry,
            "magic_area": magic_area,
            "flow": flow,
            "handler": handler,
        }

    def test_feature_properties(self, wasp_in_a_box_feature_setup):
        """Test feature properties."""
        handler = wasp_in_a_box_feature_setup["handler"]

        assert handler.feature_id == WaspInABoxOptions.FEATURE_KEY
        assert handler.feature_name == "Wasp in a Box"
        assert handler.is_available is True
        assert handler.requires_configuration is True

    def test_get_summary_no_config(self, wasp_in_a_box_feature_setup):
        """Test getting summary with no configuration."""
        handler = wasp_in_a_box_feature_setup["handler"]

        summary = handler.get_summary({})
        assert summary == "Not configured"

    def test_get_summary_with_config(self, wasp_in_a_box_feature_setup):
        """Test getting summary with configuration."""
        handler = wasp_in_a_box_feature_setup["handler"]
        config_entry = wasp_in_a_box_feature_setup["config_entry"]

        # Set up config
        test_config = {
            WaspInABoxOptions.WASP_TIMEOUT.key: 300,
        }
        config_entry.options[ConfigDomains.FEATURES] = {
            WaspInABoxOptions.FEATURE_KEY: test_config
        }

        summary = handler.get_summary(test_config)
        assert "300" in summary

    async def test_handle_step_main_no_input(self, wasp_in_a_box_feature_setup):
        """Test handling main step without input."""
        handler = wasp_in_a_box_feature_setup["handler"]

        result = await handler.handle_step("main", None)

        assert result.type == "form"
        assert result.step_id == "main"
        assert result.data_schema is not None

    async def test_handle_step_main_with_input(self, wasp_in_a_box_feature_setup):
        """Test handling main step with input."""
        handler = wasp_in_a_box_feature_setup["handler"]
        config_entry = wasp_in_a_box_feature_setup["config_entry"]

        # Test with valid input
        user_input = {
            WaspInABoxOptions.WASP_TIMEOUT.key: 300,
        }

        result = await handler.handle_step("main", user_input)

        assert result.type == "create_entry"
        assert ConfigDomains.FEATURES in config_entry.options
        assert (
            WaspInABoxOptions.FEATURE_KEY
            in config_entry.options[ConfigDomains.FEATURES]
        )
        assert (
            config_entry.options[ConfigDomains.FEATURES][WaspInABoxOptions.FEATURE_KEY]
            == user_input
        )

    def test_auto_generated_schema(self, wasp_in_a_box_feature_setup):
        """Test that schema is auto-generated from metadata."""
        handler = wasp_in_a_box_feature_setup["handler"]

        # Get current feature config
        feature_config = handler.get_config()

        # Auto-generate schema - wasp in a box options are in metadata!
        from custom_components.magic_areas.config_flow.helpers import SchemaBuilder

        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(WaspInABoxOptions)

        assert schema is not None
        assert isinstance(schema, voluptuous.Schema)

    def test_options_in_metadata(self, wasp_in_a_box_feature_setup):
        """Test that wasp in a box options are properly defined in metadata."""
        # This test verifies that the wasp in a box options are available in the metadata
        # and can be used for auto-generation

        assert hasattr(WaspInABoxOptions, "WASP_TIMEOUT")

        # The metadata should contain the options
        timeout_option = WaspInABoxOptions.WASP_TIMEOUT

        assert hasattr(timeout_option, "key")
        assert hasattr(timeout_option, "default")
        assert hasattr(timeout_option, "title")
        assert hasattr(timeout_option, "description")

        # Verify the keys are correct
        assert timeout_option.key == "wasp_timeout"

    def test_full_auto_generation(self, wasp_in_a_box_feature_setup):
        """Test that the feature is fully auto-generated with no overrides."""
        handler = wasp_in_a_box_feature_setup["handler"]

        # Get current feature config
        feature_config = handler.get_config()

        # Auto-generate base selectors
        from custom_components.magic_areas.config_flow.helpers import SelectorBuilder

        selectors = SelectorBuilder.from_option_set(WaspInABoxOptions)

        # Auto-generate schema with no overrides (fully auto-generated)
        from custom_components.magic_areas.config_flow.helpers import SchemaBuilder

        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(
            WaspInABoxOptions, selector_overrides=selectors
        )

        assert schema is not None
        assert isinstance(schema, voluptuous.Schema)

        # Verify that all selectors were auto-generated
        assert len(selectors) > 0

    def test_no_selective_overrides_needed(self, wasp_in_a_box_feature_setup):
        """Test that no selective overrides are needed for wasp in a box feature."""
        handler = wasp_in_a_box_feature_setup["handler"]

        # Get auto-generated selectors
        selectors = SelectorBuilder.from_option_set(WaspInABoxOptions)

        # Verify that all selectors are auto-generated
        assert len(selectors) > 0

        # For wasp in a box feature, all selectors should be auto-generated
        # No manual overrides should be needed
        assert all(selector is not None for selector in selectors.values())
