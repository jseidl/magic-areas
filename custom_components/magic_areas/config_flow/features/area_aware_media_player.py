"""Area aware media player feature handler."""

from custom_components.magic_areas.const import Features
from custom_components.magic_areas.const.area_aware_media_player import (
    AreaAwareMediaPlayerOptions,
)
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
class AreaAwareMediaPlayerFeature(FeatureHandler):
    """Area aware media player feature - auto-generated with 2 overrides."""

    @property
    def feature_id(self) -> str:
        return Features.AREA_AWARE_MEDIA_PLAYER

    @property
    def feature_name(self) -> str:
        return "Area Aware Media Player"

    async def handle_step(self, step_id, user_input):
        """Handle configuration with 2 selective overrides."""
        # Get current feature config
        feature_config = self.get_config()

        # Auto-generate base selectors
        selectors = SelectorBuilder.from_option_set(AreaAwareMediaPlayerOptions)

        # Override 1: Filtered media player entities
        selectors[AreaAwareMediaPlayerOptions.NOTIFICATION_DEVICES.key] = (
            self.flow._build_selector_entity_simple(
                self.all_media_players, multiple=True
            )
        )

        # Override 2: Dynamic state options (based on configured secondary states)
        secondary_states = self.area_options.get("secondary_states", {})
        available_states = StateOptionsBuilder.for_area_aware_media_player(
            secondary_states
        )
        selectors[AreaAwareMediaPlayerOptions.NOTIFY_STATES.key] = (
            self.flow._build_selector_select(available_states, multiple=True)
        )

        # Auto-generate schema with overrides
        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(
            AreaAwareMediaPlayerOptions, selector_overrides=selectors
        )

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

        devices = config.get(
            AreaAwareMediaPlayerOptions.NOTIFICATION_DEVICES.key,
            AreaAwareMediaPlayerOptions.NOTIFICATION_DEVICES.default,
        )
        states = config.get(
            AreaAwareMediaPlayerOptions.NOTIFY_STATES.key,
            AreaAwareMediaPlayerOptions.NOTIFY_STATES.default,
        )

        return f"{len(devices)} device(s), {len(states)} state(s)"
