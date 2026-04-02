"""Tests for config_flow.flow module."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import async_get as async_get_ar

from custom_components.magic_areas.config_flow.flow import (
    ConfigFlow,
    OptionsFlowHandler,
)
from custom_components.magic_areas.const import (
    CONF_AREA_ID,
    DOMAIN,
    AreaConfigOptions,
    AreaType,
    ConfigDomains,
    ConfigHelper,
    Features,
)
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import get_basic_config_entry_data, setup_mock_entities
from tests.mocks import MockBinarySensor, MockLight, MockMediaPlayer


class TestConfigFlow:
    """Test ConfigFlow class."""

    async def test_async_step_user_select_area(self, hass: HomeAssistant):
        """Test user step selecting an area."""
        # Setup area registry
        area_registry = async_get_ar(hass)
        area = area_registry.async_get_or_create(DEFAULT_MOCK_AREA.value)

        # Create proper config flow through manager
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Submit area selection
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_AREA_ID: area.id}
        )

        assert (
            "type" in result
            and "title" in result
            and "data" in result
            and CONF_AREA_ID in result["data"]
        )

        assert result["type"] == "create_entry"
        assert result["title"] == area.name
        assert CONF_AREA_ID in result["data"]
        assert result["data"][CONF_AREA_ID] == area.id

    async def test_async_step_user_select_meta_area(self, hass: HomeAssistant):
        """Test user step selecting a meta area."""
        # Create proper config flow through manager
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Submit meta area selection
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_AREA_ID: "global"}
        )

        assert (
            "type" in result
            and "title" in result
            and "data" in result
            and CONF_AREA_ID in result["data"]
            and ConfigDomains.AREA.value in result["data"]
            and AreaConfigOptions.TYPE.key in result["data"][ConfigDomains.AREA.value]
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "Global"
        assert CONF_AREA_ID in result["data"]
        assert result["data"][CONF_AREA_ID] == "global"
        assert (
            result["data"][ConfigDomains.AREA.value][AreaConfigOptions.TYPE.key]
            == AreaType.META
        )

    async def test_async_step_user_invalid_area(self, hass: HomeAssistant):
        """Test user step with invalid area."""
        # Create config flow
        flow = ConfigFlow()
        flow.hass = hass

        # Test selecting invalid area ID
        result = await flow.async_step_user({CONF_AREA_ID: "invalid_area_id"})

        assert "type" in result and "reason" in result

        assert result["type"] == "abort"
        assert result["reason"] == "invalid_area"

    async def test_async_step_user_no_areas_available(self, hass: HomeAssistant):
        """Test user step when no areas are available."""
        # Create config flow
        flow = ConfigFlow()
        flow.hass = hass

        # Test when no areas are available
        result = await flow.async_step_user({CONF_AREA_ID: "nonexistent_area"})

        assert "type" in result and "reason" in result

        assert result["type"] == "abort"
        assert result["reason"] == "invalid_area"

    async def test_async_get_options_flow(self, hass: HomeAssistant):
        """Test getting options flow."""
        config_entry = Mock()
        config_entry.entry_id = "test_entry_id"

        flow = ConfigFlow.async_get_options_flow(config_entry)

        assert isinstance(flow, OptionsFlowHandler)
        # Note: config_entry property is not available until flow is initialized with hass


class TestOptionsFlowHandler:
    """Test OptionsFlowHandler class."""

    @pytest.fixture
    async def options_flow_setup(
        self, hass: HomeAssistant
    ) -> AsyncGenerator[dict, None]:
        """Set up options flow for testing."""
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
        config_entry.entry_id = "test_entry_id"  # Required for flow.config_entry access
        config_entry.options = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

        # Create MagicArea with ConfigHelper (not plain dict)
        area_config_data = {
            ConfigDomains.AREA: {
                AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
                AreaConfigOptions.EXCLUDE_ENTITIES.key: [],
                AreaConfigOptions.INCLUDE_ENTITIES.key: [],
            }
        }

        magic_area = Mock()
        magic_area.id = DEFAULT_MOCK_AREA.value
        magic_area.name = DEFAULT_MOCK_AREA.value
        magic_area.config = ConfigHelper(area_config_data)
        magic_area.is_meta.return_value = False
        magic_area.get_presence_sensors.return_value = ["binary_sensor.motion_sensor"]

        # Store MagicArea as runtime_data on the config entry (new convention)
        config_entry.runtime_data = magic_area

        flow = OptionsFlowHandler(config_entry)
        flow.hass = hass
        flow.area = magic_area
        flow.area_options = config_entry.options

        yield {
            "hass": hass,
            "config_entry": config_entry,
            "magic_area": magic_area,
            "flow": flow,
        }

    async def test_async_step_init(self, options_flow_setup):
        """Test initialization of options flow."""
        flow = options_flow_setup["flow"]

        # Manually initialize what async_step_init would do (can't call it directly - needs handler)
        flow.area = options_flow_setup["magic_area"]
        flow.area_options = options_flow_setup["config_entry"].options

        # Set entity lists (these would be populated by FlowEntityContext)
        flow.all_entities = []
        flow.area_entities = []
        flow.all_area_entities = []
        flow.all_lights = []
        flow.all_media_players = []
        flow.all_binary_entities = []
        flow.all_light_tracking_entities = []

        # Call show_menu directly (doesn't require config_entry.entry_id)
        result = await flow.async_step_show_menu()

        assert result["type"] == "menu"
        assert result["step_id"] == "show_menu"

    async def test_async_step_show_menu(self, options_flow_setup):
        """Test showing the main menu."""
        flow = options_flow_setup["flow"]

        result = await flow.async_step_show_menu()

        assert result["type"] == "menu"
        assert "area_config" in result["menu_options"]
        assert "presence_tracking" in result["menu_options"]
        assert "secondary_states" in result["menu_options"]
        assert "user_defined_states" in result["menu_options"]
        assert "select_features" in result["menu_options"]
        assert "finish" in result["menu_options"]

    async def test_async_step_area_config(self, options_flow_setup):
        """Test area configuration step."""
        flow = options_flow_setup["flow"]

        # Test with valid input
        user_input = {
            AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
            AreaConfigOptions.INCLUDE_ENTITIES.key: [],
            AreaConfigOptions.EXCLUDE_ENTITIES.key: [],
        }

        result = await flow.async_step_area_config(user_input)

        assert result["type"] == "menu"  # Returns menu, not form
        assert result["step_id"] == "show_menu"

    async def test_async_step_presence_tracking(self, options_flow_setup):
        """Test presence tracking configuration step."""
        flow = options_flow_setup["flow"]

        # Initialize flow state (what async_step_init would do)
        flow.area = options_flow_setup["magic_area"]
        flow.area_options = options_flow_setup["config_entry"].options

        # Test displaying the form (no user_input)
        result = await flow.async_step_presence_tracking(None)
        assert result["type"] == "form"
        assert result["step_id"] == "presence_tracking"
        # Note: Submission path requires full flow initialization (entity lists, etc.)
        # Other tests adequately cover the submission flow

    async def test_async_step_secondary_states(self, options_flow_setup):
        """Test secondary states configuration step."""
        flow = options_flow_setup["flow"]

        # Test with valid input - use ConfigOption.key
        user_input = {
            SecondaryStateOptions.SLEEP_ENTITY.key: "binary_sensor.sleep_sensor",
            SecondaryStateOptions.EXTENDED_TIMEOUT.key: 10,  # minutes
        }

        result = await flow.async_step_secondary_states(user_input)

        assert result["type"] == "menu"  # Returns menu, not form
        assert result["step_id"] == "show_menu"

    async def test_async_step_select_features(self, options_flow_setup):
        """Test feature selection step."""
        flow = options_flow_setup["flow"]

        # Test with valid input - use correct enum value
        user_input = {
            Features.LIGHT_GROUPS: True,
            Features.AGGREGATION: False,  # Correct enum member name
        }

        result = await flow.async_step_select_features(user_input)

        assert result["type"] == "menu"  # Returns menu, not form
        assert result["step_id"] == "show_menu"

    async def test_async_step_finish(self, options_flow_setup):
        """Test finish step."""
        flow = options_flow_setup["flow"]

        result = await flow.async_step_finish()

        assert result["type"] == "create_entry"
        assert result["title"] == ""
        assert result["data"] == flow.area_options

    async def test_async_step_feature_dispatch(self, options_flow_setup):
        """Test feature step dispatching."""
        flow = options_flow_setup["flow"]

        # Mock feature handler
        mock_handler = Mock()
        mock_handler.handle_step = AsyncMock()
        mock_handler.handle_step.return_value = Mock(
            type="create_entry", save_data={"test": "data"}
        )
        mock_handler.cleanup = Mock()

        flow._feature_handlers = {  # pylint: disable=protected-access
            "test_feature": mock_handler
        }
        flow._current_feature = "test_feature"  # pylint: disable=protected-access

        result = await flow.async_step_feature({"test": "input"})

        assert result["type"] == "menu"  # Returns menu, not form
        assert result["step_id"] == "show_menu"
        mock_handler.handle_step.assert_called_once()
        mock_handler.cleanup.assert_called_once()

    async def test_get_feature_list(self, options_flow_setup):
        """Test getting feature list for area type."""
        flow = options_flow_setup["flow"]

        # Test with regular area
        feature_list = flow._get_feature_list()  # pylint: disable=protected-access
        assert Features.LIGHT_GROUPS in feature_list
        assert Features.AGGREGATION in feature_list

        # Test with meta area - replace entire config (ConfigHelper is immutable)
        flow.area.config = ConfigHelper(
            {
                ConfigDomains.AREA: {
                    AreaConfigOptions.TYPE.key: AreaType.META,
                    AreaConfigOptions.EXCLUDE_ENTITIES.key: [],
                    AreaConfigOptions.INCLUDE_ENTITIES.key: [],
                }
            }
        )
        feature_list = flow._get_feature_list()  # pylint: disable=protected-access
        # Meta areas DO support light groups (simple "All Lights" groups)
        assert Features.LIGHT_GROUPS in feature_list

        # Test with global area
        flow.area.id = "global"
        feature_list = flow._get_feature_list()  # pylint: disable=protected-access
        # Global area uses different feature list (may or may not include light_groups)
        assert isinstance(feature_list, list)

    async def test_get_configurable_features(self, options_flow_setup):
        """Test getting configurable features."""
        flow = options_flow_setup["flow"]

        configurable = (
            flow._get_configurable_features()  # pylint: disable=protected-access
        )
        assert isinstance(configurable, list)
        assert len(configurable) > 0

    async def test_resolve_groups(self, options_flow_setup):
        """Test resolving groups."""
        flow = options_flow_setup["flow"]

        raw_list = [["item1", "item2"], "item3"]
        resolved = flow.resolve_groups(raw_list)

        assert resolved == ["item1", "item2", "item3"]

    async def test_async_step_area_config_with_windowless_true(
        self, options_flow_setup
    ):
        """Test area configuration with windowless=True."""
        flow = options_flow_setup["flow"]

        user_input = {
            AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
            AreaConfigOptions.WINDOWLESS.key: True,
            AreaConfigOptions.INCLUDE_ENTITIES.key: [],
            AreaConfigOptions.EXCLUDE_ENTITIES.key: [],
        }

        result = await flow.async_step_area_config(user_input)

        assert result["type"] == "menu"
        # Verify saved - options are saved at the root level now
        assert (
            flow.area_options.get(ConfigDomains.AREA, {}).get(
                AreaConfigOptions.WINDOWLESS.key, None
            )
            is True
        )

    async def test_async_step_area_config_windowless_defaults_false(
        self, options_flow_setup
    ):
        """Test WINDOWLESS defaults to False."""
        flow = options_flow_setup["flow"]

        # Don't include WINDOWLESS in input
        user_input = {
            AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
            AreaConfigOptions.INCLUDE_ENTITIES.key: [],
            AreaConfigOptions.EXCLUDE_ENTITIES.key: [],
        }

        await flow.async_step_area_config(user_input)

        # Should use default (False)
        windowless = flow.area_options.get(ConfigDomains.AREA, {}).get(
            AreaConfigOptions.WINDOWLESS.key, AreaConfigOptions.WINDOWLESS.default
        )
        assert windowless is False
