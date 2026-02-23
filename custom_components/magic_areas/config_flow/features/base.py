"""Base feature handler for config flow."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.magic_areas.config_flow.helpers import (
    ConfigValidator,
    SchemaBuilder,
)
from custom_components.magic_areas.const import ConfigDomains

if TYPE_CHECKING:
    from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler


@dataclass
class StepResult:
    """Result from a feature step handler."""

    type: str  # "form", "menu", "create_entry", "abort"
    step_id: str | None = None  # Next step to call
    data_schema: vol.Schema | None = None
    errors: dict[str, str] | None = None
    description_placeholders: dict[str, str] | None = None
    menu_options: list[str] | None = None
    save_data: dict[str, Any] | None = None  # Data to save to config


class FeatureHandler(ABC):
    """Base class for feature configuration handlers."""

    def __init__(self, flow: "OptionsFlowHandler"):
        """Initialize feature handler.

        Args:
            flow: The parent OptionsFlowHandler instance

        """
        self.flow = flow
        self._state: dict[str, Any] = {}
        self._validator = ConfigValidator(self.feature_id)

    @property
    @abstractmethod
    def feature_id(self) -> str:
        """Unique identifier for this feature."""

    @property
    @abstractmethod
    def feature_name(self) -> str:
        """Human-readable name for menus."""

    @property
    def is_available(self) -> bool:
        """Check if this feature is available for current area type."""
        return True

    @property
    def requires_configuration(self) -> bool:
        """Whether this feature needs configuration beyond enable/disable."""
        return True

    def get_initial_step(self) -> str:
        """Return the first step ID for this feature."""
        return "main"

    @abstractmethod
    async def handle_step(self, step_id: str, user_input: dict | None) -> StepResult:
        """Handle a configuration step. Must be implemented by subclasses."""

    def get_summary(self, config: dict) -> str:
        """Return a summary of current configuration for the menu."""
        return "Configured" if config else "Not configured"

    def cleanup(self):
        """Clean up temporary state when exiting feature config."""
        self._state.clear()

    # Helper property to access flow's commonly used attributes
    @property
    def hass(self):
        """Access Home Assistant instance."""
        return self.flow.hass

    @property
    def area_options(self) -> dict:
        """Access area options."""
        return self.flow.area_options

    @property
    def area(self):
        """Access MagicArea instance."""
        return self.flow.area

    @property
    def all_lights(self) -> list[str]:
        """Access all lights list."""
        return self.flow.all_lights

    @property
    def all_entities(self) -> list[str]:
        """Access all entities list."""
        return self.flow.all_entities

    @property
    def all_media_players(self) -> list[str]:
        """Access all media players list."""
        return self.flow.all_media_players

    @property
    def all_binary_entities(self) -> list[str]:
        """Access all binary entities list."""
        return self.flow.all_binary_entities

    def get_config(self) -> dict:
        """Get current feature config from area options."""
        return self.flow.area_options.get(ConfigDomains.FEATURES, {}).get(
            self.feature_id, {}
        )

    def save_config(self, config: dict):
        """Save feature config to area options."""
        if ConfigDomains.FEATURES not in self.flow.area_options:
            self.flow.area_options[ConfigDomains.FEATURES] = {}
        self.flow.area_options[ConfigDomains.FEATURES][self.feature_id] = config

    def build_schema(
        self,
        options: list[tuple],
        selectors: dict[str, Any] | None = None,
    ) -> vol.Schema:
        """Build schema using helper."""
        builder = SchemaBuilder(self.get_config())
        return builder.build_feature_schema(options, self.get_config(), selectors or {})

    async def validate_and_save(
        self,
        schema: vol.Schema,
        user_input: dict,
    ) -> tuple[bool, dict[str, str] | None]:
        """Validate and save if valid."""

        async def on_save(validated):
            self.save_config(validated)

        return await self._validator.validate(schema, user_input, on_save)
