"""User-defined states domain handler."""

import logging

import voluptuous as vol

from custom_components.magic_areas.config_flow.domain_handlers import (
    DomainHandler,
    DomainStepResult,
)
from custom_components.magic_areas.config_flow.helpers import SchemaBuilder
from custom_components.magic_areas.const import ConfigDomains
from custom_components.magic_areas.const.user_defined_states import (
    UserDefinedStateEntryOptions,
    UserDefinedStateOptions,
    slugify_state_name,
    validate_state_name,
    validate_state_name_unique,
)

_LOGGER = logging.getLogger(__name__)


class UserDefinedStatesHandler(DomainHandler):
    """Handler for user-defined custom states configuration."""

    def __init__(self, flow):
        """Initialize the handler."""
        super().__init__(flow)
        # State for tracking current operation
        self._operation = None  # "add", "edit", "delete"
        self._current_index = None
        self._partial_state = {}  # Collects data across add/edit steps

    @property
    def domain_id(self) -> str:
        """Return domain identifier."""
        return "user_defined_states"

    @property
    def domain_name(self) -> str:
        """Return domain display name."""
        return "User-Defined States"

    @property
    def requires_multi_step(self) -> bool:
        """This domain requires multi-step flow."""
        return True

    async def handle_step(
        self, step_id: str, user_input: dict | None
    ) -> DomainStepResult:
        """Route to appropriate step handler."""
        _LOGGER.debug(
            "UserDefinedStates: Handling step '%s' with input: %s", step_id, user_input
        )

        if step_id == "main":
            return await self._step_main(user_input)
        if step_id == "add_state":
            return await self._step_add_state(user_input)
        if step_id == "select_state":
            return await self._step_select_state(user_input)
        if step_id == "edit_state":
            return await self._step_edit_state(user_input)
        if step_id == "delete_state":
            return await self._step_delete_state(user_input)

        return await self._step_main(user_input)

    # ========================================================================
    # Main Menu
    # ========================================================================

    def _build_main_menu_result(self) -> DomainStepResult:
        """Build main menu result with current state stats."""
        config = self.get_config()
        states = config.get(UserDefinedStateOptions.STATES.key, [])

        menu_options = ["user_defined_states_add_state"]

        # Only show edit/delete if there are states
        if states:
            menu_options.append("user_defined_states_select_state")
            menu_options.append("user_defined_states_delete_state")

        menu_options.append("show_menu")

        return DomainStepResult(
            type="menu",
            step_id="main",
            menu_options=menu_options,
            description_placeholders={
                "state_count": str(len(states)),
            },
        )

    async def _step_main(self, user_input: dict | None) -> DomainStepResult:
        """Display main menu with actions."""
        return self._build_main_menu_result()

    # ========================================================================
    # Select State (for editing)
    # ========================================================================

    async def _step_select_state(self, user_input: dict | None) -> DomainStepResult:
        """Select which state to edit."""
        config = self.get_config()
        states = config.get(UserDefinedStateOptions.STATES.key, [])

        if user_input is not None:
            # Get selected state index
            state_index = user_input.get("state_index")

            if state_index is not None and 0 <= state_index < len(states):
                self._operation = "edit"
                self._current_index = state_index
                # Load current state data
                self._partial_state = states[state_index].copy()
                return DomainStepResult(type="form", step_id="edit_state")

            # Invalid selection, return to main menu
            return self._build_main_menu_result()

        # Build dropdown with sorted states
        sorted_states = sorted(enumerate(states), key=lambda x: x[1].get("name", ""))
        state_options = {}
        for idx, state in sorted_states:
            name = state.get(UserDefinedStateEntryOptions.NAME.key, "")
            entity = state.get(UserDefinedStateEntryOptions.ENTITY.key, "")
            state_options[idx] = f"{name} ({entity})"

        return DomainStepResult(
            type="form",
            step_id="select_state",
            data_schema=vol.Schema(
                {vol.Required("state_index"): vol.In(state_options)}
            ),
        )

    # ========================================================================
    # Add State (Single Form)
    # ========================================================================

    async def _step_add_state(self, user_input: dict | None) -> DomainStepResult:
        """Add a new user-defined state - single form with all fields."""

        if user_input is not None:
            # Validate all fields
            errors = {}

            # Validate name
            name = user_input.get(UserDefinedStateEntryOptions.NAME.key, "").strip()
            if not name:
                errors[UserDefinedStateEntryOptions.NAME.key] = "malformed_input"
            else:
                # Check uniqueness (no exclusion needed for add)
                config = self.get_config()
                states = config.get(UserDefinedStateOptions.STATES.key, [])
                if not validate_state_name_unique(name, states, exclude_index=None):
                    errors[UserDefinedStateEntryOptions.NAME.key] = (
                        "duplicate_state_name"
                    )

                # Validate reserved name
                if name and not validate_state_name(name):
                    errors[UserDefinedStateEntryOptions.NAME.key] = (
                        "reserved_state_name"
                    )

            # Validate entity
            entity = user_input.get(UserDefinedStateEntryOptions.ENTITY.key, "")
            if not entity:
                errors[UserDefinedStateEntryOptions.ENTITY.key] = "no_entity_selected"

            # If validation failed, show errors
            if errors:
                return DomainStepResult(
                    type="form",
                    step_id="add_state",
                    data_schema=self._build_state_schema(),
                    errors=errors,
                )

            # Create new state using from_user_input
            new_state = UserDefinedStateEntryOptions.from_user_input(user_input)

            # Add to config
            config = self.get_config()
            states = config.get(UserDefinedStateOptions.STATES.key, [])
            states.append(new_state)
            config[UserDefinedStateOptions.STATES.key] = states
            self.save_config(config)

            # Reset state and return to main menu
            self._operation = None
            self._partial_state = {}

            return self._build_main_menu_result()

        # Show form
        return DomainStepResult(
            type="form",
            step_id="add_state",
            data_schema=self._build_state_schema(),
        )

    # ========================================================================
    # Edit State (Single Form)
    # ========================================================================

    async def _step_edit_state(self, user_input: dict | None) -> DomainStepResult:
        """Edit an existing user-defined state - single form with all fields."""
        if user_input is not None:
            # Validate all fields
            errors = {}

            # Validate name
            name = user_input.get(UserDefinedStateEntryOptions.NAME.key, "").strip()
            if not name:
                errors[UserDefinedStateEntryOptions.NAME.key] = "malformed_input"
            else:
                # Check uniqueness (excluding current state)
                config = self.get_config()
                states = config.get(UserDefinedStateOptions.STATES.key, [])
                if not validate_state_name_unique(
                    name, states, exclude_index=self._current_index
                ):
                    errors[UserDefinedStateEntryOptions.NAME.key] = (
                        "duplicate_state_name"
                    )

                # Validate reserved name
                if name and not validate_state_name(name):
                    errors[UserDefinedStateEntryOptions.NAME.key] = (
                        "reserved_state_name"
                    )

            # Validate entity
            entity = user_input.get(UserDefinedStateEntryOptions.ENTITY.key, "")
            if not entity:
                errors[UserDefinedStateEntryOptions.ENTITY.key] = "no_entity_selected"

            # If validation failed, show errors
            if errors:
                return DomainStepResult(
                    type="form",
                    step_id="edit_state",
                    data_schema=self._build_state_schema(self._partial_state),
                    errors=errors,
                )

            # Update state using from_user_input
            updated_state = UserDefinedStateEntryOptions.from_user_input(user_input)

            # Update in config
            config = self.get_config()
            states = config.get(UserDefinedStateOptions.STATES.key, [])
            states[self._current_index] = updated_state
            config[UserDefinedStateOptions.STATES.key] = states
            self.save_config(config)

            # Reset state and return to main menu
            self._operation = None
            self._partial_state = {}
            self._current_index = None

            return self._build_main_menu_result()

        # Show form with current values
        return DomainStepResult(
            type="form",
            step_id="edit_state",
            data_schema=self._build_state_schema(self._partial_state),
        )

    # ========================================================================
    # Delete State Flow
    # ========================================================================

    async def _step_delete_state(self, user_input: dict | None) -> DomainStepResult:
        """Delete a state - single form with selection and confirmation."""
        config = self.get_config()
        states = config.get(UserDefinedStateOptions.STATES.key, [])

        if user_input is not None:
            # Check if confirmed
            if not user_input.get("confirm", False):
                # Not confirmed, return to main menu
                self._operation = None
                return self._build_main_menu_result()

            # Get selected state INDEX directly
            state_index = user_input.get("state_index")

            if state_index is not None and 0 <= state_index < len(states):
                # Delete the state at index
                states.pop(state_index)
                config[UserDefinedStateOptions.STATES.key] = states
                self.save_config(config)

            # Reset and return to main menu
            self._operation = None
            return self._build_main_menu_result()

        # Build dropdown: {index: name} for display
        state_options = {
            idx: state.get(UserDefinedStateEntryOptions.NAME.key, "")
            for idx, state in enumerate(states)
        }

        return DomainStepResult(
            type="form",
            step_id="delete_state",
            data_schema=vol.Schema(
                {
                    vol.Required("state_index"): vol.In(state_options),
                    vol.Required("confirm", default=False): bool,
                }
            ),
        )

    # ========================================================================
    # Schema Builders
    # ========================================================================

    def _build_state_schema(self, current_values: dict | None = None) -> vol.Schema:
        """Build schema for state form (add or edit).

        Args:
            current_values: Current state values for edit mode (None for add mode)

        """
        if current_values is None:
            current_values = {}

        # Get available binary entities (binary_sensor, switch, input_boolean)
        binary_entities = self.flow.all_binary_entities

        # Build selector overrides for dynamic options
        selector_overrides = {
            UserDefinedStateEntryOptions.ENTITY.key: self.flow.build_selector_entity_simple(
                binary_entities
            ),
        }

        # Use SchemaBuilder to auto-generate schema
        builder = SchemaBuilder(current_values)
        schema = builder.from_option_set(
            UserDefinedStateEntryOptions, selector_overrides=selector_overrides
        )

        return schema

    # ========================================================================
    # Config Management
    # ========================================================================

    def get_config(self) -> dict:
        """Get current user-defined states configuration."""
        return self.area_options.get(ConfigDomains.USER_DEFINED_STATES.value, {})

    def save_config(self, config: dict) -> None:
        """Save user-defined states configuration."""
        if ConfigDomains.USER_DEFINED_STATES.value not in self.area_options:
            self.area_options[ConfigDomains.USER_DEFINED_STATES.value] = {}
        self.area_options[ConfigDomains.USER_DEFINED_STATES.value] = config

    def get_summary(self, config: dict) -> str:
        """Generate summary showing state count."""
        states = config.get(UserDefinedStateOptions.STATES.key, [])
        if not states:
            return "No states configured"

        return f"{len(states)} state(s) configured"
