"""Tests for light groups feature handler."""

from collections.abc import AsyncGenerator
from unittest.mock import Mock

import pytest

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import async_get as async_get_ar
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.config_flow.features.light_groups import (
    LightGroupsFeature,
)
from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler
from custom_components.magic_areas.const import (
    AreaConfigOptions,
    AreaStates,
    AreaType,
    ConfigDomains,
    ConfigHelper,
    Features,
)
from custom_components.magic_areas.const.light_groups import (
    LightGroupEntryOptions,
    LightGroupOptions,
    LightGroupTurnOffWhen,
    LightGroupTurnOnWhen,
)

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import get_basic_config_entry_data, setup_mock_entities
from tests.mocks import MockBinarySensor, MockLight, MockMediaPlayer


class TestLightGroupsFeature:
    """Test LightGroupsFeature class."""

    @pytest.fixture
    async def light_groups_feature_setup(
        self, hass: HomeAssistant
    ) -> AsyncGenerator[dict, None]:
        """Set up light groups feature for testing."""
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
            MockLight(
                name="overhead_light",
                state="off",
                unique_id="overhead_light",
                dimmable=True,
            ),
            MockLight(
                name="task_light",
                state="off",
                unique_id="task_light",
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
            {DEFAULT_MOCK_AREA: test_entities[1:4]},
        )
        await setup_mock_entities(
            hass,
            MEDIA_PLAYER_DOMAIN,
            {DEFAULT_MOCK_AREA: [test_entities[4]]},
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
        flow.all_entities = [
            "binary_sensor.motion_sensor",
            "light.test_light",
            "light.overhead_light",
            "light.task_light",
        ]
        flow.area_entities = [
            "binary_sensor.motion_sensor",
            "light.test_light",
            "light.overhead_light",
            "light.task_light",
        ]
        flow.all_area_entities = [
            "binary_sensor.motion_sensor",
            "light.test_light",
            "light.overhead_light",
            "light.task_light",
        ]
        flow.all_lights = [
            "light.test_light",
            "light.overhead_light",
            "light.task_light",
        ]
        flow.all_media_players = ["media_player.test_media_player"]
        flow.all_binary_entities = ["binary_sensor.motion_sensor"]
        flow.all_light_tracking_entities = ["binary_sensor.motion_sensor"]

        # Create feature handler
        handler = LightGroupsFeature(flow)

        yield {
            "hass": hass,
            "config_entry": config_entry,
            "magic_area": magic_area,
            "flow": flow,
            "handler": handler,
            "area_config_data": area_config_data,
        }

    # ========================================================================
    # Feature Properties Tests
    # ========================================================================

    def test_feature_properties(self, light_groups_feature_setup):
        """Test basic feature properties."""
        handler = light_groups_feature_setup["handler"]

        assert handler.feature_id == "light_groups"
        assert handler.feature_name == "Light Groups"
        assert handler.requires_configuration is True

    def test_is_available_interior_area(self, light_groups_feature_setup):
        """Test that light groups are available for interior areas."""
        handler = light_groups_feature_setup["handler"]
        area_config_data = light_groups_feature_setup["area_config_data"]

        # Set to interior
        area_config_data[ConfigDomains.AREA][
            AreaConfigOptions.TYPE.key
        ] = AreaType.INTERIOR
        assert handler.is_available is True

    def test_is_available_exterior_area(self, light_groups_feature_setup):
        """Test that light groups are available for exterior areas."""
        handler = light_groups_feature_setup["handler"]
        area_config_data = light_groups_feature_setup["area_config_data"]

        # Set to exterior
        area_config_data[ConfigDomains.AREA][
            AreaConfigOptions.TYPE.key
        ] = AreaType.EXTERIOR
        assert handler.is_available is True

    def test_is_available_meta_area(self, light_groups_feature_setup):
        """Test that light groups are NOT available for meta areas."""
        handler = light_groups_feature_setup["handler"]
        area_config_data = light_groups_feature_setup["area_config_data"]

        # Set to meta
        area_config_data[ConfigDomains.AREA][AreaConfigOptions.TYPE.key] = AreaType.META
        assert handler.is_available is False

    # ========================================================================
    # Main Menu Tests
    # ========================================================================

    async def test_main_menu_empty(self, light_groups_feature_setup):
        """Test main menu with no groups."""
        handler = light_groups_feature_setup["handler"]

        result = await handler.handle_step("main", None)

        assert result.type == "menu"
        assert result.step_id == "main"
        assert result.menu_options is not None
        # With no groups, should only show add_group and done
        assert "feature_light_groups_add_group" in result.menu_options
        assert "show_menu" in result.menu_options
        assert "feature_light_groups_select_group" not in result.menu_options
        assert "feature_light_groups_delete_group" not in result.menu_options

    async def test_main_menu_with_groups(self, light_groups_feature_setup):
        """Test main menu shows edit/delete options when groups exist."""
        handler = light_groups_feature_setup["handler"]
        config_entry = light_groups_feature_setup["config_entry"]

        # Add a group
        config_entry.options[ConfigDomains.FEATURES] = {
            "light_groups": {
                "groups": [
                    {
                        LightGroupEntryOptions.NAME.key: "Test Group",
                        LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
                    }
                ]
            }
        }

        result = await handler.handle_step("main", None)

        assert result.type == "menu"
        assert result.step_id == "main"
        assert "feature_light_groups_add_group" in result.menu_options
        assert "feature_light_groups_select_group" in result.menu_options
        assert "feature_light_groups_delete_group" in result.menu_options
        assert "show_menu" in result.menu_options

    # ========================================================================
    # Schema Validation Tests
    # ========================================================================

    async def test_add_group_form_renders_with_fields(self, light_groups_feature_setup):
        """Test that add_group step returns a form with all expected fields.

        This test would catch bugs where improper validators are used instead of
        selectors, resulting in blank forms.
        """
        handler = light_groups_feature_setup["handler"]
        flow = light_groups_feature_setup["flow"]

        # Mock build_selector_select to return proper selectors
        def mock_build_selector_select(
            options=None, multiple=False, translation_key=""
        ):
            return SelectSelector(
                SelectSelectorConfig(
                    options=options or [],
                    multiple=multiple,
                )
            )

        flow.build_selector_select = mock_build_selector_select

        # Get the form result
        result = await handler.handle_step("add_group", None)

        assert result.type == "form"
        assert result.step_id == "add_group"
        assert result.data_schema is not None

        # Verify schema has all required fields
        schema_dict = result.data_schema.schema
        field_names = {key.schema for key in schema_dict if hasattr(key, "schema")}

        assert "name" in field_names, "Form should have 'name' field"
        assert "lights" in field_names, "Form should have 'lights' field"
        assert "states" in field_names, "Form should have 'states' field"
        assert "turn_on_when" in field_names, "Form should have 'turn_on_when' field"
        assert "turn_off_when" in field_names, "Form should have 'turn_off_when' field"
        assert "require_dark" in field_names, "Form should have 'require_dark' field"

    async def test_build_group_schema_uses_proper_selectors(
        self, light_groups_feature_setup
    ):
        """Test that _build_group_schema returns schema with proper UI selectors.

        This test specifically validates that SelectSelector objects are used
        instead of cv.multi_select() validator functions. This catches bugs where
        validators are used instead of selectors, causing blank forms in the UI.
        """
        handler = light_groups_feature_setup["handler"]
        flow = light_groups_feature_setup["flow"]

        # Mock build_selector_select to return actual SelectSelector instances
        def mock_build_selector_select(
            options=None, multiple=False, translation_key=""
        ):
            return SelectSelector(
                SelectSelectorConfig(
                    options=options or [],
                    multiple=multiple,
                )
            )

        def mock_build_selector_entity_simple(
            options=None, multiple=False, translation_key=""
        ):
            return EntitySelector(
                EntitySelectorConfig(
                    include_entities=options or [],
                    multiple=multiple,
                )
            )

        flow.build_selector_select = mock_build_selector_select
        flow.build_selector_entity_simple = mock_build_selector_entity_simple

        # Build schema
        schema = handler._build_group_schema()  # pylint: disable=protected-access

        # Extract validators from schema
        schema_dict = schema.schema

        # Find the validators for our key fields
        lights_validator = None
        states_validator = None
        turn_on_when_validator = None
        turn_off_when_validator = None
        require_dark_validator = None

        for key, validator in schema_dict.items():
            if hasattr(key, "schema"):
                if key.schema == LightGroupEntryOptions.LIGHTS.key:
                    lights_validator = validator
                elif key.schema == LightGroupEntryOptions.STATES.key:
                    states_validator = validator
                elif key.schema == LightGroupEntryOptions.TURN_ON_WHEN.key:
                    turn_on_when_validator = validator
                elif key.schema == LightGroupEntryOptions.TURN_OFF_WHEN.key:
                    turn_off_when_validator = validator
                elif key.schema == LightGroupEntryOptions.REQUIRE_DARK.key:
                    require_dark_validator = validator

        # Verify they are SelectSelector instances, not cv.multi_select validators
        assert isinstance(
            lights_validator, EntitySelector
        ), f"lights field should use EntitySelector, got {type(lights_validator)}"
        assert isinstance(
            states_validator, SelectSelector
        ), f"states field should use SelectSelector, got {type(states_validator)}"
        assert isinstance(
            turn_on_when_validator, SelectSelector
        ), f"turn_on_when field should use SelectSelector, got {type(turn_on_when_validator)}"
        assert isinstance(
            turn_off_when_validator, SelectSelector
        ), f"turn_off_when field should use SelectSelector, got {type(turn_off_when_validator)}"
        assert isinstance(
            require_dark_validator, BooleanSelector
        ), f"require_dark field should use BooleanSelector, got {type(require_dark_validator)}"

        # Verify multi-select is enabled (this is important for UX)
        assert (
            lights_validator.config.get("multiple") is True
        ), "lights selector should support multiple selection"
        assert (
            states_validator.config.get("multiple") is True
        ), "states selector should support multiple selection"
        assert (
            turn_on_when_validator.config.get("multiple") is True
        ), "turn_on_when_validator selector should support multiple selection"
        assert (
            turn_off_when_validator.config.get("multiple") is True
        ), "turn_off_when_validator selector should support multiple selection"

    # ========================================================================
    # Add Group Tests
    # ========================================================================

    async def test_add_group_valid(self, light_groups_feature_setup):
        """Test adding a group with valid data."""
        handler = light_groups_feature_setup["handler"]
        config_entry = light_groups_feature_setup["config_entry"]

        group_name = "New Group"

        user_input = {
            LightGroupEntryOptions.NAME.key: group_name,
            LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
            LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
            LightGroupEntryOptions.TURN_ON_WHEN.key: [
                LightGroupTurnOnWhen.AREA_OCCUPIED.value
            ],
            LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                LightGroupTurnOffWhen.AREA_CLEAR.value
            ],
        }

        result = await handler.handle_step("add_group", user_input)

        assert result.type == "menu"
        assert result.step_id == "main"

        # Verify group was added
        groups = config_entry.options[ConfigDomains.FEATURES][Features.LIGHT_GROUPS][
            LightGroupOptions.GROUPS.key
        ]
        assert len(groups) == 1
        assert groups[0][LightGroupEntryOptions.NAME.key] == group_name

    async def test_add_group_empty_name(self, light_groups_feature_setup):
        """Test adding group with empty name shows error."""
        handler = light_groups_feature_setup["handler"]

        user_input = {
            LightGroupEntryOptions.NAME.key: "",
            LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
        }

        result = await handler.handle_step("add_group", user_input)

        assert result.type == "form"
        assert result.step_id == "add_group"
        assert result.errors is not None
        assert "name" in result.errors

    async def test_add_group_no_lights(self, light_groups_feature_setup):
        """Test adding group with no lights shows error."""
        handler = light_groups_feature_setup["handler"]

        user_input = {
            LightGroupEntryOptions.NAME.key: "Test",
            LightGroupEntryOptions.LIGHTS.key: [],
        }

        result = await handler.handle_step("add_group", user_input)

        assert result.type == "form"
        assert result.step_id == "add_group"
        assert result.errors is not None
        assert "lights" in result.errors

    async def test_add_group_duplicate_name(self, light_groups_feature_setup):
        """Test adding group with duplicate name shows error."""
        handler = light_groups_feature_setup["handler"]
        config_entry = light_groups_feature_setup["config_entry"]

        # Add existing group
        config_entry.options[ConfigDomains.FEATURES] = {
            "light_groups": {
                "groups": [
                    {
                        LightGroupEntryOptions.NAME.key: "Existing",
                        LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
                    }
                ]
            }
        }

        user_input = {
            LightGroupEntryOptions.NAME.key: "Existing",
            LightGroupEntryOptions.LIGHTS.key: ["light.overhead_light"],
        }

        result = await handler.handle_step("add_group", user_input)

        assert result.type == "form"
        assert result.step_id == "add_group"
        assert result.errors is not None
        assert "name" in result.errors

    async def test_add_group_reserved_name(self, light_groups_feature_setup):
        """Test adding group with reserved name shows error."""
        handler = light_groups_feature_setup["handler"]

        user_input = {
            LightGroupEntryOptions.NAME.key: "All Lights",
            LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
        }

        result = await handler.handle_step("add_group", user_input)

        assert result.type == "form"
        assert result.step_id == "add_group"
        assert result.errors is not None
        assert "name" in result.errors

    # ========================================================================
    # Edit Group Tests
    # ========================================================================

    async def test_edit_group_valid(self, light_groups_feature_setup):
        """Test editing a group successfully."""
        handler = light_groups_feature_setup["handler"]
        config_entry = light_groups_feature_setup["config_entry"]

        # Add initial group
        config_entry.options[ConfigDomains.FEATURES] = {
            "light_groups": {
                "groups": [
                    {
                        LightGroupEntryOptions.NAME.key: "Original",
                        LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
                        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
                        LightGroupEntryOptions.TURN_ON_WHEN.key: [
                            LightGroupTurnOnWhen.AREA_OCCUPIED.value
                        ],
                        LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                            LightGroupTurnOffWhen.AREA_CLEAR.value
                        ],
                    }
                ]
            }
        }

        # Navigate to select_group step
        select_result = await handler.handle_step("select_group", {"group_index": 0})
        assert select_result.type == "form"
        assert select_result.step_id == "edit_group"

        # Edit the group
        user_input = {
            LightGroupEntryOptions.NAME.key: "Original",
            LightGroupEntryOptions.LIGHTS.key: [
                "light.overhead_light",
                "light.task_light",
            ],
            LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
            LightGroupEntryOptions.TURN_ON_WHEN.key: [
                LightGroupTurnOnWhen.AREA_OCCUPIED.value
            ],
            LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                LightGroupTurnOffWhen.AREA_CLEAR.value
            ],
        }

        result = await handler.handle_step("edit_group", user_input)

        assert result.type == "menu"
        assert result.step_id == "main"

        # Verify group was updated
        groups = config_entry.options[ConfigDomains.FEATURES]["light_groups"]["groups"]
        assert len(groups) == 1
        assert len(groups[0][LightGroupEntryOptions.LIGHTS.key]) == 2

    async def test_edit_group_rename_valid(self, light_groups_feature_setup):
        """Test renaming a group to unique name."""
        handler = light_groups_feature_setup["handler"]
        config_entry = light_groups_feature_setup["config_entry"]

        # Add initial group
        config_entry.options[ConfigDomains.FEATURES] = {
            "light_groups": {
                "groups": [
                    {
                        LightGroupEntryOptions.NAME.key: "Original",
                        LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
                        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
                        LightGroupEntryOptions.TURN_ON_WHEN.key: [
                            LightGroupTurnOnWhen.AREA_OCCUPIED.value
                        ],
                        LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                            LightGroupTurnOffWhen.AREA_CLEAR.value
                        ],
                    }
                ]
            }
        }

        # Navigate to select_group step
        select_result = await handler.handle_step("select_group", {"group_index": 0})
        assert select_result.type == "form"
        assert select_result.step_id == "edit_group"

        # Rename the group
        user_input = {
            LightGroupEntryOptions.NAME.key: "Renamed",
            LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
            LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
            LightGroupEntryOptions.TURN_ON_WHEN.key: [
                LightGroupTurnOnWhen.AREA_OCCUPIED.value
            ],
            LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                LightGroupTurnOffWhen.AREA_CLEAR.value
            ],
        }

        result = await handler.handle_step("edit_group", user_input)

        assert result.type == "menu"
        assert result.step_id == "main"

        # Verify group was renamed
        groups = config_entry.options[ConfigDomains.FEATURES]["light_groups"]["groups"]
        assert groups[0][LightGroupEntryOptions.NAME.key] == "Renamed"

    async def test_edit_group_rename_duplicate(self, light_groups_feature_setup):
        """Test renaming to existing group name shows error."""
        handler = light_groups_feature_setup["handler"]
        config_entry = light_groups_feature_setup["config_entry"]

        # Add two groups
        config_entry.options[ConfigDomains.FEATURES] = {
            "light_groups": {
                "groups": [
                    {
                        LightGroupEntryOptions.NAME.key: "Group A",
                        LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
                        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
                        LightGroupEntryOptions.TURN_ON_WHEN.key: [
                            LightGroupTurnOnWhen.AREA_OCCUPIED.value
                        ],
                        LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                            LightGroupTurnOffWhen.AREA_CLEAR.value
                        ],
                    },
                    {
                        LightGroupEntryOptions.NAME.key: "Group B",
                        LightGroupEntryOptions.LIGHTS.key: ["light.overhead_light"],
                        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
                        LightGroupEntryOptions.TURN_ON_WHEN.key: [
                            LightGroupTurnOnWhen.AREA_OCCUPIED.value
                        ],
                        LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                            LightGroupTurnOffWhen.AREA_CLEAR.value
                        ],
                    },
                ]
            }
        }

        # Navigate to select_group and then edit first group
        await handler.handle_step("select_group", {"group_index": 0})

        # Try to rename to second group's name
        user_input = {
            LightGroupEntryOptions.NAME.key: "Group B",
            LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
            LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
            LightGroupEntryOptions.TURN_ON_WHEN.key: [
                LightGroupTurnOnWhen.AREA_OCCUPIED.value
            ],
            LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                LightGroupTurnOffWhen.AREA_CLEAR.value
            ],
        }

        result = await handler.handle_step("edit_group", user_input)

        assert result.type == "form"
        assert result.step_id == "edit_group"
        assert result.errors is not None
        assert "name" in result.errors

    # ========================================================================
    # Delete Group Tests
    # ========================================================================

    async def test_delete_group_confirm(self, light_groups_feature_setup):
        """Test deleting group with confirmation."""
        handler = light_groups_feature_setup["handler"]
        config_entry = light_groups_feature_setup["config_entry"]

        # Add groups
        config_entry.options[ConfigDomains.FEATURES] = {
            "light_groups": {
                "groups": [
                    {
                        LightGroupEntryOptions.NAME.key: "Group 1",
                        LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
                        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
                        LightGroupEntryOptions.TURN_ON_WHEN.key: [
                            LightGroupTurnOnWhen.AREA_OCCUPIED.value
                        ],
                        LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                            LightGroupTurnOffWhen.AREA_CLEAR.value
                        ],
                    },
                    {
                        LightGroupEntryOptions.NAME.key: "Group 2",
                        LightGroupEntryOptions.LIGHTS.key: ["light.overhead_light"],
                        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
                        LightGroupEntryOptions.TURN_ON_WHEN.key: [
                            LightGroupTurnOnWhen.AREA_OCCUPIED.value
                        ],
                        LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                            LightGroupTurnOffWhen.AREA_CLEAR.value
                        ],
                    },
                ]
            }
        }

        # Select first group and confirm deletion
        result = await handler.handle_step(
            "delete_group", {"group_index": 0, "confirm": True}
        )

        assert result.type == "menu"
        assert result.step_id == "main"

        # Verify group was deleted
        groups = config_entry.options[ConfigDomains.FEATURES]["light_groups"]["groups"]
        assert len(groups) == 1
        assert groups[0][LightGroupEntryOptions.NAME.key] == "Group 2"

    async def test_delete_group_cancel(self, light_groups_feature_setup):
        """Test canceling group deletion."""
        handler = light_groups_feature_setup["handler"]
        config_entry = light_groups_feature_setup["config_entry"]

        # Add group
        config_entry.options[ConfigDomains.FEATURES] = {
            "light_groups": {
                "groups": [
                    {
                        LightGroupEntryOptions.NAME.key: "Test",
                        LightGroupEntryOptions.LIGHTS.key: ["light.test_light"],
                        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED.value],
                        LightGroupEntryOptions.TURN_ON_WHEN.key: [
                            LightGroupTurnOnWhen.AREA_OCCUPIED.value
                        ],
                        LightGroupEntryOptions.TURN_OFF_WHEN.key: [
                            LightGroupTurnOffWhen.AREA_CLEAR.value
                        ],
                    }
                ]
            }
        }

        # Select first group but cancel deletion
        result = await handler.handle_step(
            "delete_group", {"group_index": 0, "confirm": False}
        )

        assert result.type == "menu"
        assert result.step_id == "main"

        # Verify group still exists
        groups = config_entry.options[ConfigDomains.FEATURES]["light_groups"]["groups"]
        assert len(groups) == 1

    # ========================================================================
    # Summary Tests
    # ========================================================================

    def test_get_summary_no_groups(self, light_groups_feature_setup):
        """Test summary with no groups."""
        handler = light_groups_feature_setup["handler"]

        summary = handler.get_summary({})
        assert summary == "No groups configured"

    def test_get_summary_with_groups(self, light_groups_feature_setup):
        """Test summary with groups."""
        handler = light_groups_feature_setup["handler"]

        config = {
            "groups": [
                {
                    LightGroupEntryOptions.NAME.key: "Group 1",
                    LightGroupEntryOptions.LIGHTS.key: [
                        "light.test_light",
                        "light.overhead_light",
                    ],
                },
                {
                    LightGroupEntryOptions.NAME.key: "Group 2",
                    LightGroupEntryOptions.LIGHTS.key: ["light.task_light"],
                },
            ]
        }

        summary = handler.get_summary(config)
        assert "2 group(s)" in summary
        assert "3 light(s)" in summary
