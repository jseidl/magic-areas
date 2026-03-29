"""Tests for user-defined states config flow."""

from collections.abc import AsyncGenerator
from unittest.mock import Mock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler
from custom_components.magic_areas.config_flow.user_defined_states import (
    UserDefinedStatesHandler,
)
from custom_components.magic_areas.const import DOMAIN, ConfigDomains
from custom_components.magic_areas.const.user_defined_states import (
    RESERVED_STATE_NAMES,
    UserDefinedStateEntryOptions,
    UserDefinedStateOptions,
    slugify_state_name,
    validate_state_name,
    validate_state_name_unique,
)

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor


class TestUserDefinedStatesHandler:
    """Test UserDefinedStatesHandler class."""

    @pytest.fixture
    async def user_defined_states_handler_setup(
        self, hass: HomeAssistant
    ) -> AsyncGenerator[dict, None]:
        """Set up user-defined states handler for testing."""
        # Create test entities
        test_binary = MockBinarySensor(
            name="movie_mode", unique_id="test_movie_mode", device_class=None
        )

        await setup_mock_entities(
            hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [test_binary]}
        )

        # Create config entry
        config_entry = Mock()
        config_entry.options = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

        # Create flow
        flow = Mock(spec=OptionsFlowHandler)
        flow.hass = hass
        flow.config_entry = config_entry
        flow.area_options = config_entry.options
        flow.all_binary_entities = [test_binary.entity_id]
        flow.area = Mock()  # DomainHandler.__init__ expects this

        # Create handler ONCE (reused across test steps)
        handler = UserDefinedStatesHandler(flow)

        yield {
            "hass": hass,
            "config_entry": config_entry,
            "flow": flow,
            "handler": handler,
            "test_entity_id": test_binary.entity_id,
        }

    # ========================================================================
    # Handler Properties Tests
    # ========================================================================

    def test_handler_properties(self, user_defined_states_handler_setup):
        """Test basic handler properties."""
        handler = user_defined_states_handler_setup["handler"]

        assert handler.domain_id == "user_defined_states"
        assert handler.domain_name == "User-Defined States"
        assert handler.requires_multi_step is True

    # ========================================================================
    # Main Menu Tests
    # ========================================================================

    async def test_main_menu_no_states(self, user_defined_states_handler_setup):
        """Test main menu when no states configured."""
        handler = user_defined_states_handler_setup["handler"]

        result = await handler.handle_step("main", None)

        # Should show main menu with add option
        assert result.type == "menu"
        assert result.step_id == "main"
        assert "user_defined_states_add_state" in result.menu_options
        assert "show_menu" in result.menu_options
        # No edit/delete options when no states exist
        assert "user_defined_states_select_state" not in result.menu_options
        assert "user_defined_states_delete_state" not in result.menu_options
        assert result.description_placeholders["state_count"] == "0"

    async def test_main_menu_with_states(self, user_defined_states_handler_setup):
        """Test main menu shows edit/delete options when states exist."""
        handler = user_defined_states_handler_setup["handler"]
        config_entry = user_defined_states_handler_setup["config_entry"]
        test_entity_id = user_defined_states_handler_setup["test_entity_id"]

        # Add a state
        config_entry.options[ConfigDomains.USER_DEFINED_STATES.value] = {
            UserDefinedStateOptions.STATES.key: [
                {
                    UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                    UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
                }
            ]
        }

        result = await handler.handle_step("main", None)

        assert result.type == "menu"
        assert "user_defined_states_add_state" in result.menu_options
        assert "user_defined_states_select_state" in result.menu_options
        assert "user_defined_states_delete_state" in result.menu_options
        assert "show_menu" in result.menu_options
        assert result.description_placeholders["state_count"] == "1"

    # ========================================================================
    # Add State Tests
    # ========================================================================

    async def test_add_state_valid(self, user_defined_states_handler_setup):
        """Test adding a state with valid data."""
        handler = user_defined_states_handler_setup["handler"]
        config_entry = user_defined_states_handler_setup["config_entry"]
        test_entity_id = user_defined_states_handler_setup["test_entity_id"]

        state_name = "Movie Time"

        user_input = {
            UserDefinedStateEntryOptions.NAME.key: state_name,
            UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
        }

        result = await handler.handle_step("add_state", user_input)

        assert result.type == "menu"
        assert result.step_id == "main"

        # Verify state was added to config_entry.options
        assert ConfigDomains.USER_DEFINED_STATES.value in config_entry.options
        states = config_entry.options[ConfigDomains.USER_DEFINED_STATES.value][
            UserDefinedStateOptions.STATES.key
        ]
        assert len(states) == 1
        assert states[0][UserDefinedStateEntryOptions.NAME.key] == state_name
        assert states[0][UserDefinedStateEntryOptions.ENTITY.key] == test_entity_id

    async def test_add_state_empty_name(self, user_defined_states_handler_setup):
        """Test adding state with empty name shows error."""
        handler = user_defined_states_handler_setup["handler"]
        test_entity_id = user_defined_states_handler_setup["test_entity_id"]

        user_input = {
            UserDefinedStateEntryOptions.NAME.key: "",
            UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
        }

        result = await handler.handle_step("add_state", user_input)

        assert result.type == "form"
        assert result.step_id == "add_state"
        assert result.errors is not None
        assert "name" in result.errors

    async def test_add_state_no_entity(self, user_defined_states_handler_setup):
        """Test adding state with no entity shows error."""
        handler = user_defined_states_handler_setup["handler"]

        user_input = {
            UserDefinedStateEntryOptions.NAME.key: "Test",
            UserDefinedStateEntryOptions.ENTITY.key: "",
        }

        result = await handler.handle_step("add_state", user_input)

        assert result.type == "form"
        assert result.step_id == "add_state"
        assert result.errors is not None
        assert "entity" in result.errors

    async def test_add_state_duplicate_name(self, user_defined_states_handler_setup):
        """Test validation prevents duplicate state names."""
        handler = user_defined_states_handler_setup["handler"]
        config_entry = user_defined_states_handler_setup["config_entry"]
        test_entity_id = user_defined_states_handler_setup["test_entity_id"]

        # Add existing state
        config_entry.options[ConfigDomains.USER_DEFINED_STATES.value] = {
            UserDefinedStateOptions.STATES.key: [
                {
                    UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                    UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
                }
            ]
        }

        # Try to add duplicate
        user_input = {
            UserDefinedStateEntryOptions.NAME.key: "Movie Time",
            UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
        }

        result = await handler.handle_step("add_state", user_input)

        # Should show error
        assert result.type == "form"
        assert result.step_id == "add_state"
        assert "errors" in result.__dict__
        assert "name" in result.errors
        assert result.errors["name"] == "duplicate_state_name"

    async def test_add_state_reserved_name(self, user_defined_states_handler_setup):
        """Test validation prevents reserved state names."""
        handler = user_defined_states_handler_setup["handler"]
        test_entity_id = user_defined_states_handler_setup["test_entity_id"]

        # Try to add reserved name
        user_input = {
            UserDefinedStateEntryOptions.NAME.key: "Occupied",
            UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
        }

        result = await handler.handle_step("add_state", user_input)

        # Should show error
        assert result.type == "form"
        assert "errors" in result.__dict__
        assert "name" in result.errors
        assert result.errors["name"] == "reserved_state_name"

    # ========================================================================
    # Edit State Tests
    # ========================================================================

    async def test_edit_state_valid(self, user_defined_states_handler_setup):
        """Test editing a state successfully."""
        handler = user_defined_states_handler_setup["handler"]
        config_entry = user_defined_states_handler_setup["config_entry"]
        test_entity_id = user_defined_states_handler_setup["test_entity_id"]

        # Add initial state
        config_entry.options[ConfigDomains.USER_DEFINED_STATES.value] = {
            UserDefinedStateOptions.STATES.key: [
                {
                    UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                    UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
                }
            ]
        }

        # Navigate to select_state step (sets _current_index on handler)
        select_result = await handler.handle_step("select_state", {"state_index": 0})
        assert select_result.type == "form"
        assert select_result.step_id == "edit_state"

        # Edit the state
        user_input = {
            UserDefinedStateEntryOptions.NAME.key: "Cinema Mode",
            UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
        }

        result = await handler.handle_step("edit_state", user_input)

        assert result.type == "menu"
        assert result.step_id == "main"

        # Verify state was updated in config_entry.options
        states = config_entry.options[ConfigDomains.USER_DEFINED_STATES.value][
            UserDefinedStateOptions.STATES.key
        ]
        assert len(states) == 1
        assert states[0][UserDefinedStateEntryOptions.NAME.key] == "Cinema Mode"
        assert states[0][UserDefinedStateEntryOptions.ENTITY.key] == test_entity_id

    async def test_edit_state_duplicate_name(self, user_defined_states_handler_setup):
        """Test renaming to existing state name shows error."""
        handler = user_defined_states_handler_setup["handler"]
        config_entry = user_defined_states_handler_setup["config_entry"]
        test_entity_id = user_defined_states_handler_setup["test_entity_id"]

        # Add two states
        config_entry.options[ConfigDomains.USER_DEFINED_STATES.value] = {
            UserDefinedStateOptions.STATES.key: [
                {
                    UserDefinedStateEntryOptions.NAME.key: "State A",
                    UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
                },
                {
                    UserDefinedStateEntryOptions.NAME.key: "State B",
                    UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
                },
            ]
        }

        # Navigate to select_state and edit first state
        await handler.handle_step("select_state", {"state_index": 0})

        # Try to rename to second state's name
        user_input = {
            UserDefinedStateEntryOptions.NAME.key: "State B",
            UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
        }

        result = await handler.handle_step("edit_state", user_input)

        assert result.type == "form"
        assert result.step_id == "edit_state"
        assert result.errors is not None
        assert "name" in result.errors

    # ========================================================================
    # Delete State Tests
    # ========================================================================

    async def test_delete_state_confirm(self, user_defined_states_handler_setup):
        """Test deleting a state with confirmation."""
        handler = user_defined_states_handler_setup["handler"]
        config_entry = user_defined_states_handler_setup["config_entry"]
        test_entity_id = user_defined_states_handler_setup["test_entity_id"]

        # Add states
        config_entry.options[ConfigDomains.USER_DEFINED_STATES.value] = {
            UserDefinedStateOptions.STATES.key: [
                {
                    UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                    UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
                },
                {
                    UserDefinedStateEntryOptions.NAME.key: "Gaming",
                    UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
                },
            ]
        }

        # Select first state and confirm deletion
        result = await handler.handle_step(
            "delete_state", {"state_index": 0, "confirm": True}
        )

        assert result.type == "menu"
        assert result.step_id == "main"

        # Verify state was deleted from config_entry.options
        states = config_entry.options[ConfigDomains.USER_DEFINED_STATES.value][
            UserDefinedStateOptions.STATES.key
        ]
        assert len(states) == 1
        assert states[0][UserDefinedStateEntryOptions.NAME.key] == "Gaming"

    async def test_delete_state_cancel(self, user_defined_states_handler_setup):
        """Test canceling deletion."""
        handler = user_defined_states_handler_setup["handler"]
        config_entry = user_defined_states_handler_setup["config_entry"]
        test_entity_id = user_defined_states_handler_setup["test_entity_id"]

        # Add state
        config_entry.options[ConfigDomains.USER_DEFINED_STATES.value] = {
            UserDefinedStateOptions.STATES.key: [
                {
                    UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                    UserDefinedStateEntryOptions.ENTITY.key: test_entity_id,
                }
            ]
        }

        # Select first state but cancel deletion
        result = await handler.handle_step(
            "delete_state", {"state_index": 0, "confirm": False}
        )

        assert result.type == "menu"
        assert result.step_id == "main"

        # Verify state still exists in config_entry.options
        states = config_entry.options[ConfigDomains.USER_DEFINED_STATES.value][
            UserDefinedStateOptions.STATES.key
        ]
        assert len(states) == 1

    # ========================================================================
    # Flow Integration Tests (Regression Tests)
    # ========================================================================

    async def test_edit_state_handler_persistence(self, hass: HomeAssistant):
        """Test that editing a state works through the actual flow (regression test).

        This test ensures the domain handler is cached and state persists between steps.
        Without caching, _current_index would be lost and edit would fail.
        """
        # Setup: Create config entry with existing state
        test_binary = MockBinarySensor(
            name="movie_mode", unique_id="test_movie", device_class=None
        )

        await setup_mock_entities(
            hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [test_binary]}
        )

        data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
        data[ConfigDomains.USER_DEFINED_STATES.value] = {
            UserDefinedStateOptions.STATES.key: [
                {
                    UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                    UserDefinedStateEntryOptions.ENTITY.key: test_binary.entity_id,
                }
            ]
        }

        # Create mock MagicArea
        magic_area = Mock()
        magic_area.id = DEFAULT_MOCK_AREA.value
        magic_area.name = DEFAULT_MOCK_AREA.value
        magic_area.config = Mock()
        magic_area.config.get = Mock(return_value=None)

        config_entry = MockConfigEntry(domain=DOMAIN, data=data, options=data)
        config_entry.runtime_data = magic_area
        await init_integration(hass, [config_entry])

        # Create flow instance - follow test_flow.py pattern
        flow = OptionsFlowHandler(config_entry)
        flow.hass = hass  # Set hass first (required for config_entry property)
        flow.area = magic_area  # Set directly (what async_step_init does)
        flow.area_options = dict(config_entry.options)  # Mutable copy for modification
        flow.all_binary_entities = [test_binary.entity_id]  # For handler

        # CRITICAL: These steps must use the SAME handler instance

        # Step 1: Navigate to user_defined_states main menu
        result = await flow.async_step_user_defined_states(None)
        assert result["type"] == "menu"

        # Step 2: Navigate to select_state
        result = await flow.async_step_user_defined_states_select_state(None)
        assert result["type"] == "form"
        assert result["step_id"] == "user_defined_states_select_state"

        # Step 3: Select state #0 (this sets handler._current_index = 0)
        result = await flow.async_step_user_defined_states_select_state(
            {"state_index": 0}
        )

        # WITHOUT FIX: New handler created, _current_index lost
        # WITH FIX: Same handler reused, _current_index = 0

        # Step 4: Show edit form (REGRESSION CHECK - should have current values)
        result = await flow.async_step_user_defined_states_edit_state(None)
        assert result["type"] == "form"
        assert result["step_id"] == "user_defined_states_edit_state"

        # Step 5: Submit edited values
        result = await flow.async_step_user_defined_states_edit_state(
            {
                UserDefinedStateEntryOptions.NAME.key: "Cinema Mode",
                UserDefinedStateEntryOptions.ENTITY.key: test_binary.entity_id,
            }
        )

        # Step 6: Verify edit succeeded
        assert result["type"] == "menu"
        assert result["step_id"] == "user_defined_states"

        # Step 7: Verify the state was updated in config
        states = config_entry.options[ConfigDomains.USER_DEFINED_STATES.value][
            UserDefinedStateOptions.STATES.key
        ]
        assert len(states) == 1
        assert states[0][UserDefinedStateEntryOptions.NAME.key] == "Cinema Mode"
        assert (
            states[0][UserDefinedStateEntryOptions.ENTITY.key] == test_binary.entity_id
        )

        await shutdown_integration(hass, [config_entry])

    # ========================================================================
    # Summary Tests
    # ========================================================================

    def test_get_summary_no_states(self, user_defined_states_handler_setup):
        """Test summary with no states."""
        handler = user_defined_states_handler_setup["handler"]

        summary = handler.get_summary({})
        assert summary == "No states configured"

    def test_get_summary_with_states(self, user_defined_states_handler_setup):
        """Test summary with states."""
        handler = user_defined_states_handler_setup["handler"]

        config = {
            UserDefinedStateOptions.STATES.key: [
                {
                    UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                    UserDefinedStateEntryOptions.ENTITY.key: "binary_sensor.test",
                },
                {
                    UserDefinedStateEntryOptions.NAME.key: "Gaming",
                    UserDefinedStateEntryOptions.ENTITY.key: "binary_sensor.test2",
                },
            ]
        }

        summary = handler.get_summary(config)
        assert "2 state(s)" in summary


class TestValidationHelpers:
    """Test validation helper functions."""

    def test_validate_state_name_reserved(self):
        """Test reserved name validation."""
        # Reserved names should fail
        for reserved in RESERVED_STATE_NAMES:
            assert not validate_state_name(reserved)
            assert not validate_state_name(str(reserved).upper())
            assert not validate_state_name(str(reserved).replace("_", " ").title())

        # Non-reserved should pass
        assert validate_state_name("Movie Time")
        assert validate_state_name("Gaming Mode")

    def test_validate_state_name_unique(self):
        """Test uniqueness validation."""
        existing = [
            {"name": "Movie Time", "entity": "test.entity"},
            {"name": "Gaming", "entity": "test.entity2"},
        ]

        # Duplicate should fail
        assert not validate_state_name_unique("Movie Time", existing)
        assert not validate_state_name_unique(
            "movie time", existing
        )  # case insensitive
        assert not validate_state_name_unique("Gaming", existing)

        # Unique should pass
        assert validate_state_name_unique("Party Mode", existing)
        assert validate_state_name_unique("Relax", existing)

    def test_validate_state_name_unique_with_exclusion(self):
        """Test uniqueness validation with exclusion index."""
        existing = [
            {"name": "Movie Time", "entity": "test.entity"},
            {"name": "Gaming", "entity": "test.entity2"},
        ]

        # Same name at same index should pass (editing)
        assert validate_state_name_unique("Movie Time", existing, exclude_index=0)
        assert validate_state_name_unique("Gaming", existing, exclude_index=1)

        # Same name at different index should fail
        assert not validate_state_name_unique("Movie Time", existing, exclude_index=1)
        assert not validate_state_name_unique("Gaming", existing, exclude_index=0)

    def test_slugify_state_name_consistency(self):
        """Test slugification produces consistent results."""
        assert slugify_state_name("Movie Time") == slugify_state_name("movie time")
        assert slugify_state_name("Movie Time") == slugify_state_name("MOVIE TIME")
        assert slugify_state_name("Movie Time") == slugify_state_name("  Movie Time  ")
