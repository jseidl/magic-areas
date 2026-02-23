"""Base class for config domain handlers."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler


@dataclass
class DomainStepResult:
    """Result of handling a domain configuration step.

    Similar to FeatureHandler's StepResult but for config domains.
    """

    type: str  # "form", "menu", "create_entry"
    step_id: str | None = None
    data_schema: Any = None
    errors: dict[str, str] | None = None
    description_placeholders: dict[str, str] | None = None
    menu_options: list[str] | None = None
    save_data: dict | None = None


class DomainHandler:
    """Base class for config domain handlers.

    Domain handlers manage configuration for core config domains like:
    - User-defined states (USER_DEFINED_STATES)
    - Area config (AREA) - if extracted from flow.py
    - Presence tracking (PRESENCE) - if extracted from flow.py
    - Secondary states (SECONDARY_STATES) - if extracted from flow.py

    This is separate from FeatureHandler which manages optional features
    under the FEATURES config domain.
    """

    def __init__(self, flow: "OptionsFlowHandler"):
        """Initialize domain handler.

        Args:
            flow: The OptionsFlowHandler instance managing the config flow

        """
        self.flow = flow
        self.hass = flow.hass
        self.area = flow.area
        self.area_options = flow.area_options

    @property
    def domain_id(self) -> str:
        """Return the config domain identifier.

        Returns:
            Domain ID (e.g., "user_defined_states")

        """
        raise NotImplementedError

    @property
    def domain_name(self) -> str:
        """Return human-readable domain name for UI.

        Returns:
            Display name (e.g., "User-Defined States")

        """
        raise NotImplementedError

    @property
    def requires_multi_step(self) -> bool:
        """Return if domain needs multi-step flow.

        Simple domains (single form) return False.
        Complex domains (lists with add/edit/delete) return True.

        Returns:
            True if multi-step flow is needed, False otherwise

        """
        return False

    def get_initial_step(self) -> str:
        """Return the initial step ID for multi-step flows.

        For simple domains, this is ignored.
        For multi-step domains, this is the first step to display.

        Returns:
            Initial step ID (e.g., "main" for menu-based flows)

        """
        return "main"

    async def handle_step(
        self, step_id: str, user_input: dict | None
    ) -> DomainStepResult:
        """Handle a configuration step.

        Args:
            step_id: The step identifier
            user_input: User input from the form, or None for initial display

        Returns:
            DomainStepResult with next action (form, menu, or create_entry)

        """
        raise NotImplementedError

    def get_config(self) -> dict:
        """Get current configuration for this domain.

        Returns:
            Domain configuration dict

        """
        raise NotImplementedError

    def save_config(self, config: dict) -> None:
        """Save configuration for this domain.

        Args:
            config: Configuration dict to save

        """
        raise NotImplementedError

    def cleanup(self) -> None:
        """Clean up any temporary state.

        Called when exiting the domain configuration.
        """

    def get_summary(self, config: dict) -> str:
        """Generate a summary of the domain configuration.

        Used for display in menus or status indicators.

        Args:
            config: Domain configuration dict

        Returns:
            Human-readable summary string

        """
        return "Configured"
