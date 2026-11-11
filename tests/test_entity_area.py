"""Tests for resolving an entity's area: its own area overrides its device's."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.sensor.const import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.const import ATTR_ENTITY_ID, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import DOMAIN, MetaAreaAutoReloadSettings
from custom_components.magic_areas.const.aggregates import AggregateOptions

from tests.const import MockAreaIds
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockSensor

DEVICE_AREA = MockAreaIds.KITCHEN
ENTITY_AREA = MockAreaIds.LIVING_ROOM

# Modelled on a weather station gateway: one device, sitting in DEVICE_AREA,
# exposing both outdoor sensors (inheriting the device's area) and its own
# indoor sensors (assigned to the room the gateway is actually in).
INHERITED_SENSOR = f"{SENSOR_DOMAIN}.gateway_outdoor_temperature"
OVERRIDDEN_SENSOR = f"{SENSOR_DOMAIN}.gateway_indoor_temperature"


def _temperature_sensor(name: str) -> MockSensor:
    return MockSensor(
        name=name,
        unique_id=name,
        native_value=20,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        extra_state_attributes={"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )


def _area_config_entry(area: MockAreaIds) -> MockConfigEntry:
    data = get_basic_config_entry_data(area)
    merge_feature_config(
        data,
        AggregateOptions.to_config(
            {
                AggregateOptions.MIN_ENTITIES.key: 1,
                AggregateOptions.SENSOR_DEVICE_CLASSES.key: [
                    SensorDeviceClass.TEMPERATURE.value
                ],
            }
        ),
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


def _magic_area(hass: HomeAssistant, config_entry: MockConfigEntry) -> MagicArea:
    area = config_entry.runtime_data
    assert isinstance(area, MagicArea)
    return area


def _area_sensor_ids(hass: HomeAssistant, config_entry: MockConfigEntry) -> list[str]:
    area = _magic_area(hass, config_entry)
    return [entity[ATTR_ENTITY_ID] for entity in area.entities.get(SENSOR_DOMAIN, [])]


@pytest.fixture(name="gateway_sensors")
async def setup_gateway_sensors(hass: HomeAssistant) -> None:
    """Create two sensors on one device in DEVICE_AREA, one overriding its area."""

    await setup_mock_entities(
        hass,
        SENSOR_DOMAIN,
        {
            DEVICE_AREA: [
                _temperature_sensor("gateway_outdoor_temperature"),
                _temperature_sensor("gateway_indoor_temperature"),
            ]
        },
    )

    device_config_entry = MockConfigEntry(domain="test")
    device_config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=device_config_entry.entry_id,
        identifiers={("test", "gateway")},
        name="Gateway",
    )
    device_registry.async_update_device(device.id, area_id=DEVICE_AREA.value)

    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(
        INHERITED_SENSOR, device_id=device.id, area_id=None
    )
    entity_registry.async_update_entity(
        OVERRIDDEN_SENSOR, device_id=device.id, area_id=ENTITY_AREA.value
    )
    await hass.async_block_till_done()


@pytest.fixture(name="area_config_entries")
async def setup_area_config_entries(
    hass: HomeAssistant, gateway_sensors: None
) -> AsyncGenerator[dict[MockAreaIds, MockConfigEntry]]:
    """Set up Magic Areas for DEVICE_AREA and ENTITY_AREA."""

    config_entries = {
        DEVICE_AREA: _area_config_entry(DEVICE_AREA),
        ENTITY_AREA: _area_config_entry(ENTITY_AREA),
    }
    await init_integration(
        hass, list(config_entries.values()), areas=list(config_entries)
    )
    yield config_entries
    await shutdown_integration(hass, list(config_entries.values()))


async def test_entity_area_overrides_device_area(
    hass: HomeAssistant,
    area_config_entries: dict[MockAreaIds, MockConfigEntry],
) -> None:
    """An entity with its own area belongs to that area only, not its device's."""

    device_area_sensors = _area_sensor_ids(hass, area_config_entries[DEVICE_AREA])
    entity_area_sensors = _area_sensor_ids(hass, area_config_entries[ENTITY_AREA])

    assert INHERITED_SENSOR in device_area_sensors
    assert OVERRIDDEN_SENSOR not in device_area_sensors

    assert OVERRIDDEN_SENSOR in entity_area_sensors
    assert INHERITED_SENSOR not in entity_area_sensors


async def test_entity_area_override_excluded_from_device_area_aggregates(
    hass: HomeAssistant,
    area_config_entries: dict[MockAreaIds, MockConfigEntry],
) -> None:
    """Aggregates only include the entities that are in the area."""

    def _members(area: MockAreaIds) -> list[str]:
        state = hass.states.get(
            f"{SENSOR_DOMAIN}.magic_areas_aggregates_{area.value}_aggregate_temperature"
        )
        assert state is not None
        return state.attributes[ATTR_ENTITY_ID]

    assert _members(DEVICE_AREA) == [INHERITED_SENSOR]
    assert _members(ENTITY_AREA) == [OVERRIDDEN_SENSOR]


async def test_entity_area_changes_reload_affected_areas(
    hass: HomeAssistant,
    area_config_entries: dict[MockAreaIds, MockConfigEntry],
) -> None:
    """Overriding or clearing an entity's area reloads its device's area too."""

    entity_registry = er.async_get(hass)
    device_area = _magic_area(hass, area_config_entries[DEVICE_AREA])
    entity_area = _magic_area(hass, area_config_entries[ENTITY_AREA])

    def _filters_accept(old_area_id: str | None) -> tuple[bool, bool]:
        # The filters ignore events shortly after an area loads.
        past = datetime.now(UTC) - timedelta(
            seconds=MetaAreaAutoReloadSettings.DELAY + 1
        )
        device_area.timestamp = past
        entity_area.timestamp = past
        event_data: Any = {
            "action": "update",
            "entity_id": INHERITED_SENSOR,
            "changes": {"area_id": old_area_id},
        }
        return (
            device_area.make_entity_registry_filter()(event_data),
            entity_area.make_entity_registry_filter()(event_data),
        )

    # Give the inheriting sensor an area of its own: both the area it stops
    # inheriting and the area it moves into must reload.
    entity_registry.async_update_entity(INHERITED_SENSOR, area_id=ENTITY_AREA.value)
    await hass.async_block_till_done()
    assert _filters_accept(old_area_id=None) == (True, True)

    # Clear the override again: it inherits the device's area once more.
    entity_registry.async_update_entity(INHERITED_SENSOR, area_id=None)
    await hass.async_block_till_done()
    assert _filters_accept(old_area_id=ENTITY_AREA.value) == (True, True)


async def test_entity_removal_reloads_area_that_had_it(
    hass: HomeAssistant,
    area_config_entries: dict[MockAreaIds, MockConfigEntry],
) -> None:
    """Removing an entity reloads the area that had loaded it, and only that one."""

    device_area = _magic_area(hass, area_config_entries[DEVICE_AREA])
    entity_area = _magic_area(hass, area_config_entries[ENTITY_AREA])

    # The registry entry is gone by the time the remove event fires.
    er.async_get(hass).async_remove(INHERITED_SENSOR)
    await hass.async_block_till_done()

    # The filters ignore events shortly after an area loads.
    past = datetime.now(UTC) - timedelta(seconds=MetaAreaAutoReloadSettings.DELAY + 1)
    device_area.timestamp = past
    entity_area.timestamp = past
    event_data: Any = {"action": "remove", "entity_id": INHERITED_SENSOR}

    assert device_area.make_entity_registry_filter()(event_data)
    assert not entity_area.make_entity_registry_filter()(event_data)
