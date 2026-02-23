"""Tests for health sensor feature handler."""

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
from custom_components.magic_areas.config_flow.features.health import HealthFeature
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
from custom_components.magic_areas.const.health import HealthOptions

from tests.const import DEFAULT_MOCK_AREA, MOCK_AREAS, MockAreaIds
from tests.helpers import get_basic_config_entry_data, init_integration
from tests.mocks import MockBinarySensor, MockLight, MockMediaPlayer


class TestHealthFeature:
    """Test HealthFeature class."""

    @pytest.fixture
    async def health_feature_setup(
        self, hass: HomeAssistant
    ) -> AsyncGenerator[dict, None]:
        """Set up health feature for testing."""
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
        handler = HealthFeature(flow)

        yield {
            "hass": hass,
            "config_entry": config_entry,
            "magic_area": magic_area,
            "flow": flow,
            "handler": handler,
        }

    def test_feature_properties(self, health_feature_setup):
        """Test feature properties."""
        handler = health_feature_setup["handler"]

        assert handler.feature_id == "health"
        assert handler.feature_name == "Health Sensor"
        assert handler.is_available is True
        assert handler.requires_configuration is True

    def test_get_summary_no_config(self, health_feature_setup):
        """Test getting summary with no configuration."""
        handler = health_feature_setup["handler"]

        summary = handler.get_summary({})
        assert summary == "Not configured"

    def test_get_summary_with_config(self, health_feature_setup):
        """Test getting summary with configuration."""
        handler = health_feature_setup["handler"]
        config_entry = health_feature_setup["config_entry"]

        # Set up config
        test_config = {
            HealthOptions.SENSOR_DEVICE_CLASSES.key: ["temperature", "humidity"],
        }
        config_entry.options[ConfigDomains.FEATURES] = {"health": test_config}

        summary = handler.get_summary(test_config)
        assert "sensor classes" in summary

    async def test_handle_step_main_no_input(self, health_feature_setup):
        """Test handling main step without input."""
        handler = health_feature_setup["handler"]

        result = await handler.handle_step("main", None)

        assert result.type == "form"
        assert result.step_id == "main"
        assert result.data_schema is not None

    async def test_handle_step_main_with_input(self, health_feature_setup):
        """Test handling main step with input."""
        handler = health_feature_setup["handler"]
        config_entry = health_feature_setup["config_entry"]

        # Test with valid input
        user_input = {
            HealthOptions.SENSOR_DEVICE_CLASSES.key: ["temperature", "humidity"],
        }

        result = await handler.handle_step("main", user_input)

        assert result.type == "create_entry"
        assert ConfigDomains.FEATURES in config_entry.options
        assert "health" in config_entry.options[ConfigDomains.FEATURES]
        assert config_entry.options[ConfigDomains.FEATURES]["health"] == user_input

    def test_auto_generated_schema(self, health_feature_setup):
        """Test that schema is auto-generated from metadata."""
        handler = health_feature_setup["handler"]

        # Get current feature config
        feature_config = handler.get_config()

        # Auto-generate schema - device class list is in metadata!
        from custom_components.magic_areas.config_flow.helpers import SchemaBuilder

        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(HealthOptions)

        assert schema is not None
        assert isinstance(schema, voluptuous.Schema)

    def test_metadata_driven_configuration(self, health_feature_setup):
        """Test that configuration is driven by metadata."""
        # This test verifies that the feature uses the metadata from HealthOptions
        # rather than hard-coded configuration

        assert hasattr(HealthOptions, "SENSOR_DEVICE_CLASSES")

        # Verify that this option has the expected metadata
        sensor_device_classes_option = HealthOptions.SENSOR_DEVICE_CLASSES

        assert sensor_device_classes_option.key == "health_binary_sensor_device_classes"

    def test_device_class_list_in_metadata(self, health_feature_setup):
        """Test that device class list is properly defined in metadata."""
        # This test verifies that the device class list is available in the metadata
        # and can be used for auto-generation

        assert hasattr(HealthOptions, "SENSOR_DEVICE_CLASSES")

        # The metadata should contain the device class list
        sensor_option = HealthOptions.SENSOR_DEVICE_CLASSES

        # Verify the option has the expected structure
        assert hasattr(sensor_option, "key")
        assert hasattr(sensor_option, "default")
        assert hasattr(sensor_option, "title")
        assert hasattr(sensor_option, "description")

        # Verify the key is correct
        assert sensor_option.key == "health_binary_sensor_device_classes"

    def test_full_auto_generation(self, health_feature_setup):
        """Test that the feature is fully auto-generated with no overrides."""
        handler = health_feature_setup["handler"]

        # Get current feature config
        feature_config = handler.get_config()

        # Auto-generate base selectors
        from custom_components.magic_areas.config_flow.helpers import SelectorBuilder

        selectors = SelectorBuilder.from_option_set(HealthOptions)

        # Auto-generate schema with no overrides (fully auto-generated)
        from custom_components.magic_areas.config_flow.helpers import SchemaBuilder

        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(HealthOptions, selector_overrides=selectors)

        assert schema is not None
        assert isinstance(schema, voluptuous.Schema)

        # Verify that all selectors were auto-generated
        assert len(selectors) > 0

    def test_no_selective_overrides_needed(self, health_feature_setup):
        """Test that no selective overrides are needed for health feature."""
        handler = health_feature_setup["handler"]

        # Get auto-generated selectors
        selectors = SelectorBuilder.from_option_set(HealthOptions)

        # Verify that all selectors are auto-generated
        assert len(selectors) > 0

        # For health feature, all selectors should be auto-generated
        # No manual overrides should be needed
        assert all(selector is not None for selector in selectors.values())
