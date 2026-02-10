"""Fan groups feature handler."""

from custom_components.magic_areas.const import AreaType, Features
from custom_components.magic_areas.const.fan_groups import FanGroupOptions
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


@register_feature
class FanGroupsFeature(FeatureHandler):
    """Fan groups feature - auto-generated with state selector override."""

    @property
    def feature_id(self) -> str:
        return Features.FAN_GROUPS

    @property
    def feature_name(self) -> str:
        return "Fan Groups"

    @property
    def is_available(self) -> bool:
        """Not available for meta areas."""
        return self.area.config.get("type") != AreaType.META

    async def handle_step(self, step_id, user_input):
        """Handle configuration with selective override."""
        # Get current feature config
        feature_config = self.get_config()

        # Auto-generate base selectors
        selectors = SelectorBuilder.from_option_set(FanGroupOptions)

        # Override: Dynamic state options (only occupied/extended for fans)
        available_states = StateOptionsBuilder.for_fan_groups()
        selectors[FanGroupOptions.REQUIRED_STATE.key] = (
            self.flow._build_selector_select(available_states)
        )

        # Auto-generate schema with overrides
        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(FanGroupOptions, selector_overrides=selectors)

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
