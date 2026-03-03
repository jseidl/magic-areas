"""Common code for running the tests."""

import asyncio
from asyncio import get_running_loop
from collections.abc import Sequence
import functools
import logging
import pathlib
from typing import Any, NoReturn
from unittest.mock import Mock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from homeassistant import loader
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_FLOOR_ID, CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    State,
    SupportsResponse,
    callback,
)
from homeassistant.helpers.area_registry import async_get as async_get_ar
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as async_get_er
from homeassistant.helpers.floor_registry import async_get as async_get_fr
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from custom_components.magic_areas.const import (
    CONF_AREA_ID,
    DOMAIN,
    AreaConfigOptions,
    ConfigDomains,
    PresenceTrackingOptions,
)
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions

from tests.const import DEFAULT_MOCK_AREA, MOCK_AREAS, MockAreaIds
from tests.mocks import MockModule, MockPlatform

_LOGGER = logging.getLogger(__name__)

# Integration Setup Helpers


def setup_test_component_platform(
    hass: HomeAssistant,
    domain: str,
    entities: Sequence[Entity],
    from_config_entry: bool = False,
    built_in: bool = True,
) -> MockPlatform:
    """Mock a test component platform for tests."""

    async def _async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up a test component platform."""
        async_add_entities(entities)

    platform = MockPlatform(
        async_setup_platform=_async_setup_platform,
    )

    # avoid creating config entry setup if not needed
    if from_config_entry:

        async def _async_setup_entry(
            hass: HomeAssistant,
            entry: ConfigEntry,
            async_add_entities: AddEntitiesCallback,
        ) -> None:
            """Set up a test component platform."""
            async_add_entities(entities)

        platform.async_setup_entry = _async_setup_entry
        platform.async_setup_platform = None

    mock_platform(hass, f"test.{domain}", platform, built_in=built_in)
    return platform


def mock_integration(
    hass: HomeAssistant, *, module: MockModule, built_in: bool = True
) -> loader.Integration:
    """Mock an integration."""
    integration = loader.Integration(
        hass,
        (
            f"{loader.PACKAGE_BUILTIN}.{module.DOMAIN}"
            if built_in
            else f"{loader.PACKAGE_CUSTOM_COMPONENTS}.{module.DOMAIN}"
        ),
        pathlib.Path(""),
        module.mock_manifest(),
        set(),
    )

    def mock_import_platform(platform_name: str) -> NoReturn:
        raise ImportError(
            f"Mocked unable to import platform '{integration.pkg_path}.{platform_name}'",
            name=f"{integration.pkg_path}.{platform_name}",
        )

    # pylint: disable-next=protected-access
    integration._import_platform = mock_import_platform

    _LOGGER.info("Adding mock integration: %s", module.DOMAIN)
    integration_cache = hass.data[loader.DATA_INTEGRATIONS]
    integration_cache[module.DOMAIN] = integration

    module_cache = hass.data[loader.DATA_COMPONENTS]
    module_cache[module.DOMAIN] = module

    return integration


def mock_platform(
    hass: HomeAssistant,
    platform_path: str,
    module: Mock | MockPlatform | None = None,
    built_in=True,
) -> None:
    """Mock a platform.

    platform_path is in form hue.config_flow.
    """
    domain, _, platform_name = platform_path.partition(".")
    integration_cache = hass.data[loader.DATA_INTEGRATIONS]
    module_cache = hass.data[loader.DATA_COMPONENTS]

    if domain not in integration_cache:
        mock_integration(hass, module=MockModule(domain), built_in=built_in)

    # pylint: disable-next=protected-access
    integration_cache[domain]._top_level_files.add(f"{platform_name}.py")
    _LOGGER.info("Adding mock integration platform: %s", platform_path)
    module_cache[platform_path] = module or Mock()


def async_mock_service(
    *,
    hass: HomeAssistant,
    domain: str,
    service: str,
    schema: vol.Schema | None = None,
    response: ServiceResponse = None,
    supports_response: SupportsResponse | None = None,
    raise_exception: Exception | None = None,
) -> list[ServiceCall]:
    """Set up a fake service & return a calls log list to this service."""
    calls = []

    @callback
    def mock_service_log(call):  # pylint: disable=unnecessary-lambda
        """Mock service call."""
        calls.append(call)
        if raise_exception is not None:
            raise raise_exception
        return response

    if supports_response is None:
        if response is not None:
            supports_response = SupportsResponse.OPTIONAL
        else:
            supports_response = SupportsResponse.NONE

    hass.services.async_register(
        domain,
        service,
        mock_service_log,
        schema=schema,
        supports_response=supports_response,
    )

    return calls


# Test Setup Helpers


async def init_integration(
    hass: HomeAssistant,
    config_entries: list[MockConfigEntry],
    areas: list[MockAreaIds] | None = None,
) -> None:
    """Set up the integration."""

    if not areas:
        areas = [DEFAULT_MOCK_AREA]

    area_registry = async_get_ar(hass)
    floor_registry = async_get_fr(hass)

    # Register areas
    for area in areas:
        area_object = MOCK_AREAS[area]
        floor_id: str | None = None

        if area_object[ATTR_FLOOR_ID]:
            assert area_object[ATTR_FLOOR_ID] is not None
            floor_name = str(area_object[ATTR_FLOOR_ID])
            floor_entry = floor_registry.async_get_floor_by_name(floor_name)
            if not floor_entry:
                floor_entry = floor_registry.async_create(floor_name)
            assert floor_entry is not None
            floor_id = floor_entry.floor_id

        # Check if area already exists before creating
        existing_area = area_registry.async_get_area_by_name(area.value)
        if not existing_area:
            area_registry.async_create(name=area.value, floor_id=floor_id)

    for config_entry in config_entries:
        config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    for config_entry in config_entries:
        assert config_entry.state is ConfigEntryState.LOADED


async def shutdown_integration(
    hass: HomeAssistant, config_entries: list[MockConfigEntry]
) -> None:
    """Teardown the integration."""

    _LOGGER.info("Unloading integration.")
    for config_entry in config_entries:
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)

    for config_entry in config_entries:
        assert config_entry.state is ConfigEntryState.NOT_LOADED
    _LOGGER.info("Integration unloaded.")


async def setup_mock_entities(
    hass: HomeAssistant, domain: str, area_entity_map: dict[MockAreaIds, list[Any]]
) -> None:
    """Set up multiple mock entities at once."""

    all_entities: list[Any] = []
    entity_area_map: dict[Any, MockAreaIds] = {}

    for area_id, entity_list in area_entity_map.items():
        for entity in entity_list:
            all_entities.append(entity)
            entity_area_map[entity.unique_id] = area_id

    # Setup entities
    setup_test_component_platform(hass, domain, all_entities)
    assert await async_setup_component(hass, domain, {domain: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    # Update area IDs
    entity_registry = async_get_er(hass)
    for entity in all_entities:
        assert entity is not None
        assert entity.entity_id is not None
        assert entity.unique_id is not None
        entity_registry.async_update_entity(
            entity.entity_id,
            area_id=entity_area_map[entity.unique_id].value,
        )
    await hass.async_block_till_done()


# Asyncio Virtual Clock


class VirtualClock:
    """Provide a virtual clock for an asyncio event loop.

    This makes timing-based tests deterministic and instantly completed.
    """

    def __init__(self) -> None:
        """Initialize the clock with a simple time."""
        self.vtime = 0.0

    def virtual_time(self) -> float:
        """Return the current virtual time."""
        return self.vtime

    def _virtual_select(self, orig_select, timeout):
        if timeout is not None:
            self.vtime += timeout
        return orig_select(0)  # override the timeout to zero

    def patch_loop(self):
        """Override some methods of the current event loop.

        This is so that sleep instantly returns while proceeding the virtual clock.
        """
        loop = get_running_loop()
        with (
            patch.object(
                loop._selector,  # pylint: disable=protected-access
                "select",
                new=functools.partial(
                    self._virtual_select,
                    loop._selector.select,  # pylint: disable=protected-access
                ),
            ),
            patch.object(
                loop,
                "time",
                new=self.virtual_time,
            ),
            patch.object(
                loop,
                "_clock_resolution",
                new=0.1,
            ),
        ):
            yield


# Helpers


def merge_feature_config(data: dict, *feature_configs: dict) -> None:
    """Merge one or more feature configs into existing data dict.

    Args:
        data: Base config dict with ConfigDomains.FEATURES key
        *feature_configs: One or more dicts from FeatureOptionSet.to_config()

    """

    features_key = ConfigDomains.FEATURES.value

    if features_key not in data:
        data[features_key] = {}

    for feature_config in feature_configs:
        # feature_config is guaranteed to have the features_key from to_config()
        data[features_key].update(feature_config[features_key])


def get_basic_config_entry_data(area_id: MockAreaIds) -> dict[str, Any]:
    """Return config entry data for given area id."""

    area_data = MOCK_AREAS.get(area_id, None)

    assert area_data is not None

    # Build config with nested structure using OptionSet classes
    data = {
        CONF_AREA_ID: area_id.value,
        ConfigDomains.FEATURES: {},
    }

    data.update(
        AreaConfigOptions.to_config(
            {
                AreaConfigOptions.TYPE.key: area_data[AreaConfigOptions.TYPE.key],
                AreaConfigOptions.EXCLUDE_ENTITIES.key: [],
                AreaConfigOptions.INCLUDE_ENTITIES.key: [],
            }
        )
    )

    # Add presence tracking config (nested under "presence_tracking" domain)
    data.update(
        PresenceTrackingOptions.to_config(
            {
                PresenceTrackingOptions.CLEAR_TIMEOUT.key: 0,
                PresenceTrackingOptions.SENSOR_DEVICE_CLASS.key: PresenceTrackingOptions.SENSOR_DEVICE_CLASS.default,
            }
        )
    )

    # Add secondary states config (nested under "secondary_states" domain)
    data.update(
        SecondaryStateOptions.to_config(
            {
                SecondaryStateOptions.EXTENDED_TIMEOUT.key: 5,
            }
        )
    )

    return data


def assert_state(entity_state: State | None, expected_value: str) -> None:
    """Assert that an entity state is a given value."""

    assert entity_state is not None
    assert entity_state.state == expected_value


def assert_attribute(
    entity_state: State | None, attribute_key: str, expected_value: str
) -> None:
    """Assert that an entity attribute is a given value."""

    assert entity_state is not None
    assert hasattr(entity_state, "attributes")
    assert attribute_key in entity_state.attributes
    assert str(entity_state.attributes[attribute_key]) == expected_value


def assert_in_attribute(
    entity_state: State | None,
    attribute_key: str,
    expected_value: str,
    negate: bool = False,
) -> None:
    """Assert that an entity attribute is a given value."""

    assert entity_state is not None
    assert hasattr(entity_state, "attributes")
    assert attribute_key in entity_state.attributes

    if negate:
        assert expected_value not in entity_state.attributes[attribute_key]
    else:
        assert expected_value in entity_state.attributes[attribute_key]


# State Change Helpers


async def safe_set_state(hass: HomeAssistant, sensor, active: bool = True) -> None:
    """Set sensor state and wait for propagation.

    Args:
        hass: Home Assistant instance
        sensor: MockBinarySensor object or entity_id string
        active: True for STATE_ON, False for STATE_OFF

    """

    state = STATE_ON if active else STATE_OFF
    # Handle both MockBinarySensor objects and entity_id strings
    entity_id = sensor.entity_id if hasattr(sensor, "entity_id") else sensor
    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)  # Wait for event propagation


async def trigger_occupancy(
    hass: HomeAssistant, motion_sensor, occupied: bool = True
) -> None:
    """Trigger area occupancy change and wait for propagation.

    Args:
        hass: Home Assistant instance
        motion_sensor: MockBinarySensor object or entity_id string
        occupied: True for occupied (ON), False for clear (OFF)

    """

    await safe_set_state(hass, motion_sensor, occupied)


async def trigger_secondary_state(
    hass: HomeAssistant, sensor, active: bool = True
) -> None:
    """Trigger secondary state (sleep, dark, accent, etc.) and wait for propagation.

    Args:
        hass: Home Assistant instance
        sensor: MockBinarySensor object or entity_id string
        active: True for active (ON), False for inactive (OFF)

    """

    await safe_set_state(hass, sensor, active)


# Timer helper


def immediate_call_factory(hass, callback_key="callback"):
    """Return a side_effect function for patching async_call_later that fires immediately but respects cancel."""

    def immediate_call(hass_arg, delay_arg, callback_arg):
        canceled = False

        def cancel():
            nonlocal canceled
            canceled = True

        async def run_callback():
            if not canceled:
                await callback_arg(utcnow())

        hass.loop.create_task(run_callback())
        return cancel

    return immediate_call
