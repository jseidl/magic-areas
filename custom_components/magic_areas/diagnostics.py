"""Diagnostics support for Magic Areas."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.magic_areas.base.magic import MagicArea, MagicMetaArea
from custom_components.magic_areas.const import ConfigDomains

# Nothing sensitive is stored today; kept as a guard for future options.
TO_REDACT: set[str] = {"password", "token", "api_key", "access_token"}


def _magic_entities(hass: HomeAssistant, area: MagicArea) -> dict[str, list[str]]:
    """Return the entity ids created by this config entry, grouped by domain."""
    entities: dict[str, list[str]] = {}
    for entry in er.async_entries_for_config_entry(
        er.async_get(hass), area.hass_config.entry_id
    ):
        entities.setdefault(entry.domain, []).append(entry.entity_id)
    return {domain: sorted(ids) for domain, ids in entities.items()}


def _area_diagnostics(hass: HomeAssistant, area: MagicArea) -> dict[str, Any]:
    """Build the diagnostics section describing a Magic Area."""
    area_state = hass.states.get(
        f"binary_sensor.magic_areas_presence_tracking_{area.slug}_area_state"
    )

    diagnostics: dict[str, Any] = {
        "id": area.id,
        "name": area.name,
        "slug": area.slug,
        "type": str(area.area_type),
        "is_meta": area.is_meta(),
        "floor_id": area.floor_id,
        "initialized": area.initialized,
        "icon": area.icon,
        "states": sorted(str(state) for state in area.states),
        "is_occupied": area.is_occupied(),
        "is_dark": area.is_area_dark(),
        "light_sensor": area.area_light_sensor,
        "available_platforms": sorted(str(p) for p in area.available_platforms()),
        "loaded_platforms": sorted(str(p) for p in area.loaded_platforms),
        "features": sorted(
            str(feature) for feature in area.config.get_raw(ConfigDomains.FEATURES, {})
        ),
        "presence_sensors": sorted(area.get_presence_sensors()),
        "entities": {
            domain: sorted(entity["entity_id"] for entity in entities)
            for domain, entities in area.entities.items()
        },
        "magic_entities": _magic_entities(hass, area),
        "area_state_entity": (
            {
                "entity_id": area_state.entity_id,
                "state": area_state.state,
                "attributes": dict(area_state.attributes),
            }
            if area_state
            else None
        ),
    }

    if isinstance(area, MagicMetaArea):
        diagnostics["child_areas"] = sorted(area.child_areas)

    return diagnostics


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "version": entry.version,
            "state": str(entry.state),
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
    }

    area: MagicArea | None = getattr(entry, "runtime_data", None)
    if area is None:
        diagnostics["area"] = None
        return diagnostics

    diagnostics["area"] = _area_diagnostics(hass, area)
    return diagnostics
