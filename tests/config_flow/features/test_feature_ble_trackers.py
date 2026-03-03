"""Tests for BLE trackers feature handler."""

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
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import async_get as async_get_ar

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.config_flow.features.ble_trackers import (
    BLETrackersFeature,
)
from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler
from custom_components.magic_areas.config_flow.helpers import (
    SchemaBuilder,
    SelectorBuilder,
)
from custom_components.magic_areas.const import (
    MAGICAREAS_UNIQUEID_PREFIX,
    AreaConfigOptions,
    AreaType,
    ConfigDomains,
)
from custom_components.magic_areas.const.ble_trackers import BleTrackerOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import get_basic_config_entry_data, setup_mock_entities
from tests.mocks import MockBinarySensor, MockLight, MockMediaPlayer


class TestBLETrackersFeature:
    """Test BLETrackersFeature class."""

    @pytest.fixture
    async def ble_trackers_feature_setup(
        self, hass: HomeAssistant
    ) -> AsyncGenerator[dict, None]:
        """Set up BLE trackers feature for testing."""
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
        handler = BLETrackersFeature(flow)

        yield {
            "hass": hass,
            "config_entry": config_entry,
            "magic_area": magic_area,
            "flow": flow,
            "handler": handler,
        }

    def test_feature_properties(self, ble_trackers_feature_setup):
        """Test feature properties."""
        handler = ble_trackers_feature_setup["handler"]

        assert handler.feature_id == "ble_trackers"
        assert handler.feature_name == "BLE Trackers"
        assert handler.is_available is True
        assert handler.requires_configuration is True

    def test_get_summary_no_config(self, ble_trackers_feature_setup):
        """Test getting summary with no configuration."""
        handler = ble_trackers_feature_setup["handler"]

        summary = handler.get_summary({})
        assert summary == "Not configured"

    def test_get_summary_with_config(self, ble_trackers_feature_setup):
        """Test getting summary with configuration."""
        handler = ble_trackers_feature_setup["handler"]
        config_entry = ble_trackers_feature_setup["config_entry"]

        # Set up config
        test_config = {
            BleTrackerOptions.ENTITIES.key: [
                "sensor.ble_tracker_1",
                "sensor.ble_tracker_2",
            ],
        }
        config_entry.options[ConfigDomains.FEATURES] = {"ble_trackers": test_config}

        summary = handler.get_summary(test_config)
        assert "tracker(s)" in summary

    async def test_handle_step_main_no_input(self, ble_trackers_feature_setup):
        """Test handling main step without input."""
        handler = ble_trackers_feature_setup["handler"]

        result = await handler.handle_step("main", None)

        assert result.type == "form"
        assert result.step_id == "main"
        assert result.data_schema is not None

    async def test_handle_step_main_with_input(self, ble_trackers_feature_setup):
        """Test handling main step with input."""
        handler = ble_trackers_feature_setup["handler"]
        config_entry = ble_trackers_feature_setup["config_entry"]

        # Test with valid input
        user_input = {
            BleTrackerOptions.ENTITIES.key: ["sensor.ble_tracker_1"],
        }

        result = await handler.handle_step("main", user_input)

        assert result.type == "create_entry"
        assert ConfigDomains.FEATURES in config_entry.options
        assert "ble_trackers" in config_entry.options[ConfigDomains.FEATURES]
        assert (
            config_entry.options[ConfigDomains.FEATURES]["ble_trackers"] == user_input
        )

    def test_auto_generated_schema_with_entity_filter_override(
        self, ble_trackers_feature_setup
    ):
        """Test that schema is auto-generated with entity filter override."""
        handler = ble_trackers_feature_setup["handler"]

        # Get current feature config
        feature_config = handler.get_config()

        # Auto-generate base selectors
        selectors = SelectorBuilder.from_option_set(BleTrackerOptions)

        # Override: Filter sensor entities (exclude Magic Areas sensors)
        sensor_entities = [
            entity_id
            for entity_id in handler.all_entities
            if (
                entity_id.split(".")[0] == SENSOR_DOMAIN
                and not entity_id.split(".")[1].startswith(MAGICAREAS_UNIQUEID_PREFIX)
            )
        ]

        selectors[BleTrackerOptions.ENTITIES.key] = (
            handler.flow.build_selector_entity_simple(sensor_entities, multiple=True)
        )

        # Auto-generate schema with overrides
        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(
            BleTrackerOptions, selector_overrides=selectors
        )

        assert schema is not None
        assert isinstance(schema, voluptuous.Schema)

    def test_entity_filter_override(self, ble_trackers_feature_setup):
        """Test that entity filter override works correctly."""
        handler = ble_trackers_feature_setup["handler"]

        # Test entity filtering
        sensor_entities = [
            entity_id
            for entity_id in handler.all_entities
            if (
                entity_id.split(".")[0] == SENSOR_DOMAIN
                and not entity_id.split(".")[1].startswith(MAGICAREAS_UNIQUEID_PREFIX)
            )
        ]

        # Should be empty since we only have binary_sensor and light entities
        assert len(sensor_entities) == 0

        # Test with mock sensor entities
        mock_sensor_entities = [
            "sensor.ble_tracker_1",
            "sensor.ble_tracker_2",
            f"{SENSOR_DOMAIN}.{MAGICAREAS_UNIQUEID_PREFIX}_test",
        ]

        filtered_entities = [
            entity_id
            for entity_id in mock_sensor_entities
            if (
                entity_id.split(".", maxsplit=1)[0] == SENSOR_DOMAIN
                and not entity_id.split(".")[1].startswith(MAGICAREAS_UNIQUEID_PREFIX)
            )
        ]

        assert len(filtered_entities) == 2
        assert "sensor.ble_tracker_1" in filtered_entities
        assert "sensor.ble_tracker_2" in filtered_entities
        assert (
            f"{SENSOR_DOMAIN}.{MAGICAREAS_UNIQUEID_PREFIX}_test"
            not in filtered_entities
        )

    def test_metadata_driven_configuration(self, ble_trackers_feature_setup):
        """Test that configuration is driven by metadata."""
        # This test verifies that the feature uses the metadata from BleTrackerOptions
        # rather than hard-coded configuration

        assert hasattr(BleTrackerOptions, "ENTITIES")

        # Verify that these options have the expected metadata
        entities_option = BleTrackerOptions.ENTITIES

        assert entities_option.key == "ble_tracker_entities"
