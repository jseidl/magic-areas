"""Helper functions for config flow."""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import voluptuous as vol
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

if TYPE_CHECKING:
    from custom_components.magic_areas.const import ConfigOption
    from custom_components.magic_areas.base.magic import MagicArea

_LOGGER = logging.getLogger(__name__)


class FlowEntityContext:
    """Encapsulates all entity lists needed for config flow."""

    def __init__(
        self,
        hass: HomeAssistant,
        area: "MagicArea",
        config_entry: config_entries.ConfigEntry,
    ):
        """Initialize entity context for the flow."""
        self.hass = hass
        self.area = area
        self.config_entry = config_entry

        # Build all entity lists on initialization
        self._all_entities = self._build_all_entities()
        self._area_entities = self._build_area_entities()
        self._all_binary_entities = self._build_binary_entities()
        self._lights = self._build_lights()
        self._media_players = self._build_media_players()
        self._light_tracking_entities = self._build_light_tracking_entities()

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

    @property
    def all_entities(self) -> list[str]:
        """All entities from allowed domains."""
        return self._all_entities

    @property
    def area_entities(self) -> list[str]:
        """Entities in this area."""
        return self._area_entities

    @property
    def all_area_entities(self) -> list[str]:
        """Area entities + excluded entities."""
        from custom_components.magic_areas.const import CONF_EXCLUDE_ENTITIES

        return sorted(
            self.area_entities
            + self.config_entry.options.get(CONF_EXCLUDE_ENTITIES, [])
        )

    @property
    def lights(self) -> list[str]:
        """Light entities in this area."""
        return self._lights

    @property
    def media_players(self) -> list[str]:
        """Media player entities in this area."""
        return self._media_players

    @property
    def binary_entities(self) -> list[str]:
        """All binary sensor entities."""
        return self._all_binary_entities

    @property
    def light_tracking_entities(self) -> list[str]:
        """Binary sensors for light tracking."""
        return self._light_tracking_entities

    def _build_all_entities(self) -> list[str]:
        """Build list of all relevant entities."""
        from custom_components.magic_areas.const import CONFIG_FLOW_ENTITY_FILTER_EXT

        return sorted(
            self.resolve_groups(
                entity_id
                for entity_id in self.hass.states.async_entity_ids()
                if entity_id.split(".")[0] in CONFIG_FLOW_ENTITY_FILTER_EXT
            )
        )

    def _build_area_entities(self) -> list[str]:
        """Build list of entities in this area."""
        from custom_components.magic_areas.const import CONFIG_FLOW_ENTITY_FILTER_EXT

        filtered_area_entities = []
        for domain in CONFIG_FLOW_ENTITY_FILTER_EXT:
            filtered_area_entities.extend(
                [
                    entity["entity_id"]
                    for entity in self.area.entities.get(domain, [])
                    if entity["entity_id"] in self._all_entities
                ]
            )
        return sorted(self.resolve_groups(filtered_area_entities))

    def _build_binary_entities(self) -> list[str]:
        """Build list of binary sensor entities."""
        from custom_components.magic_areas.const import CONFIG_FLOW_ENTITY_FILTER_BOOL

        return sorted(
            self.resolve_groups(
                entity_id
                for entity_id in self._all_entities
                if entity_id.split(".")[0] in CONFIG_FLOW_ENTITY_FILTER_BOOL
            )
        )

    def _build_lights(self) -> list[str]:
        """Build list of light entities in this area."""
        return sorted(
            self.resolve_groups(
                entity["entity_id"]
                for entity in self.area.entities.get(LIGHT_DOMAIN, [])
                if entity["entity_id"] in self._all_entities
            )
        )

    def _build_media_players(self) -> list[str]:
        """Build list of media player entities in this area."""
        return sorted(
            self.resolve_groups(
                entity["entity_id"]
                for entity in self.area.entities.get(MEDIA_PLAYER_DOMAIN, [])
                if entity["entity_id"] in self._all_entities
            )
        )

    def _build_light_tracking_entities(self) -> list[str]:
        """Build list of entities for light tracking (binary sensors with LIGHT device class)."""
        from custom_components.magic_areas.const import (
            ADDITIONAL_LIGHT_TRACKING_ENTITIES,
        )

        eligible_light_tracking = []
        for entity_id in self._all_entities:
            if entity_id.startswith("binary_sensor."):
                state = self.hass.states.get(entity_id)
                if (
                    state
                    and state.attributes.get(ATTR_DEVICE_CLASS)
                    == BinarySensorDeviceClass.LIGHT
                ):
                    eligible_light_tracking.append(entity_id)
        eligible_light_tracking.extend(ADDITIONAL_LIGHT_TRACKING_ENTITIES)
        return sorted(self.resolve_groups(eligible_light_tracking))


class ConfigValidator:
    """Handles validation with consistent error handling."""

    def __init__(self, flow_name: str):
        self.flow_name = flow_name

    async def validate(
        self,
        schema: vol.Schema,
        user_input: dict,
        on_success: Callable[[dict], Any],
        error_prefix: str = "",
    ) -> tuple[bool, Optional[Dict[str, str]]]:
        """
        Validate user input against schema.

        Returns: (success, errors_dict)
        If success is True, on_success was called and returned value can be used.
        """
        try:
            validated = schema(user_input)
            await on_success(validated)
            return True, None
        except vol.MultipleInvalid as validation:
            errors = {
                error_prefix + str(error.path[0]): str(error.msg)
                for error in validation.errors
            }
            _LOGGER.debug(
                "ConfigFlow (%s): Validation errors: %s", self.flow_name, errors
            )
            return False, errors
        except Exception as exc:
            _LOGGER.warning(
                "ConfigFlow (%s): Unexpected error: %s", self.flow_name, exc
            )
            return False, {"base": "unknown_error"}


class EntityListBuilder:
    """Builds filtered entity lists."""

    def __init__(self, hass, all_entities: List[str]):
        self.hass = hass
        self.all_entities = all_entities

    def by_domain(self, domains: List[str]) -> List[str]:
        """Filter entities by domain(s)."""
        return [e for e in self.all_entities if e.split(".")[0] in domains]

    def by_device_class(self, domain: str, device_class: str) -> List[str]:
        """Filter entities by domain and device class."""
        result = []
        for entity_id in self.all_entities:
            if not entity_id.startswith(f"{domain}."):
                continue
            state = self.hass.states.get(entity_id)
            if state and state.attributes.get("device_class") == device_class:
                result.append(entity_id)
        return result

    def by_area_entities(
        self, area_entities: Dict[str, List[dict]], domains: List[str]
    ) -> List[str]:
        """Get entities from area that match domains."""
        result = []
        for domain in domains:
            for entity in area_entities.get(domain, []):
                entity_id = entity.get("entity_id")
                if entity_id in self.all_entities:
                    result.append(entity_id)
        return sorted(set(result))


class StateOptionsBuilder:
    """Builds available state options for features."""

    @staticmethod
    def for_light_groups(
        secondary_states: dict, exclude_dark: bool = True
    ) -> List[str]:
        """Build available states for light groups."""
        from ..const import (
            AreaStates,
            BUILTIN_AREA_STATES,
            CONFIGURABLE_AREA_STATE_MAP,
        )

        states = [str(s) for s in BUILTIN_AREA_STATES]  # occupied, extended

        for state, entity_key in CONFIGURABLE_AREA_STATE_MAP.items():
            if exclude_dark and state == AreaStates.DARK:
                continue
            if secondary_states.get(entity_key):
                states.append(str(state))

        return states

    @staticmethod
    def for_fan_groups() -> List[str]:
        """Fan groups only use occupied/extended."""
        from ..const import AreaStates

        return [str(AreaStates.OCCUPIED), str(AreaStates.EXTENDED)]

    @staticmethod
    def for_area_aware_media_player(secondary_states: dict) -> List[str]:
        """Area aware media player states."""
        from ..const import (
            AreaStates,
            CONFIGURABLE_AREA_STATE_MAP,
        )

        states = [str(AreaStates.OCCUPIED), str(AreaStates.EXTENDED)]
        if secondary_states.get(CONFIGURABLE_AREA_STATE_MAP[AreaStates.SLEEP]):
            states.append(str(AreaStates.SLEEP))
        return states


class SelectorBuilder:
    """Auto-generate Home Assistant UI selectors from ConfigOption metadata."""

    @staticmethod
    def from_config_option(option: "ConfigOption") -> Any:
        """
        Build selector based on option's selector_type and selector_config.

        Args:
            option: ConfigOption with selector metadata

        Returns:
            Home Assistant selector instance

        Raises:
            ValueError: If selector_type is unknown or not specified
        """
        from custom_components.magic_areas.const import ConfigOption

        if not isinstance(option, ConfigOption):
            raise TypeError(f"Expected ConfigOption, got {type(option)}")

        selector_type = option.selector_type
        selector_config = option.selector_config or {}

        if selector_type == "boolean":
            return BooleanSelector(BooleanSelectorConfig())

        if selector_type == "select":
            config_dict = {
                "options": selector_config.get("options", []),
                "multiple": selector_config.get("multiple", False),
                "mode": selector_config.get("mode", SelectSelectorMode.DROPDOWN),
            }
            if "translation_key" in selector_config:
                config_dict["translation_key"] = selector_config["translation_key"]
            return SelectSelector(SelectSelectorConfig(**config_dict))

        if selector_type == "entity":
            config_dict = {"multiple": selector_config.get("multiple", False)}
            if "domain" in selector_config:
                config_dict["domain"] = selector_config["domain"]
            if "device_class" in selector_config:
                config_dict["device_class"] = selector_config["device_class"]
            if "include_entities" in selector_config:
                config_dict["include_entities"] = selector_config["include_entities"]
            return EntitySelector(EntitySelectorConfig(**config_dict))

        if selector_type == "number":
            config_dict = {
                "min": selector_config.get("min", 0),
                "max": selector_config.get("max", 9999),
                "step": selector_config.get("step", 1),
                "mode": selector_config.get("mode", NumberSelectorMode.BOX),
            }
            if "unit_of_measurement" in selector_config:
                config_dict["unit_of_measurement"] = selector_config[
                    "unit_of_measurement"
                ]
            return NumberSelector(NumberSelectorConfig(**config_dict))

        if selector_type == "text":
            config_dict = {"multiline": selector_config.get("multiline", False)}
            if "type" in selector_config:
                config_dict["type"] = selector_config["type"]
            return TextSelector(TextSelectorConfig(**config_dict))

        if selector_type is None:
            # No selector specified, return None to use validator
            return None

        raise ValueError(f"Unknown selector_type: {selector_type}")

    @staticmethod
    def from_option_set(option_set: type) -> Dict[str, Any]:
        """
        Generate all selectors for an OptionSet class.

        Args:
            option_set: OptionSet or FeatureOptionSet class

        Returns:
            Dict mapping option keys to selector instances
        """
        from custom_components.magic_areas.const import ConfigOption, OptionSet

        if not issubclass(option_set, OptionSet):
            raise TypeError(f"Expected OptionSet subclass, got {type(option_set)}")

        selectors = {}
        for attr_name in dir(option_set):
            attr = getattr(option_set, attr_name)
            if isinstance(attr, ConfigOption):
                try:
                    selector = SelectorBuilder.from_config_option(attr)
                    if selector is not None:
                        selectors[attr.key] = selector
                except (ValueError, TypeError) as err:
                    _LOGGER.debug(
                        "Could not build selector for %s.%s: %s",
                        option_set.__name__,
                        attr_name,
                        err,
                    )
                    continue

        return selectors


class SchemaBuilder:
    """Builds voluptuous schemas with selectors."""

    def __init__(self, saved_options: Optional[dict] = None):
        self.saved_options = saved_options or {}

    def build(
        self,
        options: List[Tuple[str, Any, Any]],  # (name, default, validator)
        selectors: Optional[Dict[str, Any]] = None,
        dynamic_validators: Optional[Dict[str, Any]] = None,
    ) -> vol.Schema:
        """Build schema from option definitions."""
        selectors = selectors or {}
        dynamic_validators = dynamic_validators or {}

        schema_fields = {}
        for name, default, validator in options:
            current_value = self.saved_options.get(name, default)
            field_validator = selectors.get(name) or dynamic_validators.get(
                name, validator
            )

            schema_fields[vol.Optional(name, default=current_value)] = field_validator

        return vol.Schema(schema_fields)

    def build_feature_schema(
        self,
        feature_options: List[Tuple[str, Any, Any]],
        feature_config: dict,
        selectors: Dict[str, Any],
    ) -> vol.Schema:
        """Build schema for a feature with current config as defaults."""
        # Temporarily save current options
        original_options = self.saved_options
        self.saved_options = feature_config

        # Build schema
        schema = self.build(
            options=feature_options,
            selectors=selectors,
        )

        # Restore original options
        self.saved_options = original_options
        return schema

    def from_option_set(
        self,
        option_set: type,
        saved_config: Optional[dict] = None,
        selector_overrides: Optional[Dict[str, Any]] = None,
    ) -> vol.Schema:
        """
        Auto-generate complete voluptuous schema from an OptionSet class.

        Uses ConfigOption metadata:
        - key: field name
        - default: default value
        - required: vol.Required vs vol.Optional
        - internal: exclude from schema if True
        - validator: validation function
        - selector_type/selector_config: UI selector generation

        Args:
            option_set: OptionSet or FeatureOptionSet class
            saved_config: Current config values (for defaults)
            selector_overrides: Manual selector overrides (key -> selector)

        Returns:
            Complete voluptuous schema

        Example:
            builder = SchemaBuilder()
            schema = builder.from_option_set(
                LightGroupOptions,
                saved_config=current_config,
                selector_overrides={
                    "overhead_lights": custom_entity_selector
                }
            )
        """
        from custom_components.magic_areas.const import ConfigOption, OptionSet

        if not issubclass(option_set, OptionSet):
            raise TypeError(f"Expected OptionSet subclass, got {type(option_set)}")

        saved_config = saved_config or self.saved_options
        selector_overrides = selector_overrides or {}

        # Auto-generate selectors from ConfigOption metadata
        auto_selectors = SelectorBuilder.from_option_set(option_set)

        # Merge with overrides (overrides take precedence)
        selectors = {**auto_selectors, **selector_overrides}

        schema_fields = {}
        for attr_name in dir(option_set):
            attr = getattr(option_set, attr_name)
            if not isinstance(attr, ConfigOption):
                continue

            # Skip internal fields (e.g., auto-generated UUIDs)
            if attr.internal:
                continue

            # Get current value or default
            current_value = saved_config.get(attr.key, attr.default)

            # Determine validator (selector > validator > cv.string)
            field_validator = selectors.get(attr.key)
            if field_validator is None:
                field_validator = attr.validator if attr.validator else cv.string

            # Build schema field (required vs optional)
            if attr.required:
                schema_fields[vol.Required(attr.key)] = field_validator
            else:
                schema_fields[vol.Optional(attr.key, default=current_value)] = (
                    field_validator
                )

        return vol.Schema(schema_fields, extra=vol.REMOVE_EXTRA)
