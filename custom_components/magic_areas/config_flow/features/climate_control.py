"""Climate control feature handler with 2-step configuration."""

import logging

from homeassistant.components.climate.const import ATTR_PRESET_MODES
from homeassistant.helpers.entity_registry import async_get as entityreg_async_get

from custom_components.magic_areas.config_flow.features import register_feature
from custom_components.magic_areas.config_flow.features.base import (
    FeatureHandler,
    StepResult,
)
from custom_components.magic_areas.config_flow.helpers import SchemaBuilder
from custom_components.magic_areas.const import EMPTY_ENTRY, Features
from custom_components.magic_areas.const.climate_control import ClimateControlOptions

_LOGGER = logging.getLogger(__name__)

_PRESET_KEYS = [
    ClimateControlOptions.PRESET_CLEAR.key,
    ClimateControlOptions.PRESET_OCCUPIED.key,
    ClimateControlOptions.PRESET_SLEEP.key,
    ClimateControlOptions.PRESET_EXTENDED.key,
]


@register_feature
class ClimateControlFeature(FeatureHandler):
    """2-step climate control configuration.

    Step 1: Select climate entity.
    Step 2: Select presets for each area state.
    """

    @property
    def feature_id(self) -> str:
        """Return feature identifier."""
        return Features.CLIMATE_CONTROL

    @property
    def feature_name(self) -> str:
        """Return feature display name."""
        return "Climate Control"

    def get_initial_step(self) -> str:
        """Return the first step ID."""
        return "select_entity"

    async def handle_step(self, step_id: str, user_input: dict | None) -> StepResult:
        """Route to appropriate step."""
        if step_id == "select_entity":
            return await self._step_select_entity(user_input)
        if step_id == "select_presets":
            return await self._step_select_presets(user_input)

        return await self._step_select_entity(user_input)

    async def _step_select_entity(self, user_input: dict | None) -> StepResult:
        """Step 1: Select the climate entity."""
        if user_input is not None:
            entity_id = user_input[ClimateControlOptions.ENTITY_ID.key]

            # Validate entity has preset support
            entity_registry = entityreg_async_get(self.hass)
            entity_object = entity_registry.async_get(entity_id)

            if not entity_object:
                return StepResult(
                    type="form",
                    step_id="select_entity",
                    data_schema=self._build_entity_schema(),
                    errors={ClimateControlOptions.ENTITY_ID.key: "invalid_entity"},
                )

            if (
                not entity_object.capabilities
                or ATTR_PRESET_MODES not in entity_object.capabilities
                or not entity_object.capabilities[ATTR_PRESET_MODES]
            ):
                return StepResult(
                    type="form",
                    step_id="select_entity",
                    data_schema=self._build_entity_schema(),
                    errors={ClimateControlOptions.ENTITY_ID.key: "no_preset_support"},
                )

            # Store entity and proceed to presets
            self._state["entity_id"] = entity_id
            self._state["preset_modes"] = entity_object.capabilities[ATTR_PRESET_MODES]

            # Save entity_id to config immediately
            config = self.get_config()
            config[ClimateControlOptions.ENTITY_ID.key] = entity_id
            self.save_config(config)

            return StepResult(type="form", step_id="select_presets")

        return StepResult(
            type="form",
            step_id="select_entity",
            data_schema=self._build_entity_schema(),
        )

    async def _step_select_presets(self, user_input: dict | None) -> StepResult:
        """Step 2: Select presets for each area state."""
        entity_id = self._state.get("entity_id")
        preset_modes = self._state.get("preset_modes", [])

        if not entity_id or not preset_modes:
            # Should not happen, go back to entity selection
            return StepResult(type="form", step_id="select_entity")

        if user_input is not None:
            # Build final config
            config = {
                ClimateControlOptions.ENTITY_ID.key: entity_id,
                ClimateControlOptions.PRESET_CLEAR.key: user_input.get(
                    ClimateControlOptions.PRESET_CLEAR.key, ""
                ),
                ClimateControlOptions.PRESET_OCCUPIED.key: user_input.get(
                    ClimateControlOptions.PRESET_OCCUPIED.key, ""
                ),
                ClimateControlOptions.PRESET_SLEEP.key: user_input.get(
                    ClimateControlOptions.PRESET_SLEEP.key, ""
                ),
                ClimateControlOptions.PRESET_EXTENDED.key: user_input.get(
                    ClimateControlOptions.PRESET_EXTENDED.key, ""
                ),
            }

            return StepResult(type="create_entry", save_data=config)

        # Build dynamic preset selector from actual entity capabilities
        preset_selector = self.flow.build_selector_select(
            options=EMPTY_ENTRY + preset_modes
        )

        # Use SchemaBuilder for pre-population + consistent schema generation
        builder = SchemaBuilder(self.get_config())
        schema = builder.from_option_set(
            ClimateControlOptions,
            selector_overrides={key: preset_selector for key in _PRESET_KEYS},
            exclude_keys=[ClimateControlOptions.ENTITY_ID.key],
        )

        return StepResult(
            type="form",
            step_id="select_presets",
            data_schema=schema,
            description_placeholders={
                "entity_id": entity_id,
                "preset_modes": ", ".join(preset_modes),
            },
        )

    def _build_entity_schema(self):
        """Build schema for entity selection, pre-populated with saved entity."""
        builder = SchemaBuilder(self.get_config())
        return builder.from_option_set(
            ClimateControlOptions,
            exclude_keys=_PRESET_KEYS,
        )

    def get_summary(self, config: dict) -> str:
        """Generate summary showing entity and configured presets."""
        if not config:
            return "Not configured"

        entity_id = config.get(ClimateControlOptions.ENTITY_ID.key)
        if not entity_id:
            return "Not configured"

        # Count configured presets
        presets = [
            config.get(ClimateControlOptions.PRESET_CLEAR.key),
            config.get(ClimateControlOptions.PRESET_OCCUPIED.key),
            config.get(ClimateControlOptions.PRESET_SLEEP.key),
            config.get(ClimateControlOptions.PRESET_EXTENDED.key),
        ]
        configured = sum(1 for p in presets if p)

        return f"{entity_id} ({configured}/4 presets)"
