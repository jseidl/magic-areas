"""Tests for the Magic Areas config flow."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.magic_areas.config_flow import OptionsFlowHandler
from custom_components.magic_areas.const import (
    CONF_AGGREGATES_MIN_ENTITIES,
    CONF_CLEAR_TIMEOUT,
    CONF_ENABLED_FEATURES,
    CONF_EXCLUDE_ENTITIES,
    CONF_FEATURE_AGGREGATION,
    CONF_FEATURE_CLIMATE_CONTROL,
    CONF_RELOAD_ON_REGISTRY_CHANGE,
    CONF_SECONDARY_STATES,
    CONF_SLEEP_TIMEOUT,
    CONF_TYPE,
    DOMAIN,
    AreaType,
)


def _meta_area_options_handler(
    area_options: dict,
) -> tuple[OptionsFlowHandler, AsyncMock]:
    """Return an options handler configured for a meta area."""
    handler = OptionsFlowHandler(MockConfigEntry(domain=DOMAIN, data={}))
    handler.area = MagicMock(name="Bedrooms", is_meta=MagicMock(return_value=True))
    handler.area_options = area_options

    show_menu = AsyncMock(return_value={"type": "menu"})
    handler.async_step_show_menu = show_menu
    return handler, show_menu


async def test_meta_area_options_steps_preserve_feature_configuration() -> None:
    """Changing non-feature options must preserve all feature configuration."""
    features = {
        CONF_FEATURE_AGGREGATION: {CONF_AGGREGATES_MIN_ENTITIES: 3},
        CONF_FEATURE_CLIMATE_CONTROL: {
            "entity_id": "climate.bedrooms",
            "preset_clear": "away",
            "preset_occupied": "home",
        },
    }
    area_options = {
        CONF_TYPE: AreaType.META,
        CONF_ENABLED_FEATURES: deepcopy(features),
        CONF_EXCLUDE_ENTITIES: ["sensor.old"],
        CONF_CLEAR_TIMEOUT: 0,
        CONF_SECONDARY_STATES: {},
    }
    handler, show_menu = _meta_area_options_handler(area_options)

    await handler.async_step_area_config(
        {
            CONF_EXCLUDE_ENTITIES: ["sensor.new"],
            CONF_RELOAD_ON_REGISTRY_CHANGE: True,
        }
    )
    assert handler.area_options[CONF_ENABLED_FEATURES] == features

    await handler.async_step_presence_tracking({CONF_CLEAR_TIMEOUT: 5})
    assert handler.area_options[CONF_ENABLED_FEATURES] == features

    await handler.async_step_secondary_states({CONF_SLEEP_TIMEOUT: 10})
    assert handler.area_options[CONF_ENABLED_FEATURES] == features
    assert show_menu.await_count == 3
