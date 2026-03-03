"""Config flow specific fixtures."""

# pylint: disable=redefined-outer-name`

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import async_get as async_get_ar

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.config_flow.features.base import FeatureHandler
from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler
from custom_components.magic_areas.config_flow.helpers import (
    ConfigValidator,
    FlowEntityContext,
)
from custom_components.magic_areas.const import (
    CONF_AREA_ID,
    AreaConfigOptions,
    AreaType,
    ConfigDomains,
)

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor, MockLight, MockMediaPlayer


@pytest.fixture
async def mock_flow_entity_context(hass: HomeAssistant) -> FlowEntityContext:
    """Create a mock FlowEntityContext for testing."""
    # Setup basic area and entities
    area_registry = async_get_ar(hass)

    # Create test area
    if not area_registry.async_get_area_by_name(DEFAULT_MOCK_AREA.value):
        area_registry.async_create(name=DEFAULT_MOCK_AREA.value)

    # Create test entities
    test_entities = [
        MockBinarySensor(
            name="motion_sensor",
            unique_id="test_motion_sensor",
            device_class="motion",
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

    # Setup entities
    await setup_mock_entities(
        hass,
        "binary_sensor",
        {DEFAULT_MOCK_AREA: [test_entities[0]]},
    )
    await setup_mock_entities(
        hass,
        "light",
        {DEFAULT_MOCK_AREA: [test_entities[1]]},
    )
    await setup_mock_entities(
        hass,
        "media_player",
        {DEFAULT_MOCK_AREA: [test_entities[2]]},
    )

    # Create config entry
    config_entry = Mock(
        spec=config_entries.ConfigEntry,
        options={
            CONF_AREA_ID: DEFAULT_MOCK_AREA.value,
            ConfigDomains.AREA: {AreaConfigOptions.TYPE: AreaType.INTERIOR},
            ConfigDomains.FEATURES: {},
        },
    )

    # Create MagicArea
    magic_area = Mock(spec=MagicArea)
    magic_area.id = DEFAULT_MOCK_AREA.value
    magic_area.name = DEFAULT_MOCK_AREA.value
    magic_area.config = {
        AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
        AreaConfigOptions.EXCLUDE_ENTITIES.key: [],
        AreaConfigOptions.INCLUDE_ENTITIES.key: [],
    }
    magic_area.get_presence_sensors.return_value = ["binary_sensor.motion_sensor"]

    # Create flow
    flow = Mock(spec=OptionsFlowHandler)
    flow.hass = hass
    flow.config_entry = config_entry
    flow.area = magic_area
    flow.area_options = config_entry.options

    return FlowEntityContext(hass, magic_area, config_entry)


@pytest.fixture
def mock_config_validator() -> ConfigValidator:
    """Create a mock ConfigValidator for testing."""
    return ConfigValidator("test_flow")


@pytest.fixture
def mock_options_flow_handler(hass: HomeAssistant) -> OptionsFlowHandler:
    """Create a mock OptionsFlowHandler for testing."""
    # Create mock config entry
    config_entry = Mock(spec=config_entries.ConfigEntry)
    config_entry.options = {
        CONF_AREA_ID: DEFAULT_MOCK_AREA.value,
        ConfigDomains.AREA: {AreaConfigOptions.TYPE: AreaType.INTERIOR},
        ConfigDomains.FEATURES: {},
    }

    # Create mock MagicArea
    magic_area = Mock(spec=MagicArea)
    magic_area.id = DEFAULT_MOCK_AREA.value
    magic_area.name = DEFAULT_MOCK_AREA.value
    magic_area.config = {
        AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
        AreaConfigOptions.EXCLUDE_ENTITIES.key: [],
        AreaConfigOptions.INCLUDE_ENTITIES.key: [],
    }
    magic_area.is_meta.return_value = False
    magic_area.get_presence_sensors.return_value = []

    # Create flow instance
    flow = OptionsFlowHandler(config_entry)
    flow.hass = hass
    flow.area = magic_area
    flow.area_options = config_entry.options
    flow.all_entities = []
    flow.area_entities = []
    flow.all_area_entities = []
    flow.all_lights = []
    flow.all_media_players = []
    flow.all_binary_entities = []
    flow.all_light_tracking_entities = []

    return flow


@pytest.fixture
def mock_feature_handler(mock_options_flow_handler) -> FeatureHandler:
    """Create a mock FeatureHandler for testing."""
    handler = Mock(spec=FeatureHandler)
    handler.flow = mock_options_flow_handler
    handler.feature_id = "test_feature"
    handler.feature_name = "Test Feature"
    handler.is_available = True
    handler.requires_configuration = True
    handler.get_initial_step.return_value = "main"
    handler.get_config.return_value = {}
    handler.save_config = Mock()
    handler.cleanup = Mock()
    handler.handle_step = AsyncMock()
    return handler


@pytest.fixture
def config_flow_test_data() -> dict[str, Any]:
    """Provide test configuration data for various scenarios."""
    return {
        "basic_area_config": {
            CONF_AREA_ID: DEFAULT_MOCK_AREA.value,
            ConfigDomains.AREA: {
                AreaConfigOptions.TYPE: AreaType.INTERIOR,
                AreaConfigOptions.WINDOWLESS: False,
            },
            ConfigDomains.FEATURES: {},
        },
        "area_with_features": {
            CONF_AREA_ID: DEFAULT_MOCK_AREA.value,
            ConfigDomains.AREA: {AreaConfigOptions.TYPE: AreaType.INTERIOR},
            ConfigDomains.FEATURES: {
                "light_groups": {},
                "aggregates": {},
            },
        },
        "windowless_area_config": {
            CONF_AREA_ID: "bathroom",
            ConfigDomains.AREA: {
                AreaConfigOptions.TYPE: AreaType.INTERIOR,
                AreaConfigOptions.WINDOWLESS: True,
            },
            ConfigDomains.FEATURES: {},
        },
        "meta_area_config": {
            CONF_AREA_ID: "global",
            ConfigDomains.AREA: {AreaConfigOptions.TYPE: AreaType.META},
            ConfigDomains.FEATURES: {},
        },
        "presence_tracking_config": {
            "clear_timeout": 300,
            "sensor_device_class": ["motion", "occupancy"],
            "keep_only_entities": [],
        },
        "secondary_states_config": {
            "sleep_entity": "binary_sensor.sleep_sensor",
            "extended_timeout": 600,
        },
        "light_groups_config": {
            "overhead_lights": ["light.overhead_1", "light.overhead_2"],
            "task_lights": ["light.task_1"],
            "accent_lights": ["light.accent_1"],
            "sleep_lights": ["light.sleep_1"],
            "overhead_lights_states": ["occupied", "extended"],
            "task_lights_states": ["occupied"],
            "accent_lights_states": ["accented"],
            "sleep_lights_states": ["sleep"],
        },
        "aggregates_config": {
            "binary_sensor_device_classes": ["motion", "occupancy"],
            "sensor_device_classes": ["temperature", "humidity"],
            "min_entities": 2,
        },
        "climate_control_config": {
            "entity_id": "climate.living_room",
            "preset_clear": "away",
            "preset_occupied": "home",
            "preset_sleep": "sleep",
            "preset_extended": "eco",
        },
        "fan_groups_config": {
            "required_state": "occupied",
            "tracked_device_class": "temperature",
            "setpoint": 24.0,
        },
        "presence_hold_config": {
            "timeout": 30,
        },
        "ble_trackers_config": {
            "entities": ["sensor.ble_tracker_1"],
            "scan_interval": 60,
        },
        "wasp_in_a_box_config": {
            "delay": 30,
            "wasp_timeout": 10,
            "wasp_device_classes": ["motion"],
        },
        "health_config": {
            "sensor_device_classes": ["temperature", "humidity"],
        },
        "area_aware_media_player_config": {
            "notification_devices": ["media_player.living_room"],
            "notify_states": ["occupied", "extended"],
        },
    }


@pytest.fixture
async def config_flow_integration_setup(
    hass: HomeAssistant,
) -> AsyncGenerator[dict[str, Any], None]:
    """Set up integration for config flow testing."""
    # Create config entry
    config_entry = Mock()
    config_entry.options = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Initialize integration
    await init_integration(hass, [config_entry])

    yield {
        "hass": hass,
        "config_entry": config_entry,
        "area_id": DEFAULT_MOCK_AREA.value,
    }

    # Cleanup
    await shutdown_integration(hass, [config_entry])
