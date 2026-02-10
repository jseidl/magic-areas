"""Health sensor feature handler."""

from custom_components.magic_areas.const import Features
from custom_components.magic_areas.const.health import HealthOptions
from custom_components.magic_areas.config_flow.features import register_feature
from custom_components.magic_areas.config_flow.features.base import (
    FeatureHandler,
    StepResult,
)
from custom_components.magic_areas.config_flow.helpers import SchemaBuilder


@register_feature
class HealthFeature(FeatureHandler):
    """Health sensor feature - fully auto-generated."""

    @property
    def feature_id(self) -> str:
        return Features.HEALTH

    @property
    def feature_name(self) -> str:
        return "Health Sensor"

    async def handle_step(self, step_id, user_input):
        """Handle configuration with full auto-generation."""
        # Get current feature config
        feature_config = self.get_config()

        # Fully auto-generated - device class list is in metadata!
        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(HealthOptions)

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

        classes = config.get(
            HealthOptions.SENSOR_DEVICE_CLASSES.key,
            HealthOptions.SENSOR_DEVICE_CLASSES.default,
        )
        return f"{len(classes)} sensor classes"
