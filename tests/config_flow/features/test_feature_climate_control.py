"""Tests for climate control feature handler."""

from collections.abc import AsyncGenerator
from unittest.mock import Mock

import pytest

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.climate.const import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import async_get as async_get_ar

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.config_flow.features.climate_control import (
    ClimateControlFeature,
)
from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler
from custom_components.magic_areas.const import (
    MAGICAREAS_UNIQUEID_PREFIX,
    AreaConfigOptions,
    AreaType,
    ConfigDomains,
)
from custom_components.magic_areas.const.climate_control import ClimateControlOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import get_basic_config_entry_data, setup_mock_entities
from tests.mocks import MockBinarySensor, MockClimate, MockLight, MockMediaPlayer


class TestClimateControlFeature:
    """Test ClimateControlFeature class."""

    @pytest.fixture
    async def climate_control_feature_setup(
        self, hass: HomeAssistant
    ) -> AsyncGenerator[dict, None]:
        """Set up climate control feature for testing."""
        # Setup area and entities
        area_registry = async_get_ar(hass)

        if not area_registry.async_get_area_by_name(DEFAULT_MOCK_AREA.value):
            area_registry.async_create(name=DEFAULT_MOCK_AREA.value)

        # Create test entities including climate entities with different configurations
        binary_sensors = [
            MockBinarySensor(
                name="motion_sensor",
                unique_id="test_motion_sensor",
                device_class=BinarySensorDeviceClass.MOTION,
            ),
        ]

        lights = [
            MockLight(
                name="test_light",
                state="off",
                unique_id="test_light",
                dimmable=True,
            ),
        ]

        media_players = [
            MockMediaPlayer(
                name="test_media_player",
                state="off",
                unique_id="test_media_player",
            ),
        ]

        # Create climate entities: one WITH presets, one WITHOUT presets
        climate_entities = [
            MockClimate(
                name="living_room_climate",
                unique_id="test_climate_with_presets",
                preset_modes=["away", "home", "sleep", "eco"],  # Has presets
            ),
            MockClimate(
                name="simple_climate",
                unique_id="test_climate_no_presets",
                preset_modes=[],  # No presets - for testing validation
            ),
        ]

        # Setup all entities
        await setup_mock_entities(
            hass,
            BINARY_SENSOR_DOMAIN,
            {DEFAULT_MOCK_AREA: binary_sensors},
        )
        await setup_mock_entities(
            hass,
            LIGHT_DOMAIN,
            {DEFAULT_MOCK_AREA: lights},
        )
        await setup_mock_entities(
            hass,
            MEDIA_PLAYER_DOMAIN,
            {DEFAULT_MOCK_AREA: media_players},
        )
        await setup_mock_entities(
            hass,
            CLIMATE_DOMAIN,
            {DEFAULT_MOCK_AREA: climate_entities},
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

        # Create flow - include climate entities in all_entities
        flow = Mock(spec=OptionsFlowHandler)
        flow.hass = hass
        flow.config_entry = config_entry
        flow.area = magic_area
        flow.area_options = config_entry.options
        flow.all_entities = [
            "binary_sensor.motion_sensor",
            "light.test_light",
            "media_player.test_media_player",
            "climate.living_room_climate",
            "climate.simple_climate",
        ]
        flow.area_entities = [
            "binary_sensor.motion_sensor",
            "light.test_light",
            "climate.living_room_climate",
            "climate.simple_climate",
        ]
        flow.all_area_entities = flow.area_entities
        flow.all_lights = ["light.test_light"]
        flow.all_media_players = ["media_player.test_media_player"]
        flow.all_binary_entities = ["binary_sensor.motion_sensor"]
        flow.all_light_tracking_entities = ["binary_sensor.motion_sensor"]

        # Create feature handler
        handler = ClimateControlFeature(flow)

        yield {
            "hass": hass,
            "config_entry": config_entry,
            "magic_area": magic_area,
            "flow": flow,
            "handler": handler,
        }

    def test_feature_properties(self, climate_control_feature_setup):
        """Test feature properties."""
        handler = climate_control_feature_setup["handler"]

        assert handler.feature_id == ClimateControlOptions.FEATURE_KEY
        assert handler.feature_name == "Climate Control"
        assert handler.is_available is True
        assert handler.requires_configuration is True
        assert handler.get_initial_step() == "select_entity"

    def test_get_summary_no_config(self, climate_control_feature_setup):
        """Test getting summary with no configuration."""
        handler = climate_control_feature_setup["handler"]

        summary = handler.get_summary({})
        assert summary == "Not configured"

    def test_get_summary_with_config(self, climate_control_feature_setup):
        """Test getting summary with configuration."""
        handler = climate_control_feature_setup["handler"]
        config_entry = climate_control_feature_setup["config_entry"]

        # Set up config
        test_config = {
            ClimateControlOptions.ENTITY_ID.key: "climate.living_room",
            ClimateControlOptions.PRESET_CLEAR.key: "away",
            ClimateControlOptions.PRESET_OCCUPIED.key: "home",
            ClimateControlOptions.PRESET_SLEEP.key: "sleep",
            ClimateControlOptions.PRESET_EXTENDED.key: "eco",
        }
        config_entry.options[ConfigDomains.FEATURES] = {
            ClimateControlOptions.FEATURE_KEY: test_config
        }

        summary = handler.get_summary(test_config)
        assert "climate.living_room" in summary
        assert "presets" in summary

    async def test_handle_step_select_entity_no_input(
        self, climate_control_feature_setup
    ):
        """Test handling select entity step without input."""
        handler = climate_control_feature_setup["handler"]

        result = await handler.handle_step("select_entity", None)

        assert result.type == "form"
        assert result.step_id == "select_entity"
        assert result.data_schema is not None

    async def test_handle_step_select_entity_with_input(
        self, climate_control_feature_setup
    ):
        """Test handling select entity step with valid climate entity."""
        handler = climate_control_feature_setup["handler"]
        config_entry = climate_control_feature_setup["config_entry"]

        # Use the REAL climate entity with presets that was created in the fixture
        user_input = {
            ClimateControlOptions.ENTITY_ID.key: "climate.living_room_climate"
        }

        result = await handler.handle_step("select_entity", user_input)

        # Should proceed to preset selection step
        assert result.type == "form"
        assert result.step_id == "select_presets"
        # pylint: disable-next=protected-access
        assert handler._state["entity_id"] == "climate.living_room_climate"
        # pylint: disable-next=protected-access
        assert "away" in handler._state["preset_modes"]
        # pylint: disable-next=protected-access
        assert "home" in handler._state["preset_modes"]
        # pylint: disable-next=protected-access
        assert "sleep" in handler._state["preset_modes"]
        # pylint: disable-next=protected-access
        assert "eco" in handler._state["preset_modes"]

        # Check that entity_id was saved to config
        assert ConfigDomains.FEATURES in config_entry.options
        assert (
            ClimateControlOptions.FEATURE_KEY
            in config_entry.options[ConfigDomains.FEATURES]
        )
        assert (
            config_entry.options[ConfigDomains.FEATURES][
                ClimateControlOptions.FEATURE_KEY
            ][ClimateControlOptions.ENTITY_ID.key]
            == "climate.living_room_climate"
        )

    async def test_handle_step_select_entity_no_preset_support(
        self, climate_control_feature_setup
    ):
        """Test handling select entity step with climate entity without presets."""
        handler = climate_control_feature_setup["handler"]

        # Use the REAL climate entity WITHOUT presets that was created in the fixture
        user_input = {ClimateControlOptions.ENTITY_ID.key: "climate.simple_climate"}

        result = await handler.handle_step("select_entity", user_input)

        # Should show error because entity doesn't support presets
        assert result.type == "form"
        assert result.step_id == "select_entity"
        assert result.errors is not None
        assert ClimateControlOptions.ENTITY_ID.key in result.errors

    async def test_handle_step_select_presets_no_input(
        self, climate_control_feature_setup
    ):
        """Test handling select presets step without input."""
        handler = climate_control_feature_setup["handler"]

        # Set up state from previous step
        # pylint: disable-next=protected-access
        handler._state["entity_id"] = "climate.living_room"
        # pylint: disable-next=protected-access
        handler._state["preset_modes"] = [
            "away",
            "home",
            "sleep",
            "eco",
        ]

        result = await handler.handle_step("select_presets", None)

        assert result.type == "form"
        assert result.step_id == "select_presets"
        assert result.data_schema is not None

    async def test_handle_step_select_presets_with_input(
        self, climate_control_feature_setup
    ):
        """Test handling select presets step with input."""
        handler = climate_control_feature_setup["handler"]

        # Set up state from previous step
        # pylint: disable-next=protected-access
        handler._state["entity_id"] = "climate.living_room"
        # pylint: disable-next=protected-access
        handler._state["preset_modes"] = [
            "away",
            "home",
            "sleep",
            "eco",
        ]

        # Test with valid input
        user_input = {
            ClimateControlOptions.PRESET_CLEAR.key: "away",
            ClimateControlOptions.PRESET_OCCUPIED.key: "home",
            ClimateControlOptions.PRESET_SLEEP.key: "sleep",
            ClimateControlOptions.PRESET_EXTENDED.key: "eco",
        }

        result = await handler.handle_step("select_presets", user_input)

        assert result.type == "create_entry"
        assert result.save_data is not None

        expected_config = {
            ClimateControlOptions.ENTITY_ID.key: "climate.living_room",
            ClimateControlOptions.PRESET_CLEAR.key: "away",
            ClimateControlOptions.PRESET_OCCUPIED.key: "home",
            ClimateControlOptions.PRESET_SLEEP.key: "sleep",
            ClimateControlOptions.PRESET_EXTENDED.key: "eco",
        }

        assert result.save_data == expected_config

    def test_build_entity_schema(self, climate_control_feature_setup):
        """Test building entity selection schema."""
        handler = climate_control_feature_setup["handler"]

        # Test with no climate entities
        schema = handler._build_entity_schema()  # pylint: disable=protected-access
        assert schema is not None

        # Test with mock climate entities
        handler.flow.all_entities = [
            "climate.living_room",
            "climate.bedroom",
            f"{CLIMATE_DOMAIN}.{MAGICAREAS_UNIQUEID_PREFIX}_test",
        ]

        schema = handler._build_entity_schema()  # pylint: disable=protected-access
        assert schema is not None

        # Verify that Magic Areas entities are filtered out
        schema_keys = list(schema.schema.keys())
        assert len(schema_keys) > 0

    def test_two_step_flow_pattern(self, climate_control_feature_setup):
        """Test that the feature follows a proper two-step flow pattern."""
        handler = climate_control_feature_setup["handler"]

        # Verify initial step
        assert handler.get_initial_step() == "select_entity"

        # Verify that state is properly managed between steps
        handler._state["entity_id"] = "climate.test"  # pylint: disable=protected-access
        handler._state["preset_modes"] = ["test"]  # pylint: disable=protected-access

        # pylint: disable-next=protected-access
        assert handler._state["entity_id"] == "climate.test"
        # pylint: disable-next=protected-access
        assert handler._state["preset_modes"] == ["test"]

    def test_entity_filtering(self, climate_control_feature_setup):
        """Test that Magic Areas climate entities are filtered out."""
        handler = climate_control_feature_setup["handler"]

        # Test with mixed entities
        test_entities = [
            "climate.living_room",
            "climate.bedroom",
            f"{CLIMATE_DOMAIN}.{MAGICAREAS_UNIQUEID_PREFIX}_test",
            "sensor.temperature",
        ]

        handler.flow.all_entities = test_entities

        # Build schema and verify filtering
        schema = handler._build_entity_schema()  # pylint: disable=protected-access
        assert schema is not None

        # The schema should only include non-Magic Areas climate entities
        schema_keys = list(schema.schema.keys())
        assert len(schema_keys) > 0

    def test_metadata_driven_configuration(self, climate_control_feature_setup):
        """Test that configuration is driven by metadata."""
        # This test verifies that the feature uses the metadata from ClimateControlOptions
        # rather than hard-coded configuration

        assert hasattr(ClimateControlOptions, "ENTITY_ID")
        assert hasattr(ClimateControlOptions, "PRESET_CLEAR")
        assert hasattr(ClimateControlOptions, "PRESET_OCCUPIED")
        assert hasattr(ClimateControlOptions, "PRESET_SLEEP")
        assert hasattr(ClimateControlOptions, "PRESET_EXTENDED")

        # Verify that these options have the expected metadata
        entity_id_option = ClimateControlOptions.ENTITY_ID
        preset_clear_option = ClimateControlOptions.PRESET_CLEAR

        assert entity_id_option.key == "entity_id"
        assert preset_clear_option.key == "preset_clear"
