"""Presence hold feature handler."""

from custom_components.magic_areas.const import Features
from custom_components.magic_areas.const.presence_hold import PresenceHoldOptions
from custom_components.magic_areas.config_flow.features import register_feature
from custom_components.magic_areas.config_flow.features.base import (
    FeatureHandler,
    StepResult,
)
from custom_components.magic_areas.config_flow.helpers import (
    SchemaBuilder,
    SelectorBuilder,
)


@register_feature
class PresenceHoldFeature(FeatureHandler):
    """Presence hold feature - fully auto-generated."""

    @property
    def feature_id(self) -> str:
        return Features.PRESENCE_HOLD

    @property
    def feature_name(self) -> str:
        return "Presence Hold"

    async def handle_step(self, step_id, user_input):
        """Handle configuration with full auto-generation."""
        # Get current feature config
        feature_config = self.get_config()

        # Fully auto-generated - no overrides needed!
        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(PresenceHoldOptions)

        if user_input is not None:
            self.save_config(user_input)
            return StepResult(type="create_entry")

        return StepResult(
            type="form",
            step_id=step_id,
            data_schema=schema,
        )

    def get_summary(self, config: dict) -> str:
        """Generate summary."""
        if not config:
            return "Not configured"

        timeout = config.get(
            PresenceHoldOptions.TIMEOUT.key,
            PresenceHoldOptions.TIMEOUT.default,
        )
        if timeout == 0:
            return "No timeout"
        return f"Timeout: {timeout} min"
