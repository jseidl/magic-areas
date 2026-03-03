"""Presence tracking domain handler."""

import logging

from custom_components.magic_areas.config_flow.domain_handlers import (
    DomainHandler,
    DomainStepResult,
)
from custom_components.magic_areas.config_flow.helpers import (
    ConfigValidator,
    SchemaBuilder,
    SelectorBuilder,
)
from custom_components.magic_areas.const import ConfigDomains, PresenceTrackingOptions
from custom_components.magic_areas.const.urls import (
    MagicAreasDocumentationUrls,
    UrlDescriptionPlaceholders,
)

_LOGGER = logging.getLogger(__name__)


class PresenceTrackingHandler(DomainHandler):
    """Handler for presence tracking configuration."""

    @property
    def domain_id(self) -> str:
        """Return domain identifier."""
        return "presence_tracking"

    @property
    def domain_name(self) -> str:
        """Return domain display name."""
        return "Presence Tracking"

    @property
    def requires_multi_step(self) -> bool:
        """Single-form configuration."""
        return False

    async def handle_step(
        self, step_id: str, user_input: dict | None
    ) -> DomainStepResult:
        """Handle presence tracking configuration step."""
        # Auto-generate selectors from PresenceTrackingOptions
        selectors = SelectorBuilder.from_option_set(PresenceTrackingOptions)

        # Override selector with dynamic presence sensor list
        selectors[PresenceTrackingOptions.KEEP_ONLY_ENTITIES.key] = (
            self.flow.build_selector_entity_simple(
                sorted(self.area.get_presence_sensors()), multiple=True
            )
        )

        # Filter selectors for meta areas (they only have CLEAR_TIMEOUT)
        exclude_keys: list[str] = []
        if self.area.is_meta():
            exclude_keys.append(PresenceTrackingOptions.DEVICE_PLATFORMS.key)
            exclude_keys.append(PresenceTrackingOptions.SENSOR_DEVICE_CLASS.key)
            exclude_keys.append(PresenceTrackingOptions.KEEP_ONLY_ENTITIES.key)

        # Get current config (nested under ConfigDomains.PRESENCE)
        current_config = self.get_config()

        # Auto-generate schema with current values
        builder = SchemaBuilder(current_config)
        schema = builder.from_option_set(
            PresenceTrackingOptions,
            selector_overrides=selectors,
            exclude_keys=exclude_keys,
        )

        description_placeholders = {
            UrlDescriptionPlaceholders.PRESENCE_SENSING: MagicAreasDocumentationUrls.PRESENCE_SENSING,
        }

        if user_input is not None:
            validator = ConfigValidator("presence_tracking")

            async def on_save(validated):
                self.save_config(validated)

            success, errors = await validator.validate(schema, user_input, on_save)
            if success:
                return DomainStepResult(type="create_entry")

            return DomainStepResult(
                type="form",
                step_id="main",
                data_schema=schema,
                errors=errors,
                description_placeholders=description_placeholders,
            )

        return DomainStepResult(
            type="form",
            step_id="main",
            data_schema=schema,
            description_placeholders=description_placeholders,
        )

    def get_config(self) -> dict:
        """Get current presence tracking configuration."""
        return self.area_options.get(ConfigDomains.PRESENCE.value, {})

    def save_config(self, config: dict) -> None:
        """Save presence tracking configuration."""
        if ConfigDomains.PRESENCE.value not in self.area_options:
            self.area_options[ConfigDomains.PRESENCE.value] = {}
        self.area_options[ConfigDomains.PRESENCE.value] = config

    def get_summary(self, config: dict) -> str:
        """Generate summary of presence tracking configuration."""
        if not config:
            return "Not configured"

        timeout = config.get(PresenceTrackingOptions.CLEAR_TIMEOUT.key, 1)
        platforms = config.get(PresenceTrackingOptions.DEVICE_PLATFORMS.key, [])
        keep_only = config.get(PresenceTrackingOptions.KEEP_ONLY_ENTITIES.key, [])

        parts = [f"Timeout: {timeout}min"]
        if platforms:
            parts.append(f"{len(platforms)} platform(s)")
        if keep_only:
            parts.append(f"{len(keep_only)} entity filter(s)")

        return ", ".join(parts)
