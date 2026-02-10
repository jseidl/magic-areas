"""Magic Areas component for Home Assistant."""

from collections.abc import Callable
from datetime import UTC, datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    EVENT_DEVICE_REGISTRY_UPDATED,
    EventDeviceRegistryUpdatedData,
)
from homeassistant.helpers.entity_registry import (
    EVENT_ENTITY_REGISTRY_UPDATED,
    EventEntityRegistryUpdatedData,
)

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    DATA_AREA_OBJECT,
    DATA_TRACKED_LISTENERS,
    MODULE_DATA,
    AreaConfigOptions,
    MagicConfigEntryVersion,
)
from custom_components.magic_areas.helpers.area import get_magic_area_for_config_entry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up the component."""

    @callback
    async def _async_reload_entry(*args, **kwargs) -> None:
        # Prevent reloads if we're not fully loaded yet
        if not hass.is_running:
            return

        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, "entity_ts": datetime.now(UTC)},
        )

    @callback
    async def _async_registry_updated(
        event: (
            Event[EventEntityRegistryUpdatedData]
            | Event[EventDeviceRegistryUpdatedData]
        ),
    ) -> None:
        """Reload integration when entity registry is updated."""

        area_data: dict[str, Any] = dict(config_entry.data)
        if config_entry.options:
            area_data.update(config_entry.options)

        # Check if disabled
        if not area_data.get(
            AreaConfigOptions.RELOAD_ON_REGISTRY_CHANGE.key,
            AreaConfigOptions.RELOAD_ON_REGISTRY_CHANGE.default,
        ):
            _LOGGER.debug(
                "%s: Auto-Reloading disabled for this area skipping...",
                config_entry.title,
            )
            return

        _LOGGER.debug(
            "%s: Reloading entry due entity registry change",
            config_entry.title,
        )

        await _async_reload_entry()

    async def _async_setup_integration(*args, **kwargs) -> None:
        """Load integration when Hass has finished starting."""
        _LOGGER.debug("Setting up entry for %s", config_entry.title)

        magic_area: MagicArea | None = get_magic_area_for_config_entry(
            hass, config_entry
        )
        assert magic_area is not None
        await magic_area.initialize()

        _LOGGER.debug(
            "%s: Magic Area (%s) created: %s",
            magic_area.name,
            magic_area.id,
            str(magic_area.config),
        )

        # Setup config uptate listener
        tracked_listeners: list[Callable] = []
        tracked_listeners.append(config_entry.add_update_listener(async_update_options))

        # Watch for area changes.
        if not magic_area.is_meta():
            tracked_listeners.append(
                hass.bus.async_listen(
                    EVENT_ENTITY_REGISTRY_UPDATED,
                    _async_registry_updated,
                    magic_area.make_entity_registry_filter(),
                )
            )
            tracked_listeners.append(
                hass.bus.async_listen(
                    EVENT_DEVICE_REGISTRY_UPDATED,
                    _async_registry_updated,
                    magic_area.make_device_registry_filter(),
                )
            )
            # Reload once Home Assistant has finished starting to make sure we have all entities.
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_reload_entry)

        hass.data[MODULE_DATA][config_entry.entry_id] = {
            DATA_AREA_OBJECT: magic_area,
            DATA_TRACKED_LISTENERS: tracked_listeners,
        }

        # Setup platforms
        await hass.config_entries.async_forward_entry_setups(
            config_entry, magic_area.available_platforms()
        )

    hass.data.setdefault(MODULE_DATA, {})

    await _async_setup_integration()

    return True


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug(
        "Detected options change for entry %s, reloading", config_entry.entry_id
    )
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if MODULE_DATA not in hass.data:
        _LOGGER.warning(
            "Module data object for Magic Areas not found, possibly already removed."
        )
        return False

    data = hass.data[MODULE_DATA]

    if config_entry.entry_id not in data:
        _LOGGER.debug(
            "Config entry '%s' not on data dictionary, probably already unloaded. Skipping.",
            config_entry.entry_id,
        )
        return True

    area_data = data[config_entry.entry_id]
    area = area_data[DATA_AREA_OBJECT]

    all_unloaded = await hass.config_entries.async_unload_platforms(
        config_entry, area.available_platforms()
    )

    for tracked_listener in area_data[DATA_TRACKED_LISTENERS]:
        tracked_listener()

    if all_unloaded:
        data.pop(config_entry.entry_id)

    if not data:
        hass.data.pop(MODULE_DATA)

    return True


# Update config version
async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.info(
        "%s: Migrating configuration from version %s.%s, current config: %s",
        config_entry.title,
        config_entry.version,
        config_entry.minor_version,
        str(config_entry.data),
    )

    if config_entry.version > MagicConfigEntryVersion.MAJOR:
        # This means the user has downgraded from a future version
        _LOGGER.warning(
            "%s: Major version downgrade detection, skipping migration.",
            config_entry.title,
        )

        return False

    hass.config_entries.async_update_entry(
        config_entry,
        minor_version=MagicConfigEntryVersion.MINOR,
        version=MagicConfigEntryVersion.MAJOR,
    )

    _LOGGER.info(
        "Migration to configuration version %s.%s successful: %s",
        config_entry.version,
        config_entry.minor_version,
        str(config_entry.data),
    )

    return True
