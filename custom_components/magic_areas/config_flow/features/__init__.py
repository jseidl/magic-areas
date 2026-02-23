"""Feature handlers registry."""

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

from custom_components.magic_areas.config_flow.features.base import FeatureHandler
from custom_components.magic_areas.const import (
    NON_CONFIGURABLE_FEATURES_META,
    AreaConfigOptions,
    AreaType,
)
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.area_aware_media_player import (
    AreaAwareMediaPlayerOptions,
)
from custom_components.magic_areas.const.ble_trackers import BleTrackerOptions
from custom_components.magic_areas.const.climate_control import ClimateControlOptions
from custom_components.magic_areas.const.fan_groups import FanGroupOptions
from custom_components.magic_areas.const.health import HealthOptions
from custom_components.magic_areas.const.light_groups import LightGroupOptions
from custom_components.magic_areas.const.presence_hold import PresenceHoldOptions
from custom_components.magic_areas.const.wasp_in_a_box import WaspInABoxOptions

if TYPE_CHECKING:
    from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

# Registry of feature handlers
_feature_handlers: dict[str, type[FeatureHandler]] = {}

# List of FeatureOptionSet classes
# This is used to check if a feature has configuration options
_feature_option_sets = [
    AggregateOptions,
    HealthOptions,
    PresenceHoldOptions,
    BleTrackerOptions,
    WaspInABoxOptions,
    AreaAwareMediaPlayerOptions,
    ClimateControlOptions,
    FanGroupOptions,
    LightGroupOptions,
]


def register_feature(
    handler_class: type[FeatureHandler],
) -> type[FeatureHandler]:
    """Register a feature handler for auto-discovery."""
    # Create temp instance to get feature_id
    # We use a mock flow for initialization
    temp_instance = handler_class(None)  # type: ignore
    feature_id = temp_instance.feature_id
    _feature_handlers[feature_id] = handler_class
    _LOGGER.debug("Registered feature handler: %s", feature_id)
    return handler_class


def get_feature_handler(feature_id: str, flow: "OptionsFlowHandler") -> FeatureHandler:
    """Get an instance of a feature handler."""
    handler_class = _feature_handlers.get(feature_id)
    if handler_class:
        return handler_class(flow)
    raise ValueError(f"Unknown feature: {feature_id}")


def get_available_features(flow: "OptionsFlowHandler") -> dict[str, FeatureHandler]:
    """Get all available feature handlers for current area."""
    result = {}
    area_type = flow.area.config.get(AreaConfigOptions.TYPE)

    for feature_id, handler_class in _feature_handlers.items():
        handler = handler_class(flow)

        # Check if feature is available for this area type
        if area_type == AreaType.META and not handler.is_available:
            continue

        result[feature_id] = handler

    return result


def get_configurable_features(flow: "OptionsFlowHandler") -> list[str]:
    """Get list of configurable features for current area type using introspection.

    Returns list of feature IDs that have configuration options and are
    available for the current area type.

    Args:
        flow: The OptionsFlowHandler instance

    Returns:
        List of feature IDs (strings) that are configurable

    """
    configurable = []
    is_meta = flow.area.is_meta()

    for option_set_class in _feature_option_sets:
        # Get feature ID from the class
        feature_id = option_set_class.FEATURE_KEY

        # Check if feature has configuration options
        if not option_set_class.has_configuration():
            continue

        # Check if available for this area type (meta areas filter)
        if is_meta and feature_id in [f.value for f in NON_CONFIGURABLE_FEATURES_META]:
            continue

        configurable.append(feature_id)

    return configurable


# Auto-import all feature modules to trigger registrations
def _load_features():
    """Dynamically import all feature modules."""
    package_dir = __path__[0]
    for _, module_name, _ in pkgutil.iter_modules([package_dir]):
        if module_name.startswith("_"):
            continue
        try:
            importlib.import_module(f"{__name__}.{module_name}")
            _LOGGER.debug("Loaded feature module: %s", module_name)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Catch all exceptions to prevent blocking other feature modules
            _LOGGER.warning("Failed to load feature module %s: %s", module_name, exc)


# Load features on module import
_load_features()
