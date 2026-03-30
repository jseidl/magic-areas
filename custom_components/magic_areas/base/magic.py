"""Classes for Magic Areas and Meta Areas."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import cached_property
import logging

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sun.const import STATE_BELOW_HORIZON
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    EventDeviceRegistryUpdatedData,
    async_get as devicereg_async_get,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity_registry import (
    EventEntityRegistryUpdatedData,
    RegistryEntry,
    async_get as entityreg_async_get,
)
from homeassistant.util import slugify

from custom_components.magic_areas.const import (
    DOMAIN,
    INVALID_STATES,
    MAGIC_AREAS_COMPONENTS,
    MAGIC_AREAS_COMPONENTS_GLOBAL,
    MAGIC_AREAS_COMPONENTS_META,
    MAGIC_DEVICE_ID_PREFIX,
    MAGICAREAS_UNIQUEID_PREFIX,
    META_AREA_GLOBAL,
    AreaConfigOptions,
    AreaStates,
    AreaType,
    ConfigDomains,
    ConfigHelper,
    Features,
    MagicAreasEvents,
    MetaAreaAutoReloadSettings,
    MetaAreaType,
    PresenceTrackingOptions,
)
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions
from custom_components.magic_areas.const.user_defined_states import (
    UserDefinedStateEntryOptions,
    UserDefinedStateOptions,
    slugify_state_name,
)

# Classes


class BasicArea:
    """An interchangeable area object for Magic Areas to consume."""

    id: str
    name: str
    icon: str | None = None
    floor_id: str | None = None
    is_meta: bool = False


class MagicArea:
    """Magic Area class.

    Tracks entities and updates area states and secondary states.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        area: BasicArea,
        config: ConfigEntry,
    ) -> None:
        """Initialize the magic area with all the stuff."""
        self.hass: HomeAssistant = hass
        self.name: str = area.name
        # Default to the icon for the area.
        self.icon: str | None = area.icon
        self.id: str = area.id
        self.slug: str = slugify(self.name)
        self.hass_config: ConfigEntry = config
        self.initialized: bool = False
        self.floor_id: str | None = area.floor_id
        self.logger = logging.getLogger(__name__)

        # Faster lookup lists
        self._area_entities: list[str] = []
        self._area_devices: list[str] = []

        # Timestamp for initialization / reload tests
        self.timestamp: datetime = datetime.now(UTC)

        # Merged options
        area_config = dict(config.data)
        if config.options:
            area_config.update(config.options)
        self.config = ConfigHelper(area_config)

        self.entities: dict[str, list[dict[str, str]]] = {}
        self.magic_entities: dict[str, list[dict[str, str]]] = {}

        self.last_changed: datetime = datetime.now(UTC)

        self.states: list[str] = []

        self.loaded_platforms: list[str] = []

        # Light sensor resolution (set during finalize_init)
        self.area_light_sensor: str | None = None

        self.logger.debug("%s: Primed for initialization.", self.name)

    def finalize_init(self):
        """Finalize initialization of the area."""
        # Resolve light entity before marking as initialized
        self.area_light_sensor = self.resolve_light_entity()

        self.initialized = True
        self.logger.debug(
            "%s (%s) initialized.", self.name, "Meta-Area" if self.is_meta() else "Area"
        )

        @callback
        async def _async_notify_load(*args, **kwargs) -> None:
            """Notify that area is loaded."""
            # Announce area type loaded
            dispatcher_send(
                self.hass,
                MagicAreasEvents.AREA_LOADED,
                self.area_type,
                self.floor_id,
                self.id,
            )

        # Wait for Hass to have started before announcing load events.
        if self.hass.is_running:
            self.hass.create_task(_async_notify_load())
        else:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, _async_notify_load
            )

    def is_occupied(self) -> bool:
        """Return if area is occupied."""
        return self.has_state(AreaStates.OCCUPIED)

    def has_state(self, state) -> bool:
        """Check if area has a given state."""
        return state in self.states

    def has_feature(self, feature) -> bool:
        """Check if area has a given feature."""
        # Get features config from the new structure
        features_config = self.config.get_raw(ConfigDomains.FEATURES, {})

        if not isinstance(features_config, dict):
            self.logger.warning("%s: Invalid configuration for features", self.name)
            return False

        # Feature is enabled if it exists in the config (presence = enabled)
        return feature in features_config

    def available_platforms(self):
        """Return available platforms to area type."""
        available_platforms = []

        if not self.is_meta():
            available_platforms = MAGIC_AREAS_COMPONENTS
        else:
            available_platforms = (
                MAGIC_AREAS_COMPONENTS_GLOBAL
                if self.id == META_AREA_GLOBAL.lower()
                else MAGIC_AREAS_COMPONENTS_META
            )

        return available_platforms

    @property
    def area_type(self):
        """Return the area type."""
        return self.config.get(AreaConfigOptions.TYPE)

    def is_meta(self) -> bool:
        """Return if area is Meta or not."""
        return self.area_type == AreaType.META

    def is_interior(self):
        """Return if area type is interior or not."""
        return self.area_type == AreaType.INTERIOR

    def is_exterior(self):
        """Return if area type is exterior or not."""
        return self.area_type == AreaType.EXTERIOR

    def _is_magic_area_entity(self, entity: RegistryEntry) -> bool:
        """Return if entity belongs to this integration instance."""
        return entity.config_entry_id == self.hass_config.entry_id

    def _should_exclude_entity(self, entity: RegistryEntry) -> bool:
        """Exclude entity."""

        # Is magic_area entity?
        if entity.config_entry_id == self.hass_config.entry_id:
            return True

        # Is disabled?
        if entity.disabled:
            return True

        # Is in the exclusion list?
        if entity.entity_id in self.config.get(AreaConfigOptions.EXCLUDE_ENTITIES):
            return True

        # Are we excluding DIAGNOSTIC and CONFIG?
        if self.config.get(AreaConfigOptions.IGNORE_DIAGNOSTIC_ENTITIES):
            if entity.entity_category in [
                EntityCategory.CONFIG,
                EntityCategory.DIAGNOSTIC,
            ]:
                return True

        return False

    async def load_entities(self) -> None:
        """Load entities into entity list."""

        entity_list: list[RegistryEntry] = []
        include_entities = self.config.get(AreaConfigOptions.INCLUDE_ENTITIES)

        entity_registry = entityreg_async_get(self.hass)
        device_registry = devicereg_async_get(self.hass)

        # Add entities from devices in this area
        devices_in_area = device_registry.devices.get_devices_for_area_id(self.id)
        for device in devices_in_area:
            entity_list.extend(
                [
                    entity
                    for entity in entity_registry.entities.get_entries_for_device_id(
                        device.id
                    )
                    if not self._should_exclude_entity(entity)
                ]
            )
            self._area_devices.append(device.id)

        # Add entities that are specifically set as this area but device is not or has no device.
        entities_in_area = entity_registry.entities.get_entries_for_area_id(self.id)
        entity_list.extend(
            [
                entity
                for entity in entities_in_area
                if entity.entity_id not in entity_list
                and not self._should_exclude_entity(entity)
            ]
        )

        if include_entities and isinstance(include_entities, list):
            for include_entity in include_entities:
                entity_entry = entity_registry.async_get(include_entity)
                if entity_entry:
                    entity_list.append(entity_entry)

        self.load_entity_list(entity_list)

        self.logger.debug(
            "%s: Found area entities: %s",
            self.name,
            str(self.entities),
        )

    def load_magic_entities(self):
        """Load magic areas-generated entities."""

        entity_registry = entityreg_async_get(self.hass)

        # Add magic are entities
        entities_for_config_id = (
            entity_registry.entities.get_entries_for_config_entry_id(
                self.hass_config.entry_id
            )
        )

        for entity_id in [entity.entity_id for entity in entities_for_config_id]:
            entity_domain = entity_id.split(".")[0]

            if entity_domain not in self.magic_entities:
                self.magic_entities[entity_domain] = []

            self.magic_entities[entity_domain].append(self.get_entity_dict(entity_id))

        self.logger.debug(
            "%s: Loaded magic entities: %s", self.name, str(self.magic_entities)
        )

    def get_entity_dict(self, entity_id) -> dict[str, str]:
        """Return entity_id in a dictionary with attributes (if available)."""

        # Get latest state and create object
        latest_state = self.hass.states.get(entity_id)
        entity_dict = {ATTR_ENTITY_ID: entity_id}

        if latest_state:
            # Need to exclude entity_id if present but latest_state.attributes
            # is a ReadOnlyDict so we can't remove it, need to iterate and select
            # all keys that are NOT entity_id
            for attr_key, attr_value in latest_state.attributes.items():
                if attr_key != ATTR_ENTITY_ID:
                    entity_dict[attr_key] = attr_value

        return entity_dict

    def load_entity_list(self, entity_list: list[RegistryEntry]) -> None:
        """Populate entity list with loaded entities."""
        self.logger.debug("%s: Original entity list: %s", self.name, str(entity_list))

        for entity in entity_list:
            if entity.entity_id in self._area_entities:
                continue
            self.logger.debug("%s: Loading entity: %s", self.name, entity.entity_id)

            try:
                updated_entity = self.get_entity_dict(entity.entity_id)

                if not entity.domain:
                    self.logger.warning(
                        "%s: Entity domain not found for %s", self.name, entity
                    )
                    continue
                if entity.domain not in self.entities:
                    self.entities[entity.domain] = []

                self.entities[entity.domain].append(updated_entity)

                self._area_entities.append(entity.entity_id)

            # Adding pylint exception because this is a last-resort hail-mary catch-all
            # pylint: disable-next=broad-exception-caught
            except Exception as err:
                self.logger.error(
                    "%s: Unable to load entity '%s': %s",
                    self.name,
                    entity,
                    str(err),
                )

        # Load our own entities
        self.load_magic_entities()

    def get_presence_sensors(self) -> list[str]:
        """Return list of entities used for presence tracking."""

        sensors: list[str] = []

        valid_presence_platforms = self.config.get(
            PresenceTrackingOptions.DEVICE_PLATFORMS
        )

        for component, entities in self.entities.items():
            if component not in valid_presence_platforms:
                continue

            for entity in entities:
                if not entity:
                    continue

                if component == BINARY_SENSOR_DOMAIN:
                    if ATTR_DEVICE_CLASS not in entity:
                        continue

                    if entity[ATTR_DEVICE_CLASS] not in self.config.get(
                        PresenceTrackingOptions.SENSOR_DEVICE_CLASS
                    ):
                        continue

                sensors.append(entity[ATTR_ENTITY_ID])

        # Append presence_hold switch as a presence_sensor
        if self.has_feature(Features.PRESENCE_HOLD):
            presence_hold_switch_id = (
                f"{SWITCH_DOMAIN}.magic_areas_presence_hold_{self.slug}"
            )
            sensors.append(presence_hold_switch_id)

        # Append BLE Tracker monitor as a presence_sensor
        if self.has_feature(Features.BLE_TRACKERS):
            ble_tracker_sensor_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_ble_trackers_{self.slug}_ble_tracker_monitor"
            sensors.append(ble_tracker_sensor_id)

        # Append Wasp In The Box sensor as presence monitor
        if self.has_feature(Features.AGGREGATION) and self.has_feature(
            Features.WASP_IN_A_BOX
        ):
            wasp_in_the_box_sensor_id = (
                f"{BINARY_SENSOR_DOMAIN}.magic_areas_wasp_in_a_box_{self.slug}"
            )
            sensors.append(wasp_in_the_box_sensor_id)

        return sensors

    async def initialize(self, _=None) -> None:
        """Initialize area."""
        self.logger.debug("%s: Initializing area...", self.name)

        await self.load_entities()

        self.finalize_init()

    def has_entities(self, domain):
        """Check if area has entities."""
        return domain in self.entities

    def make_entity_registry_filter(self):
        """Create entity register filter for this area."""

        @callback
        def _entity_registry_filter(event_data: EventEntityRegistryUpdatedData) -> bool:
            """Filter entity registry events relevant to this area."""

            entity_id = event_data["entity_id"]

            # Ignore our own stuff
            _, entity_part = entity_id.split(".")
            if entity_part.startswith(MAGICAREAS_UNIQUEID_PREFIX):
                return False

            # Ignore if too soon after area initialization
            if datetime.now(UTC) - self.timestamp < timedelta(
                seconds=MetaAreaAutoReloadSettings.DELAY
            ):
                return False

            action = event_data["action"]
            entity_registry = entityreg_async_get(self.hass)
            entity_entry = entity_registry.async_get(entity_id)

            if (
                action == "update"
                and "changes" in event_data
                and "area_id" in event_data["changes"]
            ):
                # Removed from our area
                if event_data["changes"]["area_id"] == self.id:
                    return True

                # Is from our area
                if entity_entry and entity_entry.area_id == self.id:
                    return True

                return False

            if action in ("create", "remove"):
                # Is from our area
                if entity_entry and entity_entry.area_id == self.id:
                    return True

            return False

        return _entity_registry_filter

    def resolve_light_entity(self) -> str | None:
        """Resolve which entity to use for darkness detection.

        Resolution order:
        1. Area's threshold sensor (if conditions warrant creation)
        2. Area's light aggregate (if conditions warrant creation)
        3. Windowless check (return None if true)
        4. Exterior meta-area threshold sensor (if available)
        5. Exterior meta-area light aggregate (if available)
        6. sun.sun fallback

        Returns:
            Entity ID to monitor (binary sensor or sun.sun), or None for windowless

        """
        # Import here to avoid circular dependency
        from custom_components.magic_areas.helpers.aggregates import (  # pylint: disable=import-outside-toplevel
            should_create_light_aggregate,
            should_create_threshold_sensor,
        )

        # 1. Check if threshold sensor should be created for this area
        if should_create_threshold_sensor(self):
            threshold_entity = f"{BINARY_SENSOR_DOMAIN}.magic_areas_threshold_{self.slug}_threshold_light"
            self.logger.debug(
                "%s: Will use threshold sensor for dark detection: %s",
                self.name,
                threshold_entity,
            )
            return threshold_entity

        # 2. Check if light aggregate should be created for this area
        if should_create_light_aggregate(self):
            light_aggregate = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_{self.slug}_aggregate_light"
            self.logger.debug(
                "%s: Will use light aggregate for dark detection: %s",
                self.name,
                light_aggregate,
            )
            return light_aggregate

        # 3. Check windowless flag
        if self.config.get(AreaConfigOptions.WINDOWLESS):
            self.logger.debug("%s: Windowless area - always dark", self.name)
            return None  # Always dark

        # 4. Check exterior meta-area
        exterior_area = self._get_exterior_meta_area()
        if exterior_area:
            # Try exterior threshold sensor
            if should_create_threshold_sensor(exterior_area):
                ext_threshold = f"{BINARY_SENSOR_DOMAIN}.magic_areas_threshold_exterior_threshold_light"
                self.logger.debug(
                    "%s: Will use exterior threshold sensor for dark detection: %s",
                    self.name,
                    ext_threshold,
                )
                return ext_threshold

            # Fall back to exterior light aggregate
            if should_create_light_aggregate(exterior_area):
                ext_light_aggregate = f"{BINARY_SENSOR_DOMAIN}.magic_areas_aggregates_exterior_aggregate_light"
                self.logger.debug(
                    "%s: Will use exterior light aggregate for dark detection: %s",
                    self.name,
                    ext_light_aggregate,
                )
                return ext_light_aggregate

        # 6. Final fallback: sun.sun (if available)
        sun_entity = self.hass.states.get("sun.sun")
        if sun_entity:
            self.logger.debug("%s: Using sun.sun for dark detection", self.name)
            return "sun.sun"

        # No light sensor available - will always be dark
        self.logger.debug(
            "%s: No light sensor available - will always be dark", self.name
        )
        return None

    def _iter_magic_areas(self):
        """Yield MagicArea instances for all loaded config entries."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
                yield entry.runtime_data

    def _get_exterior_meta_area(self) -> "MagicArea | None":
        """Get the exterior meta-area if it exists."""
        for area in self._iter_magic_areas():
            if area.id == MetaAreaType.EXTERIOR:
                return area
        return None

    def is_area_dark(self) -> bool:
        """Check if area is currently dark based on resolved light sensor.

        Returns:
            True if area is dark, False if bright

        """
        # Special case: windowless = no light entity = always dark
        if not hasattr(self, "area_light_sensor") or self.area_light_sensor is None:
            return True

        # Get entity state
        entity = self.hass.states.get(self.area_light_sensor)
        if not entity or entity.state in INVALID_STATES:
            self.logger.debug(
                "%s: Light sensor '%s' unavailable, assuming dark",
                self.name,
                self.area_light_sensor,
            )
            return True  # Assume dark if unavailable

        # Check state (handles both binary sensors OFF and sun.sun below_horizon)
        is_dark = entity.state.lower() in [STATE_OFF, STATE_BELOW_HORIZON]

        self.logger.debug(
            "%s: Light sensor '%s' state: %s -> dark=%s",
            self.name,
            self.area_light_sensor,
            entity.state,
            is_dark,
        )

        return is_dark

    @cached_property
    def secondary_state_entities(self) -> dict[str, str]:
        """Get map of state_name -> entity_id for secondary states.

        Returns map of configurable secondary states (sleep + user-defined):
            {
                "sleep": "binary_sensor.sleep_mode",
                "movie": "input_boolean.movie_mode",
                "gaming": "switch.gaming_mode",
            }

        Cached for the lifetime of this MagicArea instance.
        Automatically cleared on config reload (new instance created).

        """

        entities = {}

        # Add sleep state if configured
        sleep_entity = self.config.get(SecondaryStateOptions.SLEEP_ENTITY)
        if sleep_entity:
            entities["sleep"] = sleep_entity

        # Add user-defined states
        user_defined_states = self.config.get(UserDefinedStateOptions.STATES)
        for state_entry in user_defined_states:
            state_name = state_entry.get(UserDefinedStateEntryOptions.NAME.key)
            entity_id = state_entry.get(UserDefinedStateEntryOptions.ENTITY.key)
            if state_name and entity_id:
                entities[slugify_state_name(state_name)] = entity_id

        return entities

    def make_device_registry_filter(self):
        """Create device register filter for this area."""

        @callback
        def _device_registry_filter(event_data: EventDeviceRegistryUpdatedData) -> bool:
            """Filter device registry events relevant to this area."""

            # Ignore our own stuff
            if event_data["device_id"].startswith(MAGIC_DEVICE_ID_PREFIX):
                return False

            # Ignore if too soon after area initialization
            if datetime.now(UTC) - self.timestamp < timedelta(
                seconds=MetaAreaAutoReloadSettings.DELAY
            ):
                return False

            action = event_data["action"]

            if (
                action == "update"
                and "changes" in event_data
                and "area_id" in event_data["changes"]
            ):
                # Removed from our area
                if event_data["changes"]["area_id"] == self.id:
                    return True

            # Was from our area?
            if event_data["device_id"] in self._area_devices:
                return True

            device_registry = devicereg_async_get(self.hass)
            device_entry = device_registry.async_get(event_data["device_id"])

            # Is from our area
            if device_entry and device_entry.area_id == self.id:
                return True

            return False

        return _device_registry_filter


class MagicMetaArea(MagicArea):
    """Magic Meta Area class."""

    def __init__(
        self,
        hass: HomeAssistant,
        area: BasicArea,
        config: ConfigEntry,
    ) -> None:
        """Initialize the meta magic area with all the stuff."""
        super().__init__(hass, area, config)
        self.child_areas: list[str] = self.get_child_areas()
        # Pending debounced reload task
        self._reload_task: asyncio.Task | None = None

    def get_presence_sensors(self) -> list[str]:
        """Return list of entities used for presence tracking."""

        sensors: list[str] = []

        # MetaAreas track their children
        for child_area in self.child_areas:
            entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{child_area}_area_state"
            sensors.append(entity_id)
        return sensors

    def get_active_areas(self):
        """Return areas that are occupied."""

        active_areas = []

        for area in self.child_areas:
            try:
                entity_id = f"binary_sensor.area_{area}"
                entity = self.hass.states.get(entity_id)

                if not entity:
                    self.logger.debug("%s: Unable to get area state entity.", area)
                    continue

                if entity.state == STATE_ON:
                    active_areas.append(area)

            # Adding pylint exception because this is a last-resort hail-mary catch-all
            # pylint: disable-next=broad-exception-caught
            except Exception as e:
                self.logger.error(
                    "%s: Unable to get active area state: %s", area, str(e)
                )

        return active_areas

    def get_child_areas(self):
        """Return areas that a Meta area is watching."""
        areas: list[str] = []

        for area in self._iter_magic_areas():
            if area.is_meta():
                continue

            if self.floor_id:
                if self.floor_id == area.floor_id:
                    areas.append(area.slug)
            else:
                if (
                    self.id == MetaAreaType.GLOBAL
                    or area.config.get(AreaConfigOptions.TYPE) == self.id
                ):
                    areas.append(area.slug)

        return areas

    async def initialize(self, _=None) -> None:
        """Initialize Meta area."""
        if self.initialized:
            self.logger.debug("%s: Already initialized, ignoring.", self.name)
            return None

        self.logger.debug("%s: Initializing meta area...", self.name)

        await self.load_entities()

        self.finalize_init()

    async def load_entities(self) -> None:
        """Load entities into entity list."""

        entity_registry = entityreg_async_get(self.hass)
        entity_list: list[RegistryEntry] = []

        for area in self._iter_magic_areas():
            if area.slug not in self.child_areas:
                continue

            # Force loading of magic entities
            area.load_magic_entities()

            for entities in area.magic_entities.values():
                for entity in entities:
                    if not isinstance(entity[ATTR_ENTITY_ID], str):
                        self.logger.debug(
                            "%s: Entity ID is not a string: '%s' (probably a group, skipping)",
                            self.name,
                            str(entity[ATTR_ENTITY_ID]),
                        )
                        continue

                    # Skip excluded entities
                    if entity[ATTR_ENTITY_ID] in self.config.get(
                        AreaConfigOptions.EXCLUDE_ENTITIES
                    ):
                        continue

                    entity_entry = entity_registry.async_get(entity[ATTR_ENTITY_ID])
                    if not entity_entry:
                        self.logger.debug(
                            "%s: Magic Entity not found on Entity Registry: %s",
                            self.name,
                            entity[ATTR_ENTITY_ID],
                        )
                        continue
                    entity_list.append(entity_entry)

        self.load_entity_list(entity_list)

        self.logger.debug(
            "%s: Loaded entities for meta area: %s", self.name, str(self.entities)
        )

    def finalize_init(self) -> None:
        """Finalize Meta-Area initialization."""
        disconnect: Callable = async_dispatcher_connect(
            self.hass, MagicAreasEvents.AREA_LOADED, self._handle_loaded_area
        )
        # Automatically clean up the dispatcher listener and any pending reload
        # task when this config entry is unloaded, preventing orphaned listeners
        # and instances across meta-area reloads.
        self.hass_config.async_on_unload(disconnect)
        self.hass_config.async_on_unload(self._cancel_reload_task)

    def _cancel_reload_task(self) -> None:
        """Cancel any pending debounced reload task."""
        if self._reload_task and not self._reload_task.done():
            self._reload_task.cancel()
        self._reload_task = None

    def _should_reload_for(self, area_type: str, area_id: str) -> bool:
        """Return True if this meta-area should reload for the given signal."""
        if self.slug == MetaAreaType.GLOBAL:
            return True
        return area_type == self.slug or area_id in self.child_areas

    async def _handle_loaded_area(
        self, area_type: str, floor_id: int | None, area_id: str
    ) -> None:
        """Handle area loaded signals with debouncing."""
        self.logger.debug(
            "%s: Received area loaded signal (type=%s, floor_id=%s, area_id=%s)",
            self.name,
            area_type,
            floor_id,
            area_id,
        )

        if not self.hass.is_running:
            return

        if not self._should_reload_for(area_type, area_id):
            return

        # Debounce: cancel any pending reload and reschedule.
        # This ensures that a burst of AREA_LOADED signals (e.g., at startup
        # or when multiple areas reload at once) collapses into a single reload
        # that fires after the last signal settles.
        self._cancel_reload_task()
        self._reload_task = self.hass.async_create_task(
            self._delayed_reload(),
            name=f"magic_areas_meta_reload_{self.slug}",
        )

    async def _delayed_reload(self) -> None:
        """Reload after a short delay, batching rapid AREA_LOADED signals.

        Global uses a longer delay so that floor/interior/exterior meta-areas
        reload first and emit their own AREA_LOADED signals before global picks
        them up.
        """
        delay: int = (
            MetaAreaAutoReloadSettings.GLOBAL_DELAY
            if self.slug == MetaAreaType.GLOBAL
            else MetaAreaAutoReloadSettings.DELAY
        )
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            self.logger.debug(
                "%s: Reload debounced (superseded by a newer signal).", self.name
            )
            return

        self.logger.info("%s: Reloading entry.", self.name)
        self.hass.config_entries.async_schedule_reload(self.hass_config.entry_id)
