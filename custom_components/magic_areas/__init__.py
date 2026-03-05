"""Magic Areas component for Home Assistant."""

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
    CONF_AREA_ID,
    AreaConfigOptions,
    ConfigDomains,
    MagicConfigEntryVersion,
    PresenceTrackingOptions,
)
from custom_components.magic_areas.const.light_groups import (
    LightGroupEntryOptions,
    LightGroupOptions,
    LightGroupTurnOffWhen,
    LightGroupTurnOnWhen,
)
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions
from custom_components.magic_areas.const.user_defined_states import (
    UserDefinedStateEntryOptions,
    UserDefinedStateOptions,
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

        # Register cleanup callbacks — HA calls these automatically on unload.
        config_entry.async_on_unload(
            config_entry.add_update_listener(async_update_options)
        )

        # Watch for area changes.
        if not magic_area.is_meta():
            config_entry.async_on_unload(
                hass.bus.async_listen(
                    EVENT_ENTITY_REGISTRY_UPDATED,
                    _async_registry_updated,
                    magic_area.make_entity_registry_filter(),
                )
            )
            config_entry.async_on_unload(
                hass.bus.async_listen(
                    EVENT_DEVICE_REGISTRY_UPDATED,
                    _async_registry_updated,
                    magic_area.make_device_registry_filter(),
                )
            )
            # Reload once Home Assistant has finished starting to make sure we have all entities.
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_reload_entry)

        # Store the MagicArea instance as runtime data on the config entry.
        config_entry.runtime_data = magic_area

        # Setup platforms
        await hass.config_entries.async_forward_entry_setups(
            config_entry, magic_area.available_platforms()
        )

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
    area: MagicArea = config_entry.runtime_data
    return await hass.config_entries.async_unload_platforms(
        config_entry, area.available_platforms()
    )


# ============================================================================
# Config Migration Helpers
# ============================================================================

# Old light group category slugs → human-readable display names
_LIGHT_GROUP_CATEGORIES = [
    ("overhead", "Overhead Lights"),
    ("task", "Task Lights"),
    ("sleep", "Sleep Lights"),
    ("accent", "Accent Lights"),
]


def _migrate_light_groups(old_lg_config: dict) -> dict:
    """Migrate old fixed-category light groups config to new flexible groups list.

    Old format used flat keys per category:
        overhead_lights, overhead_lights_states, overhead_lights_act_on, ...
    New format is a list of group dicts under the 'groups' key.
    """
    groups = []

    for category_slug, category_name in _LIGHT_GROUP_CATEGORIES:
        lights = old_lg_config.get(f"{category_slug}_lights", [])

        # Only create a group entry if there are actual lights assigned
        if not lights:
            continue

        states = old_lg_config.get(f"{category_slug}_lights_states", [])
        act_on = old_lg_config.get(f"{category_slug}_lights_act_on", [])

        turn_on_when: list[str] = []
        turn_off_when: list[str] = []

        if "occupancy" in act_on:
            turn_on_when.append(LightGroupTurnOnWhen.AREA_OCCUPIED.value)
            turn_off_when.append(LightGroupTurnOffWhen.AREA_CLEAR.value)

        if "state" in act_on:
            turn_on_when.append(LightGroupTurnOnWhen.STATE_GAIN.value)
            turn_on_when.append(LightGroupTurnOnWhen.AREA_DARK.value)
            turn_off_when.append(LightGroupTurnOffWhen.STATE_LOSS.value)

        groups.append(
            {
                LightGroupEntryOptions.NAME.key: category_name,
                LightGroupEntryOptions.LIGHTS.key: lights,
                LightGroupEntryOptions.STATES.key: states,
                LightGroupEntryOptions.TURN_ON_WHEN.key: turn_on_when,
                LightGroupEntryOptions.TURN_OFF_WHEN.key: turn_off_when,
                LightGroupEntryOptions.REQUIRE_DARK.key: True,
            }
        )

    return {LightGroupOptions.GROUPS.key: groups}


def _migrate_v2_1_to_v2_2(config_entry: ConfigEntry) -> dict:
    """Build a new domain-based options dict from a v2.1 flat config entry.

    Merges data + options (options wins) then restructures into:
      area / presence_tracking / secondary_states / user_defined_states / features
    """
    # Merge data and options; options takes precedence over initial data
    old: dict[str, Any] = {**config_entry.data, **config_entry.options}

    new_options: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # area domain
    # ------------------------------------------------------------------
    new_options[ConfigDomains.AREA] = {
        AreaConfigOptions.TYPE.key: old.get(
            AreaConfigOptions.TYPE.key, AreaConfigOptions.TYPE.default
        ),
        AreaConfigOptions.INCLUDE_ENTITIES.key: old.get(
            AreaConfigOptions.INCLUDE_ENTITIES.key,
            AreaConfigOptions.INCLUDE_ENTITIES.default,
        ),
        AreaConfigOptions.EXCLUDE_ENTITIES.key: old.get(
            AreaConfigOptions.EXCLUDE_ENTITIES.key,
            AreaConfigOptions.EXCLUDE_ENTITIES.default,
        ),
        AreaConfigOptions.RELOAD_ON_REGISTRY_CHANGE.key: old.get(
            AreaConfigOptions.RELOAD_ON_REGISTRY_CHANGE.key,
            AreaConfigOptions.RELOAD_ON_REGISTRY_CHANGE.default,
        ),
        AreaConfigOptions.IGNORE_DIAGNOSTIC_ENTITIES.key: old.get(
            AreaConfigOptions.IGNORE_DIAGNOSTIC_ENTITIES.key,
            AreaConfigOptions.IGNORE_DIAGNOSTIC_ENTITIES.default,
        ),
        # New field with no old equivalent — default to False
        AreaConfigOptions.WINDOWLESS.key: AreaConfigOptions.WINDOWLESS.default,
    }

    # ------------------------------------------------------------------
    # presence_tracking domain
    # ------------------------------------------------------------------
    new_options[ConfigDomains.PRESENCE] = {
        PresenceTrackingOptions.CLEAR_TIMEOUT.key: old.get(
            PresenceTrackingOptions.CLEAR_TIMEOUT.key,
            PresenceTrackingOptions.CLEAR_TIMEOUT.default,
        ),
        PresenceTrackingOptions.KEEP_ONLY_ENTITIES.key: old.get(
            PresenceTrackingOptions.KEEP_ONLY_ENTITIES.key,
            PresenceTrackingOptions.KEEP_ONLY_ENTITIES.default,
        ),
        PresenceTrackingOptions.DEVICE_PLATFORMS.key: old.get(
            PresenceTrackingOptions.DEVICE_PLATFORMS.key,
            PresenceTrackingOptions.DEVICE_PLATFORMS.default,
        ),
        PresenceTrackingOptions.SENSOR_DEVICE_CLASS.key: old.get(
            PresenceTrackingOptions.SENSOR_DEVICE_CLASS.key,
            PresenceTrackingOptions.SENSOR_DEVICE_CLASS.default,
        ),
    }

    # ------------------------------------------------------------------
    # secondary_states domain  (drop dark_entity / accent_entity)
    # ------------------------------------------------------------------
    old_secondary: dict[str, Any] = old.get(ConfigDomains.SECONDARY_STATES, {})

    new_secondary: dict[str, Any] = {}
    for opt in (
        SecondaryStateOptions.SLEEP_ENTITY,
        SecondaryStateOptions.SLEEP_TIMEOUT,
        SecondaryStateOptions.EXTENDED_TIME,
        SecondaryStateOptions.EXTENDED_TIMEOUT,
    ):
        new_secondary[opt.key] = old_secondary.get(opt.key, opt.default)

    # calculation_mode is only present on meta-areas
    if SecondaryStateOptions.CALCULATION_MODE.key in old_secondary:
        new_secondary[SecondaryStateOptions.CALCULATION_MODE.key] = old_secondary[
            SecondaryStateOptions.CALCULATION_MODE.key
        ]

    new_options[ConfigDomains.SECONDARY_STATES] = new_secondary

    # ------------------------------------------------------------------
    # user_defined_states domain
    # Migrate accent_entity → a user-defined state named "Accent"
    # ------------------------------------------------------------------
    user_defined_states: list[dict] = []
    accent_entity: str = old_secondary.get("accent_entity", "")
    if accent_entity:
        user_defined_states.append(
            {
                UserDefinedStateEntryOptions.NAME.key: "Accent",
                UserDefinedStateEntryOptions.ENTITY.key: accent_entity,
            }
        )

    new_options[ConfigDomains.USER_DEFINED_STATES] = {
        UserDefinedStateOptions.STATES.key: user_defined_states
    }

    # ------------------------------------------------------------------
    # features domain
    # ------------------------------------------------------------------
    old_features: dict[str, Any] = old.get(ConfigDomains.FEATURES, {})
    new_features: dict[str, Any] = {}

    for feature_key, feature_config in old_features.items():
        if feature_key == "light_groups":
            new_features[feature_key] = _migrate_light_groups(feature_config)
        else:
            # All other feature configs (aggregates, health, wasp_in_a_box, …)
            # are copied verbatim — their internal keys did not change.
            new_features[feature_key] = feature_config

    new_options[ConfigDomains.FEATURES] = new_features

    return new_options


# ============================================================================
# Entry migration
# ============================================================================


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entries to the current version."""
    _LOGGER.info(
        "%s: Check for configuration migration for version %s.%s",
        config_entry.title,
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > MagicConfigEntryVersion.MAJOR:
        # User has downgraded from a future version — cannot migrate forward
        _LOGGER.warning(
            "%s: Major version downgrade detected, skipping migration.",
            config_entry.title,
        )
        return False

    if config_entry.version == 2 and config_entry.minor_version == 1:
        _LOGGER.info(
            "%s: Migrating from v2.1 (flat) to v2.2 (domain-based) config",
            config_entry.title,
        )

        new_options = _migrate_v2_1_to_v2_2(config_entry)

        # Strip data down to the bare area identifier only
        area_id: str = (
            config_entry.data.get(CONF_AREA_ID) or config_entry.unique_id or ""
        )

        hass.config_entries.async_update_entry(
            config_entry,
            data={CONF_AREA_ID: area_id},
            options=new_options,
            version=MagicConfigEntryVersion.MAJOR,
            minor_version=MagicConfigEntryVersion.MINOR,
        )

        _LOGGER.info(
            "%s: Migration to v%s.%s complete",
            config_entry.title,
            MagicConfigEntryVersion.MAJOR,
            MagicConfigEntryVersion.MINOR,
        )
        return True

    # No migration needed for this version combination; just stamp the version
    hass.config_entries.async_update_entry(
        config_entry,
        version=MagicConfigEntryVersion.MAJOR,
        minor_version=MagicConfigEntryVersion.MINOR,
    )
    return True
