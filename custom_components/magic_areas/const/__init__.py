"""Core constants for Magic Areas - shared across all features."""

from dataclasses import dataclass
from enum import IntEnum, StrEnum, auto
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.climate.const import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.cover.const import DOMAIN as COVER_DOMAIN
from homeassistant.components.device_tracker.const import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.components.sensor.const import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.components.sun.const import DOMAIN as SUN_DOMAIN
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    STATE_ON,
    STATE_OPEN,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers import config_validation as cv

# Utility Constants
ONE_MINUTE = 60  # seconds, for conversion
EMPTY_STRING = ""
EMPTY_ENTRY = [""]

# Domain Constants
DOMAIN = "magic_areas"

# Config Entry Keys
CONF_AREA_ID = "id"  # Area identifier stored in config_entry.data

# Additional Constants
ADDITIONAL_LIGHT_TRACKING_ENTITIES = ["sun.sun"]
DEFAULT_SENSOR_PRECISION = 2
UPDATE_INTERVAL = ONE_MINUTE

# MagicAreas Components
MAGIC_AREAS_COMPONENTS = [
    BINARY_SENSOR_DOMAIN,
    MEDIA_PLAYER_DOMAIN,
    COVER_DOMAIN,
    SWITCH_DOMAIN,
    SENSOR_DOMAIN,
    LIGHT_DOMAIN,
    FAN_DOMAIN,
]

MAGIC_AREAS_COMPONENTS_META = [
    BINARY_SENSOR_DOMAIN,
    MEDIA_PLAYER_DOMAIN,
    COVER_DOMAIN,
    SENSOR_DOMAIN,
    LIGHT_DOMAIN,
    SWITCH_DOMAIN,
]

MAGIC_AREAS_COMPONENTS_GLOBAL = MAGIC_AREAS_COMPONENTS_META

MAGICAREAS_UNIQUEID_PREFIX = "magic_areas"
MAGIC_DEVICE_ID_PREFIX = "magic_area_device_"


# Configuration Domain Keys
class ConfigDomains(StrEnum):
    """Top-level configuration domain keys."""

    AREA = "area"  # Basic area settings
    PRESENCE = "presence_tracking"  # Presence tracking settings
    SECONDARY_STATES = "secondary_states"  # Secondary state configuration
    USER_DEFINED_STATES = "user_defined_states"  # User-defined custom states
    FEATURES = "features"  # Feature-specific configuration


# Base Classes for Configuration
@dataclass(frozen=True)
class ConfigOption:
    """Defines a configuration option with complete metadata for auto-generation.

    This class provides a single source of truth for configuration options,
    including validation, UI generation, and documentation.

    Example:
        CLEAR_TIMEOUT = ConfigOption(
            key="clear_timeout",
            default=60,
            title="Clear Timeout",
            description="Time in minutes before area is marked as clear",
            validator=cv.positive_int,
            selector_type="number",
            selector_config={"min": 0, "max": 120, "unit_of_measurement": "minutes"},
            required=False,
            translation_key="clear_timeout"
        )

    Attributes:
        key: Configuration dictionary key
        default: Default value if not specified
        title: UI form field title (short, bold heading)
        description: Help text shown to user (detailed explanation)
        translation_key: Key for i18n translation lookups
        validator: Voluptuous validator (cv.entity_id, int, cv.boolean, etc.)
        required: Whether field is required (uses vol.Required vs vol.Optional)
        internal: If True, exclude from user-facing schemas (e.g., auto-generated UUIDs)
        selector_type: Type of UI selector ("entity", "select", "number", "boolean", "text")
        selector_config: Type-specific configuration for the selector
        _parent: Internal reference to parent OptionSet class

    """

    key: str
    default: Any

    # UI display metadata
    title: str | None = None
    description: str | None = None
    translation_key: str | None = None

    # Validation & schema generation
    validator: Any = None
    required: bool = False
    internal: bool = False

    # UI selector generation
    selector_type: str | None = None
    selector_config: dict | None = None

    # Internal
    _parent: type["OptionSet"] | None = None

    def __set_name__(self, owner: type["OptionSet"], name: str):
        """Set the parent class when used as a class attribute."""
        # pylint: disable=protected-access
        # Intentional internal API for ConfigOption/OptionSet system
        object.__setattr__(self, "_parent", owner)

    def get_from(self, config: dict) -> Any:
        """Get this option's value from config dict."""
        return config.get(self.key, self.default)


class OptionSet:
    """Base class for configuration option groups with a config domain."""

    CONFIG_DOMAIN: ConfigDomains

    @classmethod
    def to_config(cls, config: dict) -> dict:
        """Wrap config dict in the appropriate domain structure.

        Example:
            SecondaryStateOptions.to_config({
                SecondaryStateOptions.DARK_ENTITY.key: "binary_sensor.x"
            })
            # Returns: {"secondary_states": {"dark_entity": "binary_sensor.x"}}

        """
        return {cls.CONFIG_DOMAIN.value: config}

    @classmethod
    def from_user_input(cls, user_input: dict) -> dict:
        """Build config dict from user input, applying defaults for missing keys.

        Example:
            LightGroupEntryOptions.from_user_input({
                LightGroupEntryOptions.NAME.key: "My Group",
                LightGroupEntryOptions.LIGHTS.key: ["light.1"]
            })
            # Returns dict with NAME and LIGHTS from input, rest from defaults

        Args:
            user_input: Partial or complete user input dict

        Returns:
            Complete config dict with all keys, using defaults where not provided

        """
        result = {}
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, ConfigOption):
                result[attr.key] = user_input.get(attr.key, attr.default)
        return result


class FeatureOptionSet(OptionSet):
    """Extended OptionSet for feature-specific configuration.

    Features are optional components that can be enabled/disabled.
    Feature presence in the config indicates it is enabled.
    """

    FEATURE_KEY: str  # Feature identifier (e.g., "light_groups")

    @classmethod
    def get_feature_config(cls, config: dict) -> dict:
        """Get feature-specific config from main config dict."""
        features = config.get(ConfigDomains.FEATURES.value, {})
        return features.get(cls.FEATURE_KEY, {})

    @classmethod
    def to_config(cls, config: dict) -> dict:
        """Wrap config dict in features.{feature_key} structure.

        Example:
            AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1})
            # Returns: {"features": {"aggregates": {"aggregates_min_entities": 1}}}

        """
        return {cls.CONFIG_DOMAIN.value: {cls.FEATURE_KEY: config}}

    @classmethod
    def has_configuration(cls) -> bool:
        """Check if this feature has any configuration options.

        Returns True if the FeatureOptionSet has at least one ConfigOption defined,
        False otherwise. Used to determine if the feature should appear in the
        configuration menu.
        """
        for attr_name in dir(cls):
            # Skip private/magic attributes
            if attr_name.startswith("_"):
                continue
            try:
                attr = getattr(cls, attr_name)
                if isinstance(attr, ConfigOption):
                    return True
            except AttributeError:
                continue
        return False


class ConfigHelper:
    """Helper class for accessing area configuration with ConfigOption support."""

    def __init__(self, config: dict):
        """Initialize with raw config dict."""
        self._config = config

    def get(self, option: ConfigOption) -> Any:
        """Get option value from config.

        Automatically determines the config domain from the option's parent class.

        Args:
            option: The ConfigOption to retrieve (e.g., SecondaryStateOptions.EXTENDED_TIME)

        Returns:
            The option value or its default

        Raises:
            ValueError: If the option has no parent class

        """
        # pylint: disable=protected-access
        # Accessing internal _parent attribute is intentional part of ConfigOption API
        if option._parent is None:
            raise ValueError(f"ConfigOption '{option.key}' has no parent class")

        domain_config = self._config.get(option._parent.CONFIG_DOMAIN.value, {})

        # If this is a FeatureOptionSet, go one level deeper to the specific feature
        if issubclass(option._parent, FeatureOptionSet):
            domain_config = domain_config.get(option._parent.FEATURE_KEY, {})

        return option.get_from(domain_config)

    def get_raw(self, key: str, default: Any = None) -> Any:
        """Get raw config value (for non-ConfigOption access)."""
        return self._config.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access for raw config."""
        return self._config[key]


# Core Configuration Option Sets


class AreaConfigOptions(OptionSet):
    """Basic area configuration options."""

    CONFIG_DOMAIN = ConfigDomains.AREA

    TYPE = ConfigOption(
        key="type",
        default="interior",
        title="Area Type",
        description="Define if this is an interior or exterior area",
        translation_key="area_type",
        validator=vol.In(["interior", "exterior"]),
        selector_type="select",
        selector_config={
            "options": ["interior", "exterior"],
            "translation_key": "area_type",
        },
    )

    INCLUDE_ENTITIES = ConfigOption(
        key="include_entities",
        default=[],
        title="Include Entities",
        description="Additional entities to include in this area beyond those automatically detected",
        translation_key="include_entities",
        validator=cv.entity_ids,
        selector_type="entity",
        selector_config={"multiple": True},
    )

    EXCLUDE_ENTITIES = ConfigOption(
        key="exclude_entities",
        default=[],
        title="Exclude Entities",
        description="Entities to exclude from this area",
        translation_key="exclude_entities",
        validator=cv.entity_ids,
        selector_type="entity",
        selector_config={"multiple": True},
    )

    WINDOWLESS = ConfigOption(
        key="windowless",
        default=False,
        validator=cv.boolean,
        selector_type="boolean",
        title="Windowless Area",
        description="Enable for areas with no natural light (bathrooms, closets, basements). Skips exterior brightness checks.",
    )

    RELOAD_ON_REGISTRY_CHANGE = ConfigOption(
        key="reload_on_registry_change",
        default=True,
        title="Reload on Registry Change",
        description="Automatically reload the area when entities are added or removed",
        translation_key="reload_on_registry_change",
        validator=cv.boolean,
        selector_type="boolean",
    )

    IGNORE_DIAGNOSTIC_ENTITIES = ConfigOption(
        key="ignore_diagnostic_entities",
        default=True,
        title="Ignore Diagnostic Entities",
        description="Exclude diagnostic and configuration entities from presence detection",
        translation_key="ignore_diagnostic_entities",
        validator=cv.boolean,
        selector_type="boolean",
    )


class PresenceTrackingOptions(OptionSet):
    """Presence tracking configuration options."""

    CONFIG_DOMAIN = ConfigDomains.PRESENCE

    DEVICE_PLATFORMS = ConfigOption(
        key="presence_device_platforms",
        default=[MEDIA_PLAYER_DOMAIN, BINARY_SENSOR_DOMAIN],
        title="Device Platforms",
        description="Device types to use for presence detection",
        translation_key="presence_device_platforms",
        validator=cv.ensure_list,
        selector_type="select",
        selector_config={
            "options": [
                MEDIA_PLAYER_DOMAIN,
                BINARY_SENSOR_DOMAIN,
                REMOTE_DOMAIN,
                DEVICE_TRACKER_DOMAIN,
            ],
            "multiple": True,
        },
    )

    SENSOR_DEVICE_CLASS = ConfigOption(
        key="presence_sensor_device_class",
        default=["motion", "occupancy", "presence"],
        title="Sensor Device Classes",
        description="Binary sensor device classes to use for presence detection",
        translation_key="presence_sensor_device_class",
        validator=cv.ensure_list,
        selector_type="select",
        selector_config={
            "options": [cls.value for cls in BinarySensorDeviceClass],
            "multiple": True,
        },
    )

    KEEP_ONLY_ENTITIES = ConfigOption(
        key="keep_only_entities",
        default=[],
        title="Keep Only These Entities",
        description="If specified, only these entities will be used for presence detection (overrides platform/class filters)",
        translation_key="keep_only_entities",
        validator=cv.entity_ids,
        selector_type="entity",
        selector_config={"multiple": True},
    )

    CLEAR_TIMEOUT = ConfigOption(
        key="clear_timeout",
        default=1,
        title="Clear Timeout",
        description="Minutes to wait after all presence sensors are inactive before marking area as clear",
        translation_key="clear_timeout",
        validator=cv.positive_int,
        selector_type="number",
        selector_config={
            "min": 0,
            "max": 120,
            "unit_of_measurement": "minutes",
        },
    )

    ENABLE_DEBUG_ATTRIBUTES = ConfigOption(
        key="enable_debug_attributes",
        default=True,
        title="Enable Debug Attributes",
        description="Enable additional attributes on the presence sensor to help diagnose issues. Disable once stable to improve performance.",
        translation_key="enable_debug_attributes",
        validator=cv.boolean,
        selector_type="boolean",
    )


# Enums


class MetaAreaAutoReloadSettings(IntEnum):
    """Settings for Meta-Area Auto Reload functionality."""

    DELAY = 2  # Debounce window (seconds) for floor/interior/exterior meta-areas
    GLOBAL_DELAY = 6  # Debounce window (seconds) for global meta-area (waits for meta-areas to reload first)


class CalculationMode(StrEnum):
    """Modes for calculating values."""

    ANY = auto()
    ALL = auto()
    MAJORITY = auto()


class MagicConfigEntryVersion(IntEnum):
    """Magic Area config entry version."""

    MAJOR = 2
    MINOR = 2


class AreaStates(StrEnum):
    """Magic area states."""

    CLEAR = auto()
    OCCUPIED = auto()
    EXTENDED = auto()
    DARK = auto()
    BRIGHT = auto()
    SLEEP = auto()


class AreaType(StrEnum):
    """Regular area types."""

    INTERIOR = auto()
    EXTERIOR = auto()
    META = auto()


class CommonAttributes(StrEnum):
    """Attribute names shared by multiple entities."""

    STATES = auto()
    ACTIVE_SENSORS = auto()


class AreaAttributes(StrEnum):
    """Attributes for area state sensor."""

    AREAS = auto()
    ACTIVE_AREAS = auto()
    TYPE = auto()
    LIGHT_SENSOR = auto()
    CLEAR_TIMEOUT = auto()
    LAST_ACTIVE_SENSORS = auto()
    FEATURES = auto()
    PRESENCE_SENSORS = auto()


class MetaAreaType(StrEnum):
    """Meta area types."""

    GLOBAL = "global"
    INTERIOR = "interior"
    EXTERIOR = "exterior"
    FLOOR = "floor"


class Features(StrEnum):
    """Magic Areas features."""

    CLIMATE_CONTROL = "climate_control"
    FAN_GROUPS = "fan_groups"
    MEDIA_PLAYER_GROUPS = "media_player_groups"
    LIGHT_GROUPS = "light_groups"
    COVER_GROUPS = "cover_groups"
    AREA_AWARE_MEDIA_PLAYER = "area_aware_media_player"
    AGGREGATION = "aggregates"
    HEALTH = "health"
    PRESENCE_HOLD = "presence_hold"
    BLE_TRACKERS = "ble_trackers"
    WASP_IN_A_BOX = "wasp_in_a_box"


class MagicAreasEvents(StrEnum):
    """Magic Areas events."""

    AREA_STATE_CHANGED = "magicareas_area_state_changed"
    AREA_LOADED = "magicareas_area_loaded"


class SelectorTranslationKeys(StrEnum):
    """Translation keys for config flow UI selectors."""

    CLIMATE_PRESET_LIST = auto()
    AREA_TYPE = auto()
    AREA_STATES = auto()
    CONTROL_ON = auto()
    CALCULATION_MODE = auto()


class MetaAreaIcons(StrEnum):
    """Meta area icons."""

    INTERIOR = "mdi:home-import-outline"
    EXTERIOR = "mdi:home-export-outline"
    GLOBAL = "mdi:home"


class FeatureIcons(StrEnum):
    """Feature related icons."""

    PRESENCE_HOLD_SWITCH = "mdi:car-brake-hold"
    LIGHT_CONTROL_SWITCH = "mdi:lightbulb-auto-outline"
    MEDIA_CONTROL_SWITCH = "mdi:auto-mode"
    CLIMATE_CONTROL_SWITCH = "mdi:thermostat-auto"


# Area State Constants
# All states defined in AreaStates enum (built into the integration)
BUILTIN_AREA_STATES = [state.value for state in AreaStates]

# Basic occupancy states (for config flow UI showing base states)
BASIC_OCCUPANCY_STATES = [AreaStates.OCCUPIED.value, AreaStates.EXTENDED.value]

# Meta Areas
META_AREA_GLOBAL = "Global"
META_AREA_INTERIOR = "Interior"
META_AREA_EXTERIOR = "Exterior"
META_AREAS = [META_AREA_GLOBAL, META_AREA_INTERIOR, META_AREA_EXTERIOR]

# Area Types
AREA_TYPES = list(AreaType)

INVALID_STATES = [STATE_UNAVAILABLE, STATE_UNKNOWN]
PRESENCE_SENSOR_VALID_ON_STATES = [STATE_ON, STATE_OPEN, STATE_PLAYING]

# Device Class Lists
ALL_BINARY_SENSOR_DEVICE_CLASSES = [cls.value for cls in BinarySensorDeviceClass]
ALL_SENSOR_DEVICE_CLASSES = [cls.value for cls in SensorDeviceClass]


# Feature Lists
FEATURE_LIST_META = [
    Features.MEDIA_PLAYER_GROUPS,
    Features.LIGHT_GROUPS,
    Features.COVER_GROUPS,
    Features.CLIMATE_CONTROL,
    Features.AGGREGATION,
    Features.HEALTH,
]

FEATURE_LIST = FEATURE_LIST_META + [
    Features.AREA_AWARE_MEDIA_PLAYER,
    Features.PRESENCE_HOLD,
    Features.BLE_TRACKERS,
    Features.FAN_GROUPS,
    Features.WASP_IN_A_BOX,
]

FEATURE_LIST_GLOBAL = FEATURE_LIST_META

ALL_FEATURES = set(FEATURE_LIST) | set(FEATURE_LIST_GLOBAL)

NON_CONFIGURABLE_FEATURES_META = [
    Features.LIGHT_GROUPS,
    Features.FAN_GROUPS,
]

# Config Flow filters
CONFIG_FLOW_ENTITY_FILTER = [
    BINARY_SENSOR_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
    INPUT_BOOLEAN_DOMAIN,
]
CONFIG_FLOW_ENTITY_FILTER_BOOL = [
    BINARY_SENSOR_DOMAIN,
    SWITCH_DOMAIN,
    INPUT_BOOLEAN_DOMAIN,
]
CONFIG_FLOW_ENTITY_FILTER_EXT = CONFIG_FLOW_ENTITY_FILTER + [
    LIGHT_DOMAIN,
    MEDIA_PLAYER_DOMAIN,
    CLIMATE_DOMAIN,
    SUN_DOMAIN,
    FAN_DOMAIN,
]


# Feature Info Classes - used for entity naming and translation
class MagicAreasFeatureInfo:
    """Base class for feature information."""

    id: str
    translation_keys: dict[str, str | None]
    icons: dict[str, str] = {}


class MagicAreasFeatureInfoPresenceTracking(MagicAreasFeatureInfo):
    """Feature information for feature: Presence Tracking."""

    id = "presence_tracking"
    translation_keys = {BINARY_SENSOR_DOMAIN: "area_state"}
    icons = {BINARY_SENSOR_DOMAIN: "mdi:texture-box"}


class MagicAreasFeatureInfoPresenceHold(MagicAreasFeatureInfo):
    """Feature information for feature: Presence hold."""

    id = "presence_hold"
    translation_keys = {SWITCH_DOMAIN: "presence_hold"}
    icons = {SWITCH_DOMAIN: "mdi:car-brake-hold"}


class MagicAreasFeatureInfoBLETrackers(MagicAreasFeatureInfo):
    """Feature information for feature: BLE Trackers."""

    id = "ble_trackers"
    translation_keys = {BINARY_SENSOR_DOMAIN: "ble_tracker_monitor"}
    icons = {BINARY_SENSOR_DOMAIN: "mdi:bluetooth"}


class MagicAreasFeatureInfoWaspInABox(MagicAreasFeatureInfo):
    """Feature information for feature: Wasp in a box."""

    id = "wasp_in_a_box"
    translation_keys = {BINARY_SENSOR_DOMAIN: "wasp_in_a_box"}
    icons = {BINARY_SENSOR_DOMAIN: "mdi:bee"}


class MagicAreasFeatureInfoAggregates(MagicAreasFeatureInfo):
    """Feature information for feature: Aggregates."""

    id = "aggregates"
    translation_keys = {
        BINARY_SENSOR_DOMAIN: "aggregate",
        SENSOR_DOMAIN: "aggregate",
    }


class MagicAreasFeatureInfoThrehsold(MagicAreasFeatureInfo):
    """Feature information for feature: Aggregate Threshold Sensors."""

    id = "threshold"
    translation_keys = {BINARY_SENSOR_DOMAIN: "threshold"}


class MagicAreasFeatureInfoHealth(MagicAreasFeatureInfo):
    """Feature information for feature: Health sensors."""

    id = "health"
    translation_keys = {BINARY_SENSOR_DOMAIN: "health"}


class MagicAreasFeatureInfoLightGroups(MagicAreasFeatureInfo):
    """Feature information for feature: Light groups."""

    id = "light_groups"
    translation_keys = {
        LIGHT_DOMAIN: None,  # let light category be appended to it
        SWITCH_DOMAIN: "light_control",
    }
    icons = {
        LIGHT_DOMAIN: "mdi:lightbulb-group",
        SWITCH_DOMAIN: "mdi:lightbulb-auto-outline",
    }


class MagicAreasFeatureInfoClimateControl(MagicAreasFeatureInfo):
    """Feature information for feature: Climate control."""

    id = "climate_control"
    translation_keys = {
        SWITCH_DOMAIN: "climate_control",
    }
    icons = {SWITCH_DOMAIN: "mdi:thermostat-auto"}


class MagicAreasFeatureInfoFanGroups(MagicAreasFeatureInfo):
    """Feature information for feature: Fan groups."""

    id = "fan_groups"
    translation_keys = {
        FAN_DOMAIN: "fan_group",
        SWITCH_DOMAIN: "fan_control",
    }
    icons = {SWITCH_DOMAIN: "mdi:fan-auto"}


class MagicAreasFeatureInfoMediaPlayerGroups(MagicAreasFeatureInfo):
    """Feature information for feature: Media player groups."""

    id = "media_player_groups"
    translation_keys = {
        MEDIA_PLAYER_DOMAIN: "media_player_group",
        SWITCH_DOMAIN: "media_player_control",
    }
    icons = {SWITCH_DOMAIN: "mdi:auto-mode"}


class MagicAreasFeatureInfoCoverGroups(MagicAreasFeatureInfo):
    """Feature information for feature: Cover groups."""

    id = "cover_groups"
    translation_keys = {COVER_DOMAIN: "cover_group"}


class MagicAreasFeatureInfoAreaAwareMediaPlayer(MagicAreasFeatureInfo):
    """Feature information for feature: Area-aware media player."""

    id = "area_aware_media_player"
    translation_keys = {MEDIA_PLAYER_DOMAIN: "area_aware_media_player"}
