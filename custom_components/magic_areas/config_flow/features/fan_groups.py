"""Fan groups feature handler."""

from custom_components.magic_areas.config_flow.features import register_feature
from custom_components.magic_areas.config_flow.features.base import (
    FeatureHandler,
    StepResult,
)
from custom_components.magic_areas.config_flow.helpers import (
    SchemaBuilder,
    SelectorBuilder,
    StateOptionsBuilder,
)
from custom_components.magic_areas.const import (
    AreaConfigOptions,
    AreaType,
    ConfigDomains,
    Features,
)
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.fan_groups import FanGroupOptions


@register_feature
class FanGroupsFeature(FeatureHandler):
    """Fan groups feature - auto-generated with state selector override."""

    @property
    def feature_id(self) -> str:
        """Return feature identifier."""
        return Features.FAN_GROUPS

    @property
    def feature_name(self) -> str:
        """Return feature display name."""
        return "Fan Groups"

    @property
    def is_available(self) -> bool:
        """Not available for meta areas."""
        return self.area.config.get(AreaConfigOptions.TYPE) != AreaType.META

    async def handle_step(self, step_id, user_input):
        """Handle configuration with selective override."""
        # Get current feature config
        feature_config = self.get_config()

        # Auto-generate base selectors
        selectors = SelectorBuilder.from_option_set(FanGroupOptions)

        # Override: Dynamic state options (only occupied/extended for fans)
        available_states = StateOptionsBuilder.for_fan_groups()
        selectors[FanGroupOptions.REQUIRED_STATE.key] = self.flow.build_selector_select(
            available_states
        )

        # Auto-generate schema with overrides
        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(FanGroupOptions, selector_overrides=selectors)

        if user_input is not None:
            errors = self._validate_aggregates_dependency(user_input)
            if errors:
                return StepResult(
                    type="form",
                    step_id=step_id,
                    data_schema=SchemaBuilder(user_input).from_option_set(
                        FanGroupOptions, selector_overrides=selectors
                    ),
                    errors=errors,
                )

            self.save_config(user_input)
            return StepResult(type="create_entry")

        return StepResult(
            type="form",
            step_id=step_id,
            data_schema=schema,
        )

    def _validate_aggregates_dependency(self, user_input: dict) -> dict[str, str]:
        """Check the tracked aggregate sensor will exist.

        Fan groups track the aggregate sensor of a device class, so the Aggregates
        feature must be enabled and must aggregate the tracked device class.
        """
        tracked_key = FanGroupOptions.TRACKED_DEVICE_CLASS.key
        tracked_device_class = user_input.get(
            tracked_key, FanGroupOptions.TRACKED_DEVICE_CLASS.default
        )

        enabled_features = self.area_options.get(ConfigDomains.FEATURES, {})
        if Features.AGGREGATION.value not in enabled_features:
            return {tracked_key: "aggregates_required"}

        aggregated_device_classes = AggregateOptions.SENSOR_DEVICE_CLASSES.get_from(
            AggregateOptions.get_feature_config(self.area_options)
        )
        if tracked_device_class not in aggregated_device_classes:
            return {tracked_key: "tracked_device_class_not_aggregated"}

        return {}

    def get_summary(self, config: dict) -> str:
        """Generate summary."""
        if not config:
            return "Not configured"

        state = config.get(
            FanGroupOptions.REQUIRED_STATE.key,
            FanGroupOptions.REQUIRED_STATE.default,
        )
        device_class = config.get(
            FanGroupOptions.TRACKED_DEVICE_CLASS.key,
            FanGroupOptions.TRACKED_DEVICE_CLASS.default,
        )
        setpoint = config.get(
            FanGroupOptions.SETPOINT.key,
            FanGroupOptions.SETPOINT.default,
        )

        return f"State: {state}, {device_class} > {setpoint}"
