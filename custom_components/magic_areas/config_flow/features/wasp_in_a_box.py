"""Wasp in a box feature handler."""

from custom_components.magic_areas.config_flow.features import register_feature
from custom_components.magic_areas.config_flow.features.base import (
    FeatureHandler,
    StepResult,
)
from custom_components.magic_areas.config_flow.helpers import SchemaBuilder
from custom_components.magic_areas.const import Features
from custom_components.magic_areas.const.wasp_in_a_box import WaspInABoxOptions


@register_feature
class WaspInABoxFeature(FeatureHandler):
    """Wasp in a box feature - fully auto-generated."""

    @property
    def feature_id(self) -> str:
        """Return feature identifier."""
        return Features.WASP_IN_A_BOX

    @property
    def feature_name(self) -> str:
        """Return feature display name."""
        return "Wasp in a Box"

    async def handle_step(self, step_id, user_input):
        """Handle configuration with full auto-generation."""
        # Get current feature config
        feature_config = self.get_config()

        # Fully auto-generated - all metadata is in WaspInABoxOptions!
        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(WaspInABoxOptions)

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

        delay = config.get(
            WaspInABoxOptions.DELAY.key,
            WaspInABoxOptions.DELAY.default,
        )
        timeout = config.get(
            WaspInABoxOptions.WASP_TIMEOUT.key,
            WaspInABoxOptions.WASP_TIMEOUT.default,
        )
        classes = config.get(
            WaspInABoxOptions.WASP_DEVICE_CLASSES.key,
            WaspInABoxOptions.WASP_DEVICE_CLASSES.default,
        )

        parts = [f"delay: {delay}s"]
        if timeout > 0:
            parts.append(f"timeout: {timeout}min")
        parts.append(f"{len(classes)} classes")

        return ", ".join(parts)
