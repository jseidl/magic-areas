"""BLE trackers feature handler."""

from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN

from custom_components.magic_areas.const import (
    Features,
    MAGICAREAS_UNIQUEID_PREFIX,
)
from custom_components.magic_areas.const.ble_trackers import BleTrackerOptions
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
class BLETrackersFeature(FeatureHandler):
    """BLE trackers feature - auto-generated with entity filter override."""

    @property
    def feature_id(self) -> str:
        return Features.BLE_TRACKERS

    @property
    def feature_name(self) -> str:
        return "BLE Trackers"

    async def handle_step(self, step_id, user_input):
        """Handle configuration with selective override."""
        # Get current feature config
        feature_config = self.get_config()

        # Auto-generate base selectors
        selectors = SelectorBuilder.from_option_set(BleTrackerOptions)

        # Override: Filter sensor entities (exclude Magic Areas sensors)
        sensor_entities = [
            entity_id
            for entity_id in self.all_entities
            if (
                entity_id.split(".")[0] == SENSOR_DOMAIN
                and not entity_id.split(".")[1].startswith(MAGICAREAS_UNIQUEID_PREFIX)
            )
        ]

        selectors[BleTrackerOptions.ENTITIES.key] = (
            self.flow._build_selector_entity_simple(sensor_entities, multiple=True)
        )

        # Auto-generate schema with overrides
        builder = SchemaBuilder(feature_config)
        schema = builder.from_option_set(
            BleTrackerOptions, selector_overrides=selectors
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

        entities = config.get(
            BleTrackerOptions.ENTITIES.key,
            BleTrackerOptions.ENTITIES.default,
        )
        return f"{len(entities)} tracker(s)"
