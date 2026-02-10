"""Feature handlers registry."""

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

from custom_components.magic_areas.config_flow.features.base import FeatureHandler

if TYPE_CHECKING:
    from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

# Registry of feature handlers
_feature_handlers: dict[str, type[FeatureHandler]] = {}


def register_feature(
    handler_class: type[FeatureHandler],
) -> type[FeatureHandler]:
    """Decorator to register a feature handler."""
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
    from custom_components.magic_areas.const import AreaConfigOptions, AreaType

    result = {}
    area_type = flow.area.config.get(AreaConfigOptions.TYPE)

    for feature_id, handler_class in _feature_handlers.items():
        handler = handler_class(flow)

        # Check if feature is available for this area type
        if area_type == AreaType.META and not handler.is_available:
            continue

        result[feature_id] = handler

    return result


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
        except Exception as exc:
            _LOGGER.warning("Failed to load feature module %s: %s", module_name, exc)


# Load features on module import
_load_features()
