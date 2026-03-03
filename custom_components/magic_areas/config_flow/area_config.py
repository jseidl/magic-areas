"""Area configuration domain handler."""

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
from custom_components.magic_areas.const import AreaConfigOptions, ConfigDomains
from custom_components.magic_areas.const.urls import (
    MagicAreasDocumentationUrls,
    UrlDescriptionPlaceholders,
)

_LOGGER = logging.getLogger(__name__)


class AreaConfigHandler(DomainHandler):
    """Handler for basic area configuration."""

    @property
    def domain_id(self) -> str:
        """Return domain identifier."""
        return "area"

    @property
    def domain_name(self) -> str:
        """Return domain display name."""
        return "Area Configuration"

    @property
    def requires_multi_step(self) -> bool:
        """Single-form configuration."""
        return False

    async def handle_step(
        self, step_id: str, user_input: dict | None
    ) -> DomainStepResult:
        """Handle area configuration step."""
        # Auto-generate selectors from AreaConfigOptions
        selectors = SelectorBuilder.from_option_set(AreaConfigOptions)

        # Override selectors with dynamic entity lists
        selectors[AreaConfigOptions.INCLUDE_ENTITIES.key] = (
            self.flow.build_selector_entity_simple(
                self.flow.all_entities, multiple=True
            )
        )
        selectors[AreaConfigOptions.EXCLUDE_ENTITIES.key] = (
            self.flow.build_selector_entity_simple(
                self.flow.all_area_entities, multiple=True
            )
        )

        # Filter selectors for meta areas (they don't have TYPE or INCLUDE_ENTITIES)
        exclude_keys: list[str] = []
        if self.area.is_meta():
            exclude_keys.append(AreaConfigOptions.TYPE.key)
            exclude_keys.append(AreaConfigOptions.INCLUDE_ENTITIES.key)
            exclude_keys.append(AreaConfigOptions.WINDOWLESS.key)
            exclude_keys.append(AreaConfigOptions.IGNORE_DIAGNOSTIC_ENTITIES.key)

        # Get current config (nested under ConfigDomains.AREA)
        current_config = self.get_config()

        # Auto-generate schema with current values
        builder = SchemaBuilder(current_config)
        schema = builder.from_option_set(
            AreaConfigOptions, selector_overrides=selectors, exclude_keys=exclude_keys
        )

        description_placeholders = {
            UrlDescriptionPlaceholders.META_AREAS: MagicAreasDocumentationUrls.META_AREAS,
        }

        if user_input is not None:
            validator = ConfigValidator("area_config")

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
        """Get current area configuration."""
        return self.area_options.get(ConfigDomains.AREA.value, {})

    def save_config(self, config: dict) -> None:
        """Save area configuration."""
        if ConfigDomains.AREA.value not in self.area_options:
            self.area_options[ConfigDomains.AREA.value] = {}
        self.area_options[ConfigDomains.AREA.value] = config

    def get_summary(self, config: dict) -> str:
        """Generate summary of area configuration."""
        if not config:
            return "Not configured"

        area_type = config.get(AreaConfigOptions.TYPE.key, "interior")
        windowless = config.get(AreaConfigOptions.WINDOWLESS.key, False)
        included = len(config.get(AreaConfigOptions.INCLUDE_ENTITIES.key, []))
        excluded = len(config.get(AreaConfigOptions.EXCLUDE_ENTITIES.key, []))

        parts = [f"Type: {area_type}"]
        if windowless:
            parts.append("windowless")
        if included:
            parts.append(f"+{included} entities")
        if excluded:
            parts.append(f"-{excluded} entities")

        return ", ".join(parts)
