"""Main config flow for Magic Areas."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.area_registry import async_get as areareg_async_get
from homeassistant.helpers.floor_registry import async_get as floorreg_async_get
from homeassistant.util import slugify

from custom_components.magic_areas.config_flow.area_config import AreaConfigHandler
from custom_components.magic_areas.config_flow.base import ConfigBase
from custom_components.magic_areas.config_flow.features import (
    get_available_features,
    get_configurable_features,
)
from custom_components.magic_areas.config_flow.helpers import FlowEntityContext
from custom_components.magic_areas.config_flow.presence_tracking import (
    PresenceTrackingHandler,
)
from custom_components.magic_areas.config_flow.secondary_states import (
    SecondaryStatesHandler,
)
from custom_components.magic_areas.config_flow.user_defined_states import (
    UserDefinedStatesHandler,
)
from custom_components.magic_areas.const import (
    CONF_AREA_ID,
    DOMAIN,
    FEATURE_LIST,
    FEATURE_LIST_GLOBAL,
    FEATURE_LIST_META,
    META_AREA_GLOBAL,
    AreaConfigOptions,
    AreaType,
    ConfigDomains,
    MagicConfigEntryVersion,
)
from custom_components.magic_areas.helpers.area import (
    basic_area_from_floor,
    basic_area_from_meta,
    basic_area_from_object,
)

_LOGGER = logging.getLogger(__name__)

EMPTY_ENTRY = [""]


class ConfigFlow(config_entries.ConfigFlow, ConfigBase, domain=DOMAIN):
    """Handle a config flow for Magic Areas."""

    VERSION = MagicConfigEntryVersion.MAJOR
    MINOR_VERSION = MagicConfigEntryVersion.MINOR

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
            # Look up area object by ID (from dropdown selection)
            area_id = user_input[CONF_AREA_ID]
            area_object = next((a for a in areas if a.id == area_id), None)

            if not area_object:
                return self.async_abort(reason="invalid_area")

            await self.async_set_unique_id(area_object.id)
            self._abort_if_unique_id_configured()

            # Create entry with only area ID (name is stored in entry.title)
            config_entry = {CONF_AREA_ID: area_object.id}

            # Handle Meta area type
            if slugify(area_object.id) in reserved_names:
                _LOGGER.debug("ConfigFlow: Meta area %s found", area_object.id)
                config_entry.update(
                    AreaConfigOptions.to_config(
                        {
                            AreaConfigOptions.TYPE.key: AreaType.META,
                        }
                    )
                )

            return self.async_create_entry(title=area_object.name, data=config_entry)

        # Filter out already-configured areas
        configured_areas = [
            entry.runtime_data.id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if hasattr(entry, "runtime_data") and entry.runtime_data is not None
        ]

        available_areas = [area for area in areas if area.id not in configured_areas]

        if not available_areas:
            return self.async_abort(reason="no_more_areas")

        # Build dropdown: {area_id: display_name}
        # Regular areas show name, meta areas show "(Meta) name"
        area_choices = {}
        for area in sorted(available_areas, key=lambda a: a.name):
            if area.id in reserved_names:
                area_choices[area.id] = f"(Meta) {area.name}"
            else:
                area_choices[area.id] = area.name

        schema = vol.Schema({vol.Required(CONF_AREA_ID): vol.In(area_choices)})

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
        self.area: Any = None  # MagicArea instance, set in async_step_init
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
        feature_list = FEATURE_LIST
        area_type = self.area.config.get(AreaConfigOptions.TYPE)
        if area_type == AreaType.META:
            feature_list = FEATURE_LIST_META
        if self.area.id == META_AREA_GLOBAL.lower():
            feature_list = FEATURE_LIST_GLOBAL
        return feature_list

    def _get_configurable_features(self) -> list:
        """Return configurable features for area type using introspection."""
        return get_configurable_features(self)

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
        self.area = self.config_entry.runtime_data

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
            "user_defined_states",
            "select_features",
        ]

        # Add configured features to menu
        enabled = self.area_options.get(ConfigDomains.FEATURES, {})
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
        handler = AreaConfigHandler(self)
        result = await handler.handle_step("main", user_input)

        if result.type == "create_entry":
            return await self.async_step_show_menu()

        return self.async_show_form(
            step_id="area_config",
            data_schema=result.data_schema,
            errors=result.errors,
            description_placeholders=result.description_placeholders,
        )

    async def async_step_presence_tracking(self, user_input=None):
        """Configure presence tracking settings."""
        handler = PresenceTrackingHandler(self)
        result = await handler.handle_step("main", user_input)

        if result.type == "create_entry":
            return await self.async_step_show_menu()

        return self.async_show_form(
            step_id="presence_tracking",
            data_schema=result.data_schema,
            errors=result.errors,
            description_placeholders=result.description_placeholders,
        )

    async def async_step_secondary_states(self, user_input=None):
        """Configure secondary states settings."""
        handler = SecondaryStatesHandler(self)
        result = await handler.handle_step("main", user_input)

        if result.type == "create_entry":
            return await self.async_step_show_menu()

        return self.async_show_form(
            step_id="secondary_states",
            data_schema=result.data_schema,
            errors=result.errors,
            description_placeholders=result.description_placeholders,
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

            if ConfigDomains.FEATURES not in self.area_options:
                self.area_options[ConfigDomains.FEATURES] = {}

            for feature in feature_list:
                if feature in selected_features:
                    if feature.value not in self.area_options[ConfigDomains.FEATURES]:
                        self.area_options[ConfigDomains.FEATURES][feature.value] = {}
                else:
                    if feature.value in self.area_options[ConfigDomains.FEATURES]:
                        self.area_options[ConfigDomains.FEATURES].pop(
                            feature.value, None
                        )

            return await self.async_step_show_menu()

        return self.async_show_form(
            step_id="select_features",
            data_schema=self.build_options_schema(
                options=[(feature.value, False, bool) for feature in feature_list],
                saved_options={
                    feature.value: (
                        feature in self.area_options.get(ConfigDomains.FEATURES, {})
                    )
                    for feature in feature_list
                },
            ),
        )

    async def async_step_feature(self, user_input=None):
        """Dispatch feature configuration to appropriate handler."""
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
            # Check if we're transitioning to a new step
            if result.step_id != step_id:
                # Step transition - recursively call handler with new step and user_input=None
                _LOGGER.debug(
                    "Feature %s: Step transition from '%s' to '%s'",
                    self._current_feature,
                    step_id,
                    result.step_id,
                )
                self._current_feature_step = result.step_id
                return await self.async_step_feature(user_input=None)

            # Same step - show form with schema
            self._current_feature_step = result.step_id

            # Construct proper step_id for Home Assistant to route correctly
            # and for translation keys to match (e.g., feature_light_groups_add_group)
            if result.step_id == handler.get_initial_step():
                form_step_id = f"feature_{self._current_feature}"
            else:
                form_step_id = f"feature_{self._current_feature}_{result.step_id}"

            _LOGGER.debug(
                "Feature %s: Showing form step '%s' with schema having %d fields: %s",
                self._current_feature,
                form_step_id,
                (
                    len(result.data_schema.schema)
                    if result.data_schema and hasattr(result.data_schema, "schema")
                    else 0
                ),
                (
                    list(result.data_schema.schema.keys())
                    if result.data_schema and hasattr(result.data_schema, "schema")
                    else "N/A"
                ),
            )

            return self.async_show_form(
                step_id=form_step_id,
                data_schema=result.data_schema,
                errors=result.errors,
                description_placeholders=result.description_placeholders,
            )

        if result.type == "menu":
            # Construct feature-specific step_id for proper translation lookup
            if result.step_id == handler.get_initial_step():
                menu_step_id = f"feature_{self._current_feature}"
            else:
                menu_step_id = f"feature_{self._current_feature}_{result.step_id}"

            return self.async_show_menu(
                step_id=menu_step_id,
                menu_options=result.menu_options or [],
                description_placeholders=result.description_placeholders,
            )

        return await self.async_step_show_menu()

    # Individual feature step handlers - they all delegate to async_step_feature
    async def async_step_feature_light_groups(self, user_input=None):
        """Handle light groups feature config."""
        _LOGGER.warning("LG MAIN")
        self._current_feature = "light_groups"
        return await self.async_step_feature(user_input)

    async def async_step_feature_light_groups_add_group(self, user_input=None):
        """Handle light groups add group step - routes to generic handler."""
        _LOGGER.warning(
            "SHOWING LG ADD FORM STEP async_step_feature_light_groups_add_group"
        )
        self._current_feature = "light_groups"
        self._current_feature_step = "add_group"
        return await self.async_step_feature(user_input)

    async def async_step_feature_light_groups_select_group(self, user_input=None):
        """Handle light groups select group step - routes to generic handler."""
        self._current_feature = "light_groups"
        self._current_feature_step = "select_group"
        return await self.async_step_feature(user_input)

    async def async_step_feature_light_groups_edit_group(self, user_input=None):
        """Handle light groups edit group step - routes to generic handler."""
        self._current_feature = "light_groups"
        self._current_feature_step = "edit_group"
        return await self.async_step_feature(user_input)

    async def async_step_feature_light_groups_delete_group(self, user_input=None):
        """Handle light groups delete group - routes to generic handler."""
        self._current_feature = "light_groups"
        self._current_feature_step = "delete_group"
        return await self.async_step_feature(user_input)

    async def async_step_feature_climate_control(self, user_input=None):
        """Handle climate control feature config."""
        self._current_feature = "climate_control"
        return await self.async_step_feature(user_input)

    async def async_step_feature_climate_control_select_presets(self, user_input=None):
        """Handle climate control preset selection - routes to generic handler."""
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

    # User-defined states domain handlers
    async def async_step_user_defined_states(self, user_input=None):
        """Handle user-defined states configuration."""
        handler = UserDefinedStatesHandler(self)
        result = await handler.handle_step("main", user_input)

        if result.type == "create_entry":
            return await self.async_step_show_menu()

        if result.type == "form":
            return self.async_show_form(
                step_id=f"user_defined_states_{result.step_id}",
                data_schema=result.data_schema,
                errors=result.errors,
                description_placeholders=result.description_placeholders,
            )

        if result.type == "menu":
            return self.async_show_menu(
                step_id="user_defined_states",
                menu_options=result.menu_options or [],
                description_placeholders=result.description_placeholders,
            )

        return await self.async_step_show_menu()

    async def async_step_user_defined_states_add_state(self, user_input=None):
        """Handle adding a user-defined state."""
        handler = UserDefinedStatesHandler(self)
        result = await handler.handle_step("add_state", user_input)

        if result.type == "create_entry":
            return await self.async_step_show_menu()

        if result.type == "form":
            return self.async_show_form(
                step_id="user_defined_states_add_state",
                data_schema=result.data_schema,
                errors=result.errors,
            )

        return await self.async_step_user_defined_states(None)

    async def async_step_user_defined_states_select_state(self, user_input=None):
        """Handle selecting a state to edit."""
        handler = UserDefinedStatesHandler(self)
        result = await handler.handle_step("select_state", user_input)

        if result.type == "create_entry":
            return await self.async_step_show_menu()

        if result.type == "form":
            if result.step_id == "edit_state":
                # Transition to edit step
                return await self.async_step_user_defined_states_edit_state(None)

            return self.async_show_form(
                step_id="user_defined_states_select_state",
                data_schema=result.data_schema,
                errors=result.errors,
            )

        return await self.async_step_user_defined_states(None)

    async def async_step_user_defined_states_edit_state(self, user_input=None):
        """Handle editing a user-defined state."""
        handler = UserDefinedStatesHandler(self)
        result = await handler.handle_step("edit_state", user_input)

        if result.type == "create_entry":
            return await self.async_step_show_menu()

        if result.type == "form":
            return self.async_show_form(
                step_id="user_defined_states_edit_state",
                data_schema=result.data_schema,
                errors=result.errors,
            )

        return await self.async_step_user_defined_states(None)

    async def async_step_user_defined_states_delete_state(self, user_input=None):
        """Handle deleting a user-defined state."""
        handler = UserDefinedStatesHandler(self)
        result = await handler.handle_step("delete_state", user_input)

        if result.type == "create_entry":
            return await self.async_step_show_menu()

        if result.type == "form":
            return self.async_show_form(
                step_id="user_defined_states_delete_state",
                data_schema=result.data_schema,
                errors=result.errors,
            )

        return await self.async_step_user_defined_states(None)

    async def async_step_finish(self, user_input=None):
        """Save options and exit."""
        _LOGGER.debug(
            "OptionsFlow: Saving config for area %s: %s",
            self.area.name,
            str(self.area_options),
        )
        # return await self._update_options()
        return self.async_create_entry(title="", data=dict(self.area_options))
