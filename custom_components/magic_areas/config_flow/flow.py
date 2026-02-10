"""Main config flow for Magic Areas."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.area_registry import async_get as areareg_async_get
from homeassistant.helpers.floor_registry import async_get as floorreg_async_get
from homeassistant.util import slugify

from custom_components.magic_areas.const import (
    AreaType,
    CONF_AREA_ID,
    CONF_ENABLED_FEATURES,
    CONF_TYPE,
    DATA_AREA_OBJECT,
    DOMAIN,
    FEATURE_LIST,
    FEATURE_LIST_GLOBAL,
    FEATURE_LIST_META,
    META_AREA_GLOBAL,
    MODULE_DATA,
    NON_CONFIGURABLE_FEATURES_META,
)
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.area_aware_media_player import (
    AreaAwareMediaPlayerOptions,
)
from custom_components.magic_areas.const.ble_trackers import BleTrackerOptions
from custom_components.magic_areas.const.climate_control import ClimateControlOptions
from custom_components.magic_areas.const.fan_groups import FanGroupOptions
from custom_components.magic_areas.const.health import HealthOptions
from custom_components.magic_areas.const.presence_hold import PresenceHoldOptions
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions
from custom_components.magic_areas.const.wasp_in_a_box import WaspInABoxOptions
from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.helpers.area import (
    basic_area_from_floor,
    basic_area_from_meta,
    basic_area_from_object,
)
from custom_components.magic_areas.config_flow.base import (
    ConfigBase,
    NullableEntitySelector,
)
from custom_components.magic_areas.config_flow.features import (
    get_available_features,
    get_feature_handler,
)
from custom_components.magic_areas.config_flow.helpers import (
    ConfigValidator,
    FlowEntityContext,
)

_LOGGER = logging.getLogger(__name__)

EMPTY_ENTRY = [""]


class ConfigFlow(config_entries.ConfigFlow, ConfigBase, domain=DOMAIN):
    """Handle a config flow for Magic Areas."""

    VERSION = 2
    MINOR_VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        reserved_names = []
        non_floor_meta_areas = ["global", "interior", "exterior"]

        # Load registries
        area_registry = areareg_async_get(self.hass)
        floor_registry = floorreg_async_get(self.hass)
        areas = [
            basic_area_from_object(area) for area in area_registry.async_list_areas()
        ]
        area_ids = [area.id for area in areas]

        # Load floors meta-areas
        floors = floor_registry.async_list_floors()

        for floor in floors:
            if floor.floor_id in area_ids:
                _LOGGER.warning(
                    "ConfigFlow: Area with reserved name '%s' prevents using %s Meta area.",
                    floor.floor_id,
                    floor.floor_id,
                )
                continue

            area = basic_area_from_floor(floor)
            reserved_names.append(area.id)
            areas.append(area)

        # Add standard meta areas
        for meta_area in non_floor_meta_areas:
            if meta_area in area_ids:
                _LOGGER.warning(
                    "ConfigFlow: Area with reserved name '%s' prevents using %s Meta area.",
                    meta_area,
                    meta_area,
                )
                continue

            area = basic_area_from_meta(meta_area)
            reserved_names.append(area.id)
            areas.append(area)

        if user_input is not None:
            # Look up area object by name
            area_object = None
            area_name = user_input[CONF_NAME]

            # Handle meta area name prefix
            if area_name.startswith("(Meta)"):
                area_name = " ".join(area_name.split(" ")[1:])

            for area in areas:
                if area.name == area_name:
                    area_object = area
                    break

            if not area_object:
                return self.async_abort(reason="invalid_area")

            await self.async_set_unique_id(area_object.id)
            self._abort_if_unique_id_configured()

            # Create entry with only area ID (name is stored in entry.title)
            config_entry = {CONF_AREA_ID: area_object.id}

            # Handle Meta area type
            if slugify(area_object.id) in reserved_names:
                _LOGGER.debug("ConfigFlow: Meta area %s found", area_object.id)
                config_entry[CONF_TYPE] = AreaType.META

            return self.async_create_entry(title=area_object.name, data=config_entry)

        # Filter out already-configured areas
        configured_areas = []
        ma_data = self.hass.data.get(MODULE_DATA, {})
        for config_data in ma_data.values():
            configured_areas.append(config_data[DATA_AREA_OBJECT].id)

        available_areas = [area for area in areas if area.id not in configured_areas]

        if not available_areas:
            return self.async_abort(reason="no_more_areas")

        # Sort: regular areas first, then meta areas
        available_area_names = sorted(
            [area.name for area in available_areas if area.id not in reserved_names]
        )
        available_area_names.extend(
            sorted(
                [
                    f"(Meta) {area.name}"
                    for area in available_areas
                    if area.id in reserved_names
                ]
            )
        )

        schema = vol.Schema({vol.Required(CONF_NAME): vol.In(available_area_names)})

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow, ConfigBase):
    """Handle options flow using feature handlers."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        super().__init__()
        self.data: dict[str, Any] = {}
        self.all_entities: list[str] = []
        self.area_entities: list[str] = []
        self.all_area_entities: list[str] = []
        self.all_lights: list[str] = []
        self.all_media_players: list[str] = []
        self.all_binary_entities: list[str] = []
        self.all_light_tracking_entities: list[str] = []
        self.area_options: dict = {}

        # Feature handler state
        self._feature_handlers: dict[str, Any] = {}
        self._current_feature: str | None = None
        self._current_feature_step: str | None = None

    def _get_feature_list(self) -> list:
        """Return list of available features for area type."""
        from custom_components.magic_areas.const import AreaConfigOptions

        feature_list = FEATURE_LIST
        area_type = self.area.config.get(AreaConfigOptions.TYPE)
        if area_type == AreaType.META:
            feature_list = FEATURE_LIST_META
        if self.area.id == META_AREA_GLOBAL.lower():
            feature_list = FEATURE_LIST_GLOBAL
        return feature_list

    def _get_configurable_features(self) -> list:
        """Return configurable features for area type using introspection."""
        # Map feature keys to their OptionSet classes
        feature_option_sets = {
            "aggregates": AggregateOptions,
            "health": HealthOptions,
            "presence_hold": PresenceHoldOptions,
            "ble_trackers": BleTrackerOptions,
            "wasp_in_a_box": WaspInABoxOptions,
            "area_aware_media_player": AreaAwareMediaPlayerOptions,
            "climate_control": ClimateControlOptions,
            "fan_groups": FanGroupOptions,
        }

        configurable = []
        for feature_key, option_set in feature_option_sets.items():
            # Check if feature has configuration options
            if option_set.has_configuration():
                # Check if available for this area type
                if self.area.is_meta() and feature_key in [
                    f.value for f in NON_CONFIGURABLE_FEATURES_META
                ]:
                    continue
                configurable.append(feature_key)

        return configurable

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(title="", data=dict(self.area_options))

    @staticmethod
    def resolve_groups(raw_list):
        """Resolve entities from groups."""
        resolved_list = []
        for item in raw_list:
            if isinstance(item, list):
                for item_child in item:
                    resolved_list.append(item_child)
                continue
            resolved_list.append(item)
        return list(dict.fromkeys(resolved_list))

    async def async_step_init(self, user_input=None):
        """Initialize the options flow."""
        self.data = self.hass.data[MODULE_DATA][self.config_entry.entry_id]
        self.area = self.data[DATA_AREA_OBJECT]

        _LOGGER.debug("OptionsFlow: Initializing for area %s", self.area.name)

        # Build entity context (replaces ~60 lines of entity filtering)
        entity_context = FlowEntityContext(self.hass, self.area, self.config_entry)

        # Populate instance variables for backward compatibility
        self.all_entities = entity_context.all_entities
        self.area_entities = entity_context.area_entities
        self.all_area_entities = entity_context.all_area_entities
        self.all_lights = entity_context.lights
        self.all_media_players = entity_context.media_players
        self.all_binary_entities = entity_context.binary_entities
        self.all_light_tracking_entities = entity_context.light_tracking_entities

        # Initialize area options - load directly without schema validation
        self.area_options = dict(self.config_entry.options)

        _LOGGER.debug(
            "%s: Loaded area options: %s", self.area.name, str(self.area_options)
        )

        # Load feature handlers
        self._feature_handlers = get_available_features(self)

        return await self.async_step_show_menu()

    async def async_step_show_menu(self, user_input=None):
        """Show main options menu."""
        menu_options = [
            "area_config",
            "presence_tracking",
            "secondary_states",
            "select_features",
        ]

        # Add configured features to menu
        enabled = self.area_options.get(CONF_ENABLED_FEATURES, {})
        configurable = self._get_configurable_features()

        for feature_id in sorted(enabled.keys()):
            if feature_id in configurable and feature_id in self._feature_handlers:
                handler = self._feature_handlers[feature_id]
                if handler.requires_configuration:
                    menu_options.append(f"feature_{feature_id}")

        menu_options.append("finish")

        return self.async_show_menu(step_id="show_menu", menu_options=menu_options)

    async def async_step_area_config(self, user_input=None):
        """Configure basic area settings."""
        from custom_components.magic_areas.const import AreaConfigOptions
        from custom_components.magic_areas.config_flow.helpers import (
            SelectorBuilder,
            SchemaBuilder,
        )

        # Auto-generate selectors from AreaConfigOptions
        selectors = SelectorBuilder.from_option_set(AreaConfigOptions)

        # Override selectors with dynamic entity lists
        selectors[AreaConfigOptions.INCLUDE_ENTITIES.key] = (
            self._build_selector_entity_simple(self.all_entities, multiple=True)
        )
        selectors[AreaConfigOptions.EXCLUDE_ENTITIES.key] = (
            self._build_selector_entity_simple(self.all_area_entities, multiple=True)
        )

        # Filter selectors for meta areas (they don't have TYPE or INCLUDE_ENTITIES)
        if self.area.is_meta():
            selectors.pop(AreaConfigOptions.TYPE.key, None)
            selectors.pop(AreaConfigOptions.INCLUDE_ENTITIES.key, None)
            selectors.pop(AreaConfigOptions.IGNORE_DIAGNOSTIC_ENTITIES.key, None)

        # Auto-generate schema with current values
        builder = SchemaBuilder(self.area_options)
        schema = builder.from_option_set(
            AreaConfigOptions, selector_overrides=selectors
        )

        if user_input is not None:
            validator = ConfigValidator("area_config")
            success, errors = await validator.validate(
                schema, user_input, lambda v: self.area_options.update(v)
            )
            if success:
                return await self.async_step_show_menu()

            return self.async_show_form(
                step_id="area_config",
                data_schema=schema,
                errors=errors,
            )

        return self.async_show_form(
            step_id="area_config",
            data_schema=schema,
        )

    async def async_step_presence_tracking(self, user_input=None):
        """Configure presence tracking settings."""
        from custom_components.magic_areas.const import PresenceTrackingOptions
        from custom_components.magic_areas.config_flow.helpers import (
            SelectorBuilder,
            SchemaBuilder,
        )

        # Auto-generate selectors from PresenceTrackingOptions
        selectors = SelectorBuilder.from_option_set(PresenceTrackingOptions)

        # Override selector with dynamic presence sensor list
        selectors[PresenceTrackingOptions.KEEP_ONLY_ENTITIES.key] = (
            self._build_selector_entity_simple(
                sorted(self.area.get_presence_sensors()), multiple=True
            )
        )

        # Filter selectors for meta areas (they only have CLEAR_TIMEOUT)
        if self.area.is_meta():
            selectors = {
                PresenceTrackingOptions.CLEAR_TIMEOUT.key: selectors.get(
                    PresenceTrackingOptions.CLEAR_TIMEOUT.key
                )
            }

        # Auto-generate schema with current values
        builder = SchemaBuilder(self.area_options)
        schema = builder.from_option_set(
            PresenceTrackingOptions, selector_overrides=selectors
        )

        if user_input is not None:
            validator = ConfigValidator("presence_tracking")
            success, errors = await validator.validate(
                schema, user_input, lambda v: self.area_options.update(v)
            )
            if success:
                return await self.async_step_show_menu()

            return self.async_show_form(
                step_id="presence_tracking",
                data_schema=schema,
                errors=errors,
            )

        return self.async_show_form(
            step_id="presence_tracking",
            data_schema=schema,
        )

    async def async_step_secondary_states(self, user_input=None):
        """Configure secondary states settings."""
        from custom_components.magic_areas.const import SecondaryStateOptions
        from custom_components.magic_areas.config_flow.helpers import (
            SelectorBuilder,
            SchemaBuilder,
        )

        # Auto-generate selectors from SecondaryStateOptions
        selectors = SelectorBuilder.from_option_set(SecondaryStateOptions)

        # Override selectors with dynamic entity lists
        selectors[SecondaryStateOptions.DARK_ENTITY.key] = (
            self._build_selector_entity_simple(self.all_light_tracking_entities)
        )
        selectors[SecondaryStateOptions.SLEEP_ENTITY.key] = (
            self._build_selector_entity_simple(self.all_binary_entities)
        )
        selectors[SecondaryStateOptions.ACCENT_ENTITY.key] = (
            self._build_selector_entity_simple(self.all_binary_entities)
        )

        # Filter selectors for meta areas (no DARK, SLEEP, ACCENT entities)
        if self.area.is_meta():
            selectors.pop(SecondaryStateOptions.DARK_ENTITY.key, None)
            selectors.pop(SecondaryStateOptions.SLEEP_ENTITY.key, None)
            selectors.pop(SecondaryStateOptions.ACCENT_ENTITY.key, None)

        # Get nested config (secondary_states is nested under this key)
        saved_options = self.area_options.get("secondary_states", {})

        # Auto-generate schema with current values
        builder = SchemaBuilder(saved_options)
        schema = builder.from_option_set(
            SecondaryStateOptions, selector_overrides=selectors
        )

        if user_input is not None:
            validator = ConfigValidator("secondary_states")

            async def on_save(validated):
                if "secondary_states" not in self.area_options:
                    self.area_options["secondary_states"] = {}
                self.area_options["secondary_states"].update(validated)

            success, errors = await validator.validate(schema, user_input, on_save)
            if success:
                return await self.async_step_show_menu()

            return self.async_show_form(
                step_id="secondary_states",
                data_schema=schema,
                errors=errors,
            )

        return self.async_show_form(
            step_id="secondary_states",
            data_schema=schema,
        )

    async def async_step_select_features(self, user_input=None):
        """Select features to enable."""
        feature_list = self._get_feature_list()

        if user_input is not None:
            selected_features = [
                feature for feature, is_selected in user_input.items() if is_selected
            ]

            _LOGGER.debug(
                "OptionsFlow: Selected features for area %s: %s",
                self.area.name,
                str(selected_features),
            )

            if CONF_ENABLED_FEATURES not in self.area_options:
                self.area_options[CONF_ENABLED_FEATURES] = {}

            for feature in feature_list:
                if feature in selected_features:
                    if feature not in self.area_options[CONF_ENABLED_FEATURES]:
                        self.area_options[CONF_ENABLED_FEATURES][feature] = {}
                else:
                    if feature in self.area_options[CONF_ENABLED_FEATURES]:
                        self.area_options[CONF_ENABLED_FEATURES].pop(feature, None)

            return await self.async_step_show_menu()

        return self.async_show_form(
            step_id="select_features",
            data_schema=self._build_options_schema(
                options=[(feature, False, bool) for feature in feature_list],
                saved_options={
                    feature: (
                        feature in self.area_options.get(CONF_ENABLED_FEATURES, {})
                    )
                    for feature in feature_list
                },
            ),
        )

    async def async_step_feature(self, user_input=None):
        """Generic feature configuration dispatcher."""
        # Determine which feature we're handling
        # The step_id will be like "feature_light_groups"
        if not self._current_feature:
            return await self.async_step_show_menu()

        handler = self._feature_handlers.get(self._current_feature)
        if not handler:
            return await self.async_step_show_menu()

        # Get the specific step for this feature
        step_id = self._current_feature_step or handler.get_initial_step()

        # Handle the step
        result = await handler.handle_step(step_id, user_input)

        if result.type == "create_entry":
            if result.save_data is not None:
                handler.save_config(result.save_data)
            handler.cleanup()
            self._current_feature = None
            self._current_feature_step = None
            return await self.async_step_show_menu()

        if result.type == "form":
            self._current_feature_step = result.step_id
            return self.async_show_form(
                step_id="feature",
                data_schema=result.data_schema,
                errors=result.errors,
                description_placeholders=result.description_placeholders,
            )

        if result.type == "menu":
            return self.async_show_menu(
                step_id="feature",
                menu_options=result.menu_options or [],
            )

        return await self.async_step_show_menu()

    # Individual feature step handlers - they all delegate to async_step_feature
    async def async_step_feature_light_groups(self, user_input=None):
        """Handle light groups feature config."""
        self._current_feature = "light_groups"
        return await self.async_step_feature(user_input)

    async def async_step_feature_climate_control(self, user_input=None):
        """Handle climate control feature config."""
        self._current_feature = "climate_control"
        return await self.async_step_feature(user_input)

    async def async_step_feature_aggregates(self, user_input=None):
        """Handle aggregates feature config."""
        self._current_feature = "aggregates"
        return await self.async_step_feature(user_input)

    async def async_step_feature_health(self, user_input=None):
        """Handle health feature config."""
        self._current_feature = "health"
        return await self.async_step_feature(user_input)

    async def async_step_feature_presence_hold(self, user_input=None):
        """Handle presence hold feature config."""
        self._current_feature = "presence_hold"
        return await self.async_step_feature(user_input)

    async def async_step_feature_ble_trackers(self, user_input=None):
        """Handle BLE trackers feature config."""
        self._current_feature = "ble_trackers"
        return await self.async_step_feature(user_input)

    async def async_step_feature_wasp_in_a_box(self, user_input=None):
        """Handle wasp in a box feature config."""
        self._current_feature = "wasp_in_a_box"
        return await self.async_step_feature(user_input)

    async def async_step_feature_fan_groups(self, user_input=None):
        """Handle fan groups feature config."""
        self._current_feature = "fan_groups"
        return await self.async_step_feature(user_input)

    async def async_step_feature_area_aware_media_player(self, user_input=None):
        """Handle area aware media player feature config."""
        self._current_feature = "area_aware_media_player"
        return await self.async_step_feature(user_input)

    async def async_step_finish(self, user_input=None):
        """Save options and exit."""
        _LOGGER.debug(
            "OptionsFlow: Saving config for area %s: %s",
            self.area.name,
            str(self.area_options),
        )
        return await self._update_options()
