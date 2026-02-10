"""Light groups feature handler - arbitrary user-defined groups."""

import logging
from typing import Optional

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from custom_components.magic_areas.const import Features
from custom_components.magic_areas.const.light_groups import (
    LightGroupActOn,
    LightGroupEntryOptions,
    LightGroupOptions,
    generate_group_uuid,
    validate_group_name,
    validate_group_name_unique,
)
from custom_components.magic_areas.config_flow.features import register_feature
from custom_components.magic_areas.config_flow.features.base import (
    FeatureHandler,
    StepResult,
)
from custom_components.magic_areas.config_flow.helpers import (
    SchemaBuilder,
    StateOptionsBuilder,
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
        self._current_uuid = None
        self._partial_group = {}  # Collects data across add/edit steps

    @property
    def feature_id(self) -> str:
        return Features.LIGHT_GROUPS

    @property
    def feature_name(self) -> str:
        return "Light Groups"

    def get_initial_step(self) -> str:
        return "main"

    async def handle_step(self, step_id: str, user_input: Optional[dict]) -> StepResult:
        """Route to appropriate step handler."""
        if step_id == "main":
            return await self._step_main(user_input)
        elif step_id == "add_group":
            return await self._step_add_group(user_input)
        elif step_id == "edit_group":
            return await self._step_edit_group(user_input)
        elif step_id == "delete_confirm":
            return await self._step_delete_confirm(user_input)

        return await self._step_main(user_input)

    # ========================================================================
    # Main Menu
    # ========================================================================

    async def _step_main(self, user_input: Optional[dict]) -> StepResult:
        """Main menu with list of groups and actions."""
        if user_input is not None:
            selection = user_input["action"]
            if selection == "done":
                return StepResult(type="create_entry")
            elif selection == "add":
                self._operation = "add"
                return StepResult(type="form", step_id="add_group")
            elif selection.startswith("edit_"):
                self._operation = "edit"
                self._current_uuid = selection[5:]  # Extract UUID
                # Load current group data
                config = self.get_config()
                groups = config.get("groups", [])
                for group in groups:
                    if group["uuid"] == self._current_uuid:
                        self._partial_group = group.copy()
                        break
                return StepResult(type="form", step_id="edit_group")
            elif selection.startswith("delete_"):
                self._operation = "delete"
                self._current_uuid = selection[7:]  # Extract UUID
                return StepResult(type="form", step_id="delete_confirm")

        # Build menu showing existing groups
        config = self.get_config()
        groups = config.get("groups", [])

        menu = {"add": "➕ Add New Group"}

        # Sort groups alphabetically for display
        sorted_groups = sorted(groups, key=lambda g: g.get("name", ""))

        for group in sorted_groups:
            group_uuid = group["uuid"]
            name = group["name"]
            light_count = len(group.get("lights", []))
            state_count = len(group.get("states", []))

            menu[f"edit_{group_uuid}"] = (
                f"✏️  {name} ({light_count} lights, {state_count} states)"
            )

        for group in sorted_groups:
            group_uuid = group["uuid"]
            name = group["name"]
            menu[f"delete_{group_uuid}"] = f"🗑️  Delete {name}"

        menu["done"] = "✓ Done"

        total_lights = sum(len(g.get("lights", [])) for g in groups)

        return StepResult(
            type="form",
            step_id="main",
            data_schema=vol.Schema({vol.Required("action"): vol.In(menu)}),
            description_placeholders={
                "group_count": str(len(groups)),
                "total_lights": str(total_lights),
            },
        )

    # ========================================================================
    # Add Group (Single Form)
    # ========================================================================

    async def _step_add_group(self, user_input: Optional[dict]) -> StepResult:
        """Add a new light group - single form with all fields."""
        if user_input is not None:
            # Validate all fields
            errors = {}

            # Validate name
            name = user_input.get("name", "").strip()
            if not name:
                errors["name"] = "malformed_input"
            else:
                # Check uniqueness
                config = self.get_config()
                groups = config.get("groups", [])
                if not validate_group_name_unique(name, groups):
                    errors["name"] = "duplicate_group_name"

            # Validate lights
            lights = user_input.get("lights", [])
            if not lights:
                errors["lights"] = "no_lights_selected"

            # Validate icon format
            icon = user_input.get("icon", LightGroupEntryOptions.ICON.default)
            if icon and not icon.startswith("mdi:"):
                errors["icon"] = "invalid_icon"

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

            # Create new group (UUID auto-generated, never shown to user)
            new_group = {
                LightGroupEntryOptions.UUID.key: generate_group_uuid(),
                LightGroupEntryOptions.NAME.key: name,
                LightGroupEntryOptions.LIGHTS.key: lights,
                LightGroupEntryOptions.STATES.key: user_input.get(
                    LightGroupEntryOptions.STATES.key,
                    LightGroupEntryOptions.STATES.default,
                ),
                LightGroupEntryOptions.ACT_ON.key: user_input.get(
                    LightGroupEntryOptions.ACT_ON.key,
                    LightGroupEntryOptions.ACT_ON.default,
                ),
                LightGroupEntryOptions.ICON.key: icon,
            }

            # Add to config
            config = self.get_config()
            groups = config.get("groups", [])
            groups.append(new_group)
            config["groups"] = groups
            self.save_config(config)

            # Reset state and return to main
            self._operation = None
            self._partial_group = {}

            return StepResult(type="form", step_id="main")

        # Show form
        return StepResult(
            type="form",
            step_id="add_group",
            data_schema=self._build_group_schema(),
        )

    # ========================================================================
    # Edit Group (Single Form)
    # ========================================================================

    async def _step_edit_group(self, user_input: Optional[dict]) -> StepResult:
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
                    name, groups, exclude_uuid=self._current_uuid
                ):
                    errors["name"] = "duplicate_group_name"

            # Validate lights
            lights = user_input.get("lights", [])
            if not lights:
                errors["lights"] = "no_lights_selected"

            # Validate icon format
            icon = user_input.get("icon", LightGroupEntryOptions.ICON.default)
            if icon and not icon.startswith("mdi:"):
                errors["icon"] = "invalid_icon"

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

            # Update group (preserve UUID)
            updated_group = {
                LightGroupEntryOptions.UUID.key: self._current_uuid,
                LightGroupEntryOptions.NAME.key: name,
                LightGroupEntryOptions.LIGHTS.key: lights,
                LightGroupEntryOptions.STATES.key: user_input.get(
                    LightGroupEntryOptions.STATES.key,
                    LightGroupEntryOptions.STATES.default,
                ),
                LightGroupEntryOptions.ACT_ON.key: user_input.get(
                    LightGroupEntryOptions.ACT_ON.key,
                    LightGroupEntryOptions.ACT_ON.default,
                ),
                LightGroupEntryOptions.ICON.key: icon,
            }

            # Update in config
            config = self.get_config()
            groups = config.get("groups", [])
            for i, group in enumerate(groups):
                if group["uuid"] == self._current_uuid:
                    groups[i] = updated_group
                    break
            config["groups"] = groups
            self.save_config(config)

            # Reset state and return to main
            self._operation = None
            self._partial_group = {}
            self._current_uuid = None

            return StepResult(type="form", step_id="main")

        # Show form with current values
        return StepResult(
            type="form",
            step_id="edit_group",
            data_schema=self._build_group_schema(self._partial_group),
        )

    # ========================================================================
    # Delete Group Flow
    # ========================================================================

    async def _step_delete_confirm(self, user_input: Optional[dict]) -> StepResult:
        """Confirm group deletion."""
        if user_input is not None:
            if user_input.get("confirm", False):
                # Delete group
                config = self.get_config()
                groups = config.get("groups", [])
                groups = [g for g in groups if g["uuid"] != self._current_uuid]

                # Save and return to main menu
                config["groups"] = groups
                self.save_config(config)

            # Reset state and return to main
            self._operation = None
            self._partial_group = {}
            self._current_uuid = None

            return StepResult(type="form", step_id="main")

        # Find group name for display
        config = self.get_config()
        groups = config.get("groups", [])
        group_name = "Unknown"
        for group in groups:
            if group["uuid"] == self._current_uuid:
                group_name = group["name"]
                break

        return StepResult(
            type="form",
            step_id="delete_confirm",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"group_name": group_name},
        )

    # ========================================================================
    # Schema Builders
    # ========================================================================

    def _build_group_schema(self, current_values: Optional[dict] = None) -> vol.Schema:
        """
        Build schema for group form (add or edit).

        Args:
            current_values: Current group values for edit mode (None for add mode)
        """
        if current_values is None:
            current_values = {}

        # Get available lights
        lights = self.all_lights
        if not lights:
            lights = []

        # Get available states based on secondary states config
        secondary_states = self.area_options.get("secondary_states", {})
        available_states = StateOptionsBuilder.for_light_groups(
            secondary_states, exclude_dark=True
        )

        # Build selector overrides for dynamic options
        selector_overrides = {
            LightGroupEntryOptions.LIGHTS.key: cv.multi_select(lights),
            LightGroupEntryOptions.STATES.key: cv.multi_select(available_states),
            LightGroupEntryOptions.ACT_ON.key: cv.multi_select(
                [e.value for e in LightGroupActOn]
            ),
        }

        # Use SchemaBuilder to auto-generate schema (UUID excluded automatically via internal=True)
        return SchemaBuilder.from_option_set(
            LightGroupEntryOptions,
            saved_config=current_values,
            selector_overrides=selector_overrides,
        )

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
