"""Aggregates feature handler."""

from custom_components.magic_areas.config_flow.features import register_feature
from custom_components.magic_areas.config_flow.features.base import (
    FeatureHandler,
    StepResult,
)
from custom_components.magic_areas.config_flow.helpers import SchemaBuilder
from custom_components.magic_areas.const import Features
from custom_components.magic_areas.const.aggregates import AggregateOptions


@register_feature
class AggregatesFeature(FeatureHandler):
    """Aggregates feature - fully auto-generated."""

    @property
    def feature_id(self) -> str:
        """Return feature identifier."""
        return Features.AGGREGATION

    @property
    def feature_name(self) -> str:
        """Return feature display name."""
        return "Aggregates"

    async def handle_step(self, step_id, user_input):
        """Handle configuration with full auto-generation."""
        # Get current feature config
        feature_config = self.get_config()

        # Fully auto-generated - all device class lists and configs are in metadata!
        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(AggregateOptions)

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

        bs_count = len(
            config.get(
                AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key,
                AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.default,
            )
        )
        s_count = len(
            config.get(
                AggregateOptions.SENSOR_DEVICE_CLASSES.key,
                AggregateOptions.SENSOR_DEVICE_CLASSES.default,
            )
        )
        min_ent = config.get(
            AggregateOptions.MIN_ENTITIES.key,
            AggregateOptions.MIN_ENTITIES.default,
        )

        return f"{bs_count} binary, {s_count} sensors, min={min_ent}"
