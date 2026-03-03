"""Light groups feature handler - arbitrary user-defined groups."""

import logging

import voluptuous as vol

from custom_components.magic_areas.config_flow.features import register_feature
from custom_components.magic_areas.config_flow.features.base import (
    FeatureHandler,
    StepResult,
)
from custom_components.magic_areas.config_flow.helpers import (
    SchemaBuilder,
    StateOptionsBuilder,
)
from custom_components.magic_areas.const import (
    AreaConfigOptions,
    AreaType,
    ConfigOption,
    Features,
)
from custom_components.magic_areas.const.light_groups import (
    LightGroupEntryOptions,
    validate_group_name,
    validate_group_name_unique,
)

_LOGGER = logging.getLogger(__name__)


@register_feature
class LightGroupsFeature(FeatureHandler):
    """Handler for arbitrary user-defined light groups."""

    def __init__(self, flow):
        """Initialize the handler."""
        super().__init__(flow)
        # State for tracking current operation
        self._operation = None  # "add", "edit", "delete"
        self._current_index = None
        self._partial_group = {}  # Collects data across add/edit steps

    @property
    def feature_id(self) -> str:
        """Return feature identifier."""
        return Features.LIGHT_GROUPS

    @property
    def feature_name(self) -> str:
        """Return feature display name."""
        return "Light Groups"

    @property
    def is_available(self) -> bool:
        """Not available for meta areas."""
        return self.area.config.get(AreaConfigOptions.TYPE) != AreaType.META

    async def handle_step(self, step_id: str, user_input: dict | None) -> StepResult:
        """Route to appropriate step handler."""
        _LOGGER.warning(
            "LG HANDLING STEPS step_id=%s user_input=%s", step_id, str(user_input)
        )
        if step_id == "main":
            _LOGGER.warning("LG HANDLING STEPS :: MAIN")
            return await self._step_main(user_input)
        if step_id == "add_group":
            _LOGGER.warning("LG HANDLING STEPS :: ADD")
            return await self._step_add_group(user_input)
        if step_id == "select_group":
            _LOGGER.warning("LG HANDLING STEPS :: SELECT GROUP")
            return await self._step_select_group(user_input)
        if step_id == "edit_group":
            _LOGGER.warning("LG HANDLING STEPS :: EDIT")
            return await self._step_edit_group(user_input)
        if step_id == "delete_group":
            _LOGGER.warning("LG HANDLING STEPS :: DELETE")
            return await self._step_delete_group(user_input)

        return await self._step_main(user_input)

    # ========================================================================
    # Main Menu
    # ========================================================================

    def _build_main_menu_result(self) -> StepResult:
        """Build main menu result with current group stats."""
        config = self.get_config()
        groups = config.get("groups", [])
        total_lights = sum(len(g.get("lights", [])) for g in groups)

        menu_options = ["feature_light_groups_add_group"]

        # Only show edit/delete if there are groups
        if groups:
            menu_options.append("feature_light_groups_select_group")
            menu_options.append("feature_light_groups_delete_group")

        menu_options.append("show_menu")

        return StepResult(
            type="menu",
            step_id="main",
            menu_options=menu_options,
            description_placeholders={
                "group_count": str(len(groups)),
                "total_lights": str(total_lights),
            },
        )

    async def _step_main(self, user_input: dict | None) -> StepResult:
        """Display main menu with actions."""
        return self._build_main_menu_result()

    # ========================================================================
    # Select Group (for editing)
    # ========================================================================

    async def _step_select_group(self, user_input: dict | None) -> StepResult:
        """Select which group to edit."""
        config = self.get_config()
        groups = config.get("groups", [])

        if user_input is not None:
            # Get selected group index
            group_index = user_input.get("group_index")

            if group_index is not None and 0 <= group_index < len(groups):
                self._operation = "edit"
                self._current_index = group_index
                # Load current group data
                self._partial_group = groups[group_index].copy()
                return StepResult(type="form", step_id="edit_group")

            # Invalid selection, return to main menu
            return self._build_main_menu_result()

        # Build dropdown with sorted groups
        sorted_groups = sorted(enumerate(groups), key=lambda x: x[1].get("name", ""))
        group_options = {}
        for idx, group in sorted_groups:
            name = group["name"]
            light_count = len(group.get("lights", []))
            state_count = len(group.get("states", []))
            group_options[idx] = f"{name} ({light_count} lights, {state_count} states)"

        return StepResult(
            type="form",
            step_id="select_group",
            data_schema=vol.Schema(
                {vol.Required("group_index"): vol.In(group_options)}
            ),
        )

    # ========================================================================
    # Add Group (Single Form)
    # ========================================================================

    async def _step_add_group(self, user_input: dict | None) -> StepResult:
        """Add a new light group - single form with all fields."""

        _LOGGER.warning("ADD G START")

        if user_input is not None:
            # Validate all fields
            errors = {}

            # Validate name
            name = user_input.get("name", "").strip()
            if not name:
                errors["name"] = "malformed_input"
            else:
                # Check uniqueness (no exclusion needed for add)
                config = self.get_config()
                groups = config.get("groups", [])
                if not validate_group_name_unique(name, groups, exclude_index=None):
                    errors["name"] = "duplicate_group_name"

            # Validate lights
            lights = user_input.get("lights", [])
            if not lights:
                errors["lights"] = "no_lights_selected"

            # Validate reserved name
            if name and not validate_group_name(name):
                errors["name"] = "reserved_name"

            # If validation failed, show errors
            if errors:
                return StepResult(
                    type="form",
                    step_id="add_group",
                    data_schema=self._build_group_schema(),
                    errors=errors,
                )

            # Create new group
            # new_group = {
            #     LightGroupEntryOptions.NAME.key: name,
            #     LightGroupEntryOptions.LIGHTS.key: lights,
            #     LightGroupEntryOptions.STATES.key: user_input.get(
            #         LightGroupEntryOptions.STATES.key,
            #         LightGroupEntryOptions.STATES.default,
            #     ),
            #     LightGroupEntryOptions.TURN_ON_WHEN.key: user_input.get(
            #         LightGroupEntryOptions.TURN_ON_WHEN.key,
            #         LightGroupEntryOptions.TURN_ON_WHEN.default,
            #     ),
            #     LightGroupEntryOptions.TURN_OFF_WHEN.key: user_input.get(
            #         LightGroupEntryOptions.TURN_OFF_WHEN.key,
            #         LightGroupEntryOptions.TURN_OFF_WHEN.default,
            #     ),
            #     LightGroupEntryOptions.REQUIRE_DARK.key: user_input.get(
            #         LightGroupEntryOptions.REQUIRE_DARK.key,
            #         LightGroupEntryOptions.REQUIRE_DARK.default,
            #     ),
            # }
            new_group = LightGroupEntryOptions.from_user_input(user_input)

            # Add to config
            config = self.get_config()
            groups = config.get("groups", [])
            groups.append(new_group)
            config["groups"] = groups
            self.save_config(config)

            # Reset state and return to main menu
            self._operation = None
            self._partial_group = {}

            return self._build_main_menu_result()

        _LOGGER.warning("CREATING GS")

        group_schema = self._build_group_schema()

        _LOGGER.warning("GS: --> %s", str(group_schema))

        # Show form
        return StepResult(
            type="form",
            step_id="add_group",
            data_schema=group_schema,
        )

    # ========================================================================
    # Edit Group (Single Form)
    # ========================================================================

    async def _step_edit_group(self, user_input: dict | None) -> StepResult:
        """Edit an existing light group - single form with all fields."""
        if user_input is not None:
            # Validate all fields
            errors = {}

            # Validate name
            name = user_input.get("name", "").strip()
            if not name:
                errors["name"] = "malformed_input"
            else:
                # Check uniqueness (excluding current group)
                config = self.get_config()
                groups = config.get("groups", [])
                if not validate_group_name_unique(
                    name, groups, exclude_index=self._current_index
                ):
                    errors["name"] = "duplicate_group_name"

            # Validate lights
            lights = user_input.get("lights", [])
            if not lights:
                errors["lights"] = "no_lights_selected"

            # Validate reserved name
            if name and not validate_group_name(name):
                errors["name"] = "reserved_name"

            # If validation failed, show errors
            if errors:
                return StepResult(
                    type="form",
                    step_id="edit_group",
                    data_schema=self._build_group_schema(self._partial_group),
                    errors=errors,
                )

            # Update group at index
            # updated_group = {
            #     LightGroupEntryOptions.NAME.key: name,
            #     LightGroupEntryOptions.LIGHTS.key: lights,
            #     LightGroupEntryOptions.STATES.key: user_input.get(
            #         LightGroupEntryOptions.STATES.key,
            #         LightGroupEntryOptions.STATES.default,
            #     ),
            #     LightGroupEntryOptions.TURN_ON_WHEN.key: user_input.get(
            #         LightGroupEntryOptions.TURN_ON_WHEN.key,
            #         LightGroupEntryOptions.TURN_ON_WHEN.default,
            #     ),
            #     LightGroupEntryOptions.TURN_OFF_WHEN.key: user_input.get(
            #         LightGroupEntryOptions.TURN_OFF_WHEN.key,
            #         LightGroupEntryOptions.TURN_OFF_WHEN.default,
            #     ),
            #     LightGroupEntryOptions.REQUIRE_DARK.key: user_input.get(
            #         LightGroupEntryOptions.REQUIRE_DARK.key,
            #         LightGroupEntryOptions.REQUIRE_DARK.default,
            #     ),
            # }
            updated_group = LightGroupEntryOptions.from_user_input(user_input)

            # Update in config
            config = self.get_config()
            groups = config.get("groups", [])
            groups[self._current_index] = updated_group
            config["groups"] = groups
            self.save_config(config)

            # Reset state and return to main menu
            self._operation = None
            self._partial_group = {}
            self._current_index = None

            return self._build_main_menu_result()

        # Show form with current values
        return StepResult(
            type="form",
            step_id="edit_group",
            data_schema=self._build_group_schema(self._partial_group),
        )

    # ========================================================================
    # Delete Group Flow
    # ========================================================================

    async def _step_delete_group(self, user_input: dict | None) -> StepResult:
        """Delete a group - single form with selection and confirmation."""
        config = self.get_config()
        groups = config.get("groups", [])

        if user_input is not None:
            # Check if confirmed
            if not user_input.get("confirm", False):
                # Not confirmed, return to main menu
                self._operation = None
                return self._build_main_menu_result()

            # Get selected group INDEX directly
            group_index = user_input.get("group_index")

            if group_index is not None and 0 <= group_index < len(groups):
                # Delete the group at index
                groups.pop(group_index)
                config["groups"] = groups
                self.save_config(config)

            # Reset and return to main menu
            self._operation = None
            return self._build_main_menu_result()

        # Build dropdown: {index: name} for display
        group_options = {idx: group["name"] for idx, group in enumerate(groups)}

        return StepResult(
            type="form",
            step_id="delete_group",
            data_schema=vol.Schema(
                {
                    vol.Required("group_index"): vol.In(group_options),
                    vol.Required("confirm", default=False): bool,
                }
            ),
        )

    # ========================================================================
    # Schema Builders
    # ========================================================================

    def _build_group_schema(self, current_values: dict | None = None) -> vol.Schema:
        """Build schema for group form (add or edit).

        Args:
            current_values: Current group values for edit mode (None for add mode)

        """
        _LOGGER.debug(
            "Light Groups: _build_group_schema() called with current_values: %s",
            current_values,
        )

        try:
            if current_values is None:
                current_values = {}

            # Get available lights
            _LOGGER.debug("Light Groups: Getting all_lights...")
            lights = self.all_lights
            _LOGGER.debug("Light Groups: all_lights = %s", lights)

            if not lights:
                lights = []

            # Get available states using helper
            _LOGGER.debug("Light Groups: Building available states...")
            available_states = StateOptionsBuilder.build_available_states(
                self.flow.area
            )
            available_states = StateOptionsBuilder.for_light_groups(available_states)
            _LOGGER.debug("Light Groups: available_states = %s", available_states)

            # Build selector overrides for dynamic options
            _LOGGER.debug("Light Groups: Building selector_overrides...")
            selector_overrides = {
                LightGroupEntryOptions.LIGHTS.key: self.flow.build_selector_entity_simple(
                    options=lights,
                    multiple=True,
                ),
                LightGroupEntryOptions.STATES.key: self.flow.build_selector_select(
                    options=available_states,
                    multiple=True,
                    translation_key=LightGroupEntryOptions.STATES.key,
                ),
            }
            _LOGGER.debug(
                "Light Groups: selector_overrides keys = %s",
                list(selector_overrides.keys()),
            )

            # Use SchemaBuilder to auto-generate schema
            _LOGGER.debug("Light Groups: Creating SchemaBuilder with current_values...")

            # For add mode (empty current_values), auto-populate with defaults from ConfigOptions
            schema_values = current_values.copy() if current_values else {}
            if not schema_values:
                # Add mode - ensure proper defaults from ConfigOption definitions
                for attr_name in dir(LightGroupEntryOptions):
                    if attr_name.startswith("_"):
                        continue
                    attr = getattr(LightGroupEntryOptions, attr_name)
                    if isinstance(attr, ConfigOption):
                        schema_values[attr.key] = attr.default

            builder = SchemaBuilder(schema_values)

            _LOGGER.debug("Light Groups: Calling builder.from_option_set()...")
            schema = builder.from_option_set(
                LightGroupEntryOptions,
                saved_config=schema_values,
                selector_overrides=selector_overrides,
            )

            # Check if schema is empty (indicates validation error)
            if not schema.schema:
                _LOGGER.error(
                    "Light Groups: Schema validation failed - empty schema returned. "
                    "Check logs for missing selector configuration."
                )
                return vol.Schema({})

            _LOGGER.debug(
                "Light Groups: Built schema with %d fields: %s",
                len(schema.schema),
                list(schema.schema.keys()),
            )

            return schema

        except Exception as exc:  # pylint: disable=broad-exception-caught
            _LOGGER.error(
                "Light Groups: Exception in _build_group_schema: %s", exc, exc_info=True
            )
            # Return empty schema to prevent crash
            return vol.Schema({})

    # ========================================================================
    # Summary
    # ========================================================================

    def get_summary(self, config: dict) -> str:
        """Generate summary showing group count and total lights."""
        groups = config.get("groups", [])
        if not groups:
            return "No groups configured"

        total_lights = sum(len(g.get("lights", [])) for g in groups)
        return f"{len(groups)} group(s), {total_lights} light(s)"
