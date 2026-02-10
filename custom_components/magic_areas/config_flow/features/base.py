"""Base feature handler for config flow."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import voluptuous as vol

from custom_components.magic_areas.const import CONF_ENABLED_FEATURES
from custom_components.magic_areas.config_flow.helpers import (
    ConfigValidator,
    SchemaBuilder,
)

if TYPE_CHECKING:
    from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler


@dataclass
class StepResult:
    """Result from a feature step handler."""

    type: str  # "form", "menu", "create_entry", "abort"
    step_id: Optional[str] = None  # Next step to call
    data_schema: Optional[vol.Schema] = None
    errors: Optional[Dict[str, str]] = None
    description_placeholders: Optional[Dict[str, str]] = None
    menu_options: Optional[List[str]] = None
    save_data: Optional[Dict[str, Any]] = None  # Data to save to config


class FeatureHandler(ABC):
    """Base class for feature configuration handlers."""

    def __init__(self, flow: "OptionsFlowHandler"):
        self.flow = flow
        self._state: Dict[str, Any] = {}
        self._validator = ConfigValidator(self.feature_id)

    @property
    @abstractmethod
    def feature_id(self) -> str:
        """Unique identifier for this feature."""
        pass

    @property
    @abstractmethod
    def feature_name(self) -> str:
        """Human-readable name for menus."""
        pass

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
    async def handle_step(self, step_id: str, user_input: Optional[dict]) -> StepResult:
        """Handle a configuration step. Must be implemented by subclasses."""
        pass

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
    def all_lights(self) -> List[str]:
        """Access all lights list."""
        return self.flow.all_lights

    @property
    def all_entities(self) -> List[str]:
        """Access all entities list."""
        return self.flow.all_entities

    @property
    def all_media_players(self) -> List[str]:
        """Access all media players list."""
        return self.flow.all_media_players

    @property
    def all_binary_entities(self) -> List[str]:
        """Access all binary entities list."""
        return self.flow.all_binary_entities

    def get_config(self) -> dict:
        """Get current feature config from area options."""
        return self.flow.area_options.get(CONF_ENABLED_FEATURES, {}).get(
            self.feature_id, {}
        )

    def save_config(self, config: dict):
        """Save feature config to area options."""
        if CONF_ENABLED_FEATURES not in self.flow.area_options:
            self.flow.area_options[CONF_ENABLED_FEATURES] = {}
        self.flow.area_options[CONF_ENABLED_FEATURES][self.feature_id] = config

    def build_schema(
        self,
        options: List[tuple],
        selectors: Optional[Dict[str, Any]] = None,
    ) -> vol.Schema:
        """Build schema using helper."""
        builder = SchemaBuilder(self.get_config())
        return builder.build_feature_schema(options, self.get_config(), selectors or {})

    async def validate_and_save(
        self,
        schema: vol.Schema,
        user_input: dict,
    ) -> tuple[bool, Optional[Dict[str, str]]]:
        """Validate and save if valid."""

        async def on_save(validated):
            self.save_config(validated)

        return await self._validator.validate(schema, user_input, on_save)
