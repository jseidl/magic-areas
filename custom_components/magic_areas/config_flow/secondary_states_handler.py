"""Secondary states domain handler."""

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
from custom_components.magic_areas.const import ConfigDomains
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions

_LOGGER = logging.getLogger(__name__)


class SecondaryStatesHandler(DomainHandler):
    """Handler for secondary states configuration."""

    @property
    def domain_id(self) -> str:
        """Return domain identifier."""
        return "secondary_states"

    @property
    def domain_name(self) -> str:
        """Return domain display name."""
        return "Secondary States"

    @property
    def requires_multi_step(self) -> bool:
        """Single-form configuration."""
        return False

    async def handle_step(
        self, step_id: str, user_input: dict | None
    ) -> DomainStepResult:
        """Handle secondary states configuration step."""
        # Auto-generate selectors from SecondaryStateOptions
        selectors = SelectorBuilder.from_option_set(SecondaryStateOptions)

        # Override selectors with dynamic entity lists
        selectors[SecondaryStateOptions.SLEEP_ENTITY.key] = (
            self.flow.build_selector_entity_simple(self.flow.all_binary_entities)
        )

        # Filter selectors for meta areas (no SLEEP entity)
        if self.area.is_meta():
            selectors.pop(SecondaryStateOptions.SLEEP_ENTITY.key, None)

        # Get current config (nested under ConfigDomains.SECONDARY_STATES)
        current_config = self.get_config()

        # Auto-generate schema with current values
        builder = SchemaBuilder(current_config)
        schema = builder.from_option_set(
            SecondaryStateOptions, selector_overrides=selectors
        )

        if user_input is not None:
            validator = ConfigValidator("secondary_states")

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
            )

        return DomainStepResult(
            type="form",
            step_id="main",
            data_schema=schema,
        )

    def get_config(self) -> dict:
        """Get current secondary states configuration."""
        return self.area_options.get(ConfigDomains.SECONDARY_STATES.value, {})

    def save_config(self, config: dict) -> None:
        """Save secondary states configuration."""
        if ConfigDomains.SECONDARY_STATES.value not in self.area_options:
            self.area_options[ConfigDomains.SECONDARY_STATES.value] = {}
        self.area_options[ConfigDomains.SECONDARY_STATES.value] = config

    def get_summary(self, config: dict) -> str:
        """Generate summary of secondary states configuration."""
        if not config:
            return "Not configured"

        sleep_entity = config.get(SecondaryStateOptions.SLEEP_ENTITY.key, "")
        extended_time = config.get(SecondaryStateOptions.EXTENDED_TIME.key, 5)
        calc_mode = config.get(SecondaryStateOptions.CALCULATION_MODE.key, "majority")

        parts = []
        if sleep_entity:
            parts.append("Sleep configured")
        parts.append(f"Extended: {extended_time}min")
        parts.append(f"Mode: {calc_mode}")

        return ", ".join(parts)
