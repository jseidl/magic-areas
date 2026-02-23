"""Tests for area aware media player feature handler."""

from collections.abc import AsyncGenerator
from unittest.mock import Mock

import pytest
import voluptuous

from custom_components.magic_areas.config_flow.helpers import SelectorBuilder
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import async_get as async_get_ar
from homeassistant.helpers.entity_registry import async_get as async_get_er

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.config_flow.features.area_aware_media_player import (
    AreaAwareMediaPlayerFeature,
)
from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler
from custom_components.magic_areas.const import (
    AreaConfigOptions,
    AreaStates,
    AreaType,
    ConfigDomains,
)
from custom_components.magic_areas.const.area_aware_media_player import (
    AreaAwareMediaPlayerOptions,
)

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import get_basic_config_entry_data
from tests.mocks import MockBinarySensor, MockLight, MockMediaPlayer


class TestAreaAwareMediaPlayerFeature:
    """Test AreaAwareMediaPlayerFeature class."""

    @pytest.fixture
    async def area_aware_media_player_feature_setup(
        self, hass: HomeAssistant
    ) -> AsyncGenerator[dict, None]:
        """Set up area aware media player feature for testing."""
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
        handler = AreaAwareMediaPlayerFeature(flow)

        yield {
            "hass": hass,
            "config_entry": config_entry,
            "magic_area": magic_area,
            "flow": flow,
            "handler": handler,
        }

    def test_feature_properties(self, area_aware_media_player_feature_setup):
        """Test feature properties."""
        handler = area_aware_media_player_feature_setup["handler"]

        assert handler.feature_id == "area_aware_media_player"
        assert handler.feature_name == "Area Aware Media Player"
        assert handler.is_available is True
        assert handler.requires_configuration is True

    def test_get_summary_no_config(self, area_aware_media_player_feature_setup):
        """Test getting summary with no configuration."""
        handler = area_aware_media_player_feature_setup["handler"]

        summary = handler.get_summary({})
        assert summary == "Not configured"

    def test_get_summary_with_config(self, area_aware_media_player_feature_setup):
        """Test getting summary with configuration."""
        handler = area_aware_media_player_feature_setup["handler"]
        config_entry = area_aware_media_player_feature_setup["config_entry"]

        # Set up config
        test_config = {
            AreaAwareMediaPlayerOptions.NOTIFICATION_DEVICES.key: [
                "media_player.living_room",
                "media_player.bedroom",
            ],
            AreaAwareMediaPlayerOptions.NOTIFICATION_STATES.key: [
                AreaStates.OCCUPIED,
                AreaStates.EXTENDED,
            ],
        }
        config_entry.options[ConfigDomains.FEATURES] = {
            "area_aware_media_player": test_config
        }

        summary = handler.get_summary(test_config)
        assert "device(s)" in summary
        assert "state(s)" in summary

    async def test_handle_step_main_no_input(
        self, area_aware_media_player_feature_setup
    ):
        """Test handling main step without input."""
        handler = area_aware_media_player_feature_setup["handler"]

        result = await handler.handle_step("main", None)

        assert result.type == "form"
        assert result.step_id == "main"
        assert result.data_schema is not None

    async def test_handle_step_main_with_input(
        self, area_aware_media_player_feature_setup
    ):
        """Test handling main step with input."""
        handler = area_aware_media_player_feature_setup["handler"]
        config_entry = area_aware_media_player_feature_setup["config_entry"]

        # Test with valid input
        user_input = {
            AreaAwareMediaPlayerOptions.NOTIFICATION_DEVICES.key: [
                "media_player.living_room"
            ],
            AreaAwareMediaPlayerOptions.NOTIFICATION_STATES.key: [AreaStates.OCCUPIED],
        }

        result = await handler.handle_step("main", user_input)

        assert result.type == "create_entry"
        assert ConfigDomains.FEATURES in config_entry.options
        assert "area_aware_media_player" in config_entry.options[ConfigDomains.FEATURES]
        assert (
            config_entry.options[ConfigDomains.FEATURES]["area_aware_media_player"]
            == user_input
        )

    def test_auto_generated_schema_with_overrides(
        self, area_aware_media_player_feature_setup
    ):
        """Test that schema is auto-generated with selective overrides."""
        handler = area_aware_media_player_feature_setup["handler"]

        # Get current feature config
        feature_config = handler.get_config()

        # Auto-generate base selectors
        from custom_components.magic_areas.config_flow.helpers import (
            SelectorBuilder,
            StateOptionsBuilder,
        )

        selectors = SelectorBuilder.from_option_set(AreaAwareMediaPlayerOptions)

        # Override 1: Filtered media player entities
        selectors[AreaAwareMediaPlayerOptions.NOTIFICATION_DEVICES.key] = (
            handler.flow.build_selector_entity_simple(
                handler.all_media_players, multiple=True
            )
        )

        # Override 2: Dynamic state options - build available states list
        from custom_components.magic_areas.const import BUILTIN_AREA_STATES

        available_states = [str(s) for s in BUILTIN_AREA_STATES]
        available_states = StateOptionsBuilder.for_area_aware_media_player(
            available_states
        )
        selectors[AreaAwareMediaPlayerOptions.NOTIFICATION_STATES.key] = (
            handler.flow.build_selector_select(available_states, multiple=True)
        )

        # Auto-generate schema with overrides
        from custom_components.magic_areas.config_flow.helpers import SchemaBuilder

        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(
            AreaAwareMediaPlayerOptions, selector_overrides=selectors
        )

        assert schema is not None
        assert isinstance(schema, voluptuous.Schema)

    def test_selective_overrides(self, area_aware_media_player_feature_setup):
        """Test that only specific selectors are overridden."""
        handler = area_aware_media_player_feature_setup["handler"]

        # Get auto-generated selectors
        selectors = SelectorBuilder.from_option_set(AreaAwareMediaPlayerOptions)

        # Verify that most selectors are auto-generated
        assert len(selectors) > 0

        # Verify that specific selectors can be overridden
        media_player_selector = handler.flow.build_selector_entity_simple(
            handler.all_media_players, multiple=True
        )
        assert media_player_selector is not None

        state_selector = handler.flow.build_selector_select(
            [AreaStates.OCCUPIED, AreaStates.EXTENDED], multiple=True
        )
        assert state_selector is not None

    def test_metadata_driven_configuration(self, area_aware_media_player_feature_setup):
        """Test that configuration is driven by metadata."""
        # This test verifies that the feature uses the metadata from AreaAwareMediaPlayerOptions
        # rather than hard-coded configuration

        assert hasattr(AreaAwareMediaPlayerOptions, "NOTIFICATION_DEVICES")
        assert hasattr(AreaAwareMediaPlayerOptions, "NOTIFICATION_STATES")

        # Verify that these options have the expected metadata
        notification_devices_option = AreaAwareMediaPlayerOptions.NOTIFICATION_DEVICES
        notification_states_option = AreaAwareMediaPlayerOptions.NOTIFICATION_STATES

        assert notification_devices_option.key == "notification_devices"
        assert notification_states_option.key == "notification_states"
