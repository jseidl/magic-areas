"""Tests for ignoring entities hidden by an integration."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.sensor.const import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    DOMAIN,
    AreaConfigOptions,
    ConfigDomains,
    MetaAreaAutoReloadSettings,
)
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

AREA = MockAreaIds.KITCHEN
OTHER_AREA = MockAreaIds.LIVING_ROOM
META_AREA = MockAreaIds.INTERIOR

PLAIN_SENSOR = f"{SENSOR_DOMAIN}.plain_temperature"
INTEGRATION_HIDDEN_SENSOR = f"{SENSOR_DOMAIN}.integration_hidden_temperature"
USER_HIDDEN_SENSOR = f"{SENSOR_DOMAIN}.user_hidden_temperature"
OTHER_AREA_SENSOR = f"{SENSOR_DOMAIN}.other_area_temperature"

ALL_AREA_SENSORS = {PLAIN_SENSOR, INTEGRATION_HIDDEN_SENSOR, USER_HIDDEN_SENSOR}

IGNORE_DIAGNOSTIC = AreaConfigOptions.IGNORE_DIAGNOSTIC_ENTITIES.key
IGNORE_INTEGRATION_HIDDEN = AreaConfigOptions.IGNORE_INTEGRATION_HIDDEN_ENTITIES.key
INCLUDE_ENTITIES = AreaConfigOptions.INCLUDE_ENTITIES.key


def _temperature_sensor(entity_id: str) -> MockSensor:
    name = entity_id.split(".")[1]
    return MockSensor(
        name=name,
        unique_id=name,
        native_value=20,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        extra_state_attributes={"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )


async def _setup_sensors(hass: HomeAssistant) -> None:
    """Create AREA sensors: plain, hidden by an integration, and hidden by the user."""
    await setup_mock_entities(
        hass,
        SENSOR_DOMAIN,
        {
            AREA: [_temperature_sensor(entity_id) for entity_id in ALL_AREA_SENSORS],
            OTHER_AREA: [_temperature_sensor(OTHER_AREA_SENSOR)],
        },
    )
    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(
        INTEGRATION_HIDDEN_SENSOR, hidden_by=er.RegistryEntryHider.INTEGRATION
    )
    entity_registry.async_update_entity(
        USER_HIDDEN_SENSOR, hidden_by=er.RegistryEntryHider.USER
    )
    await hass.async_block_till_done()


def _area_config_entry(area: MockAreaIds, **area_options: Any) -> MockConfigEntry:
    """Build a config entry for area, with area_options in its area section."""
    data = get_basic_config_entry_data(area)
    data[ConfigDomains.AREA.value].update(area_options)
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


def _sensor_ids(hass: HomeAssistant, config_entry: MockConfigEntry) -> set[str]:
    area = _magic_area(hass, config_entry)
    return {entity[ATTR_ENTITY_ID] for entity in area.entities.get(SENSOR_DOMAIN, [])}


async def _area_sensor_ids(hass: HomeAssistant, **options: Any) -> set[str]:
    """Set up AREA with the given options and return the sensors it loaded."""
    await _setup_sensors(hass)
    config_entry = _area_config_entry(AREA, **options)
    await init_integration(hass, [config_entry])
    try:
        return _sensor_ids(hass, config_entry)
    finally:
        await shutdown_integration(hass, [config_entry])


async def test_integration_hidden_entities_excluded_by_default(
    hass: HomeAssistant,
) -> None:
    """Entities hidden by an integration are ignored; ones hidden by the user aren't."""
    assert await _area_sensor_ids(hass) == {PLAIN_SENSOR, USER_HIDDEN_SENSOR}


async def test_integration_hidden_entities_included_when_option_off(
    hass: HomeAssistant,
) -> None:
    """Turning the option off includes integration-hidden entities again."""
    assert (
        await _area_sensor_ids(hass, **{IGNORE_INTEGRATION_HIDDEN: False})
        == ALL_AREA_SENSORS
    )


async def test_include_entities_overrides_integration_hiding(
    hass: HomeAssistant,
) -> None:
    """Entities listed in include_entities are kept even if an integration hid them."""
    assert (
        await _area_sensor_ids(hass, **{INCLUDE_ENTITIES: [INTEGRATION_HIDDEN_SENSOR]})
        == ALL_AREA_SENSORS
    )


async def test_hiding_and_disabling_reload_affected_area(hass: HomeAssistant) -> None:
    """Hidden and disabled changes reload an area for entities it has or would load."""
    await _setup_sensors(hass)
    config_entries = {
        AREA: _area_config_entry(AREA),
        OTHER_AREA: _area_config_entry(
            OTHER_AREA, **{IGNORE_INTEGRATION_HIDDEN: False}
        ),
    }
    await init_integration(
        hass, list(config_entries.values()), areas=list(config_entries)
    )
    try:
        past = datetime.now(UTC) - timedelta(
            seconds=MetaAreaAutoReloadSettings.DELAY + 1
        )

        def _accepts(area: MockAreaIds, entity_id: str, field: str) -> bool:
            # The filters ignore events shortly after an area loads.
            magic_area = _magic_area(hass, config_entries[area])
            magic_area.timestamp = past
            event_data: Any = {
                "action": "update",
                "entity_id": entity_id,
                "changes": {field: None},
            }
            return magic_area.make_entity_registry_filter()(event_data)

        # AREA ignores integration-hidden entities: hiding or unhiding matters.
        assert _accepts(AREA, PLAIN_SENSOR, "hidden_by")  # loaded, may now be hidden
        assert _accepts(AREA, INTEGRATION_HIDDEN_SENSOR, "hidden_by")  # may be unhidden
        assert _accepts(AREA, PLAIN_SENSOR, "disabled_by")
        assert not _accepts(AREA, OTHER_AREA_SENSOR, "hidden_by")  # not ours
        assert not _accepts(AREA, PLAIN_SENSOR, "name")  # irrelevant change

        # OTHER_AREA doesn't ignore them: only disabling matters there.
        assert not _accepts(OTHER_AREA, OTHER_AREA_SENSOR, "hidden_by")
        assert _accepts(OTHER_AREA, OTHER_AREA_SENSOR, "disabled_by")
    finally:
        await shutdown_integration(hass, list(config_entries.values()))


async def test_options_flow_field(hass: HomeAssistant) -> None:
    """Regular areas offer the option after the diagnostic one; meta-areas don't."""
    await _setup_sensors(hass)
    area_entry = _area_config_entry(AREA)
    meta_entry = _area_config_entry(META_AREA)
    await init_integration(hass, [area_entry, meta_entry], areas=[AREA])
    try:

        async def _fields(config_entry: MockConfigEntry) -> list[str]:
            result = await hass.config_entries.options.async_init(config_entry.entry_id)
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "area_config"}
            )
            assert result["step_id"] == "area_config"
            hass.config_entries.options.async_abort(result["flow_id"])
            return [str(key) for key in result["data_schema"].schema]

        fields = await _fields(area_entry)
        assert (
            fields.index(IGNORE_INTEGRATION_HIDDEN)
            == fields.index(IGNORE_DIAGNOSTIC) + 1
        )
        assert IGNORE_INTEGRATION_HIDDEN not in await _fields(meta_entry)
    finally:
        await shutdown_integration(hass, [area_entry, meta_entry])


async def test_disabled_entities_are_excluded(hass: HomeAssistant) -> None:
    """Entities disabled in the registry are not loaded into the area."""
    await _setup_sensors(hass)
    er.async_get(hass).async_update_entity(
        PLAIN_SENSOR, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    config_entry = _area_config_entry(AREA)
    await init_integration(hass, [config_entry])
    try:
        assert PLAIN_SENSOR not in _sensor_ids(hass, config_entry)
        assert USER_HIDDEN_SENSOR in _sensor_ids(hass, config_entry)
    finally:
        await shutdown_integration(hass, [config_entry])


@pytest.mark.parametrize(
    ("ignore_diagnostic", "expected_loaded"),
    [(True, False), (False, True)],
)
async def test_diagnostic_entities_follow_the_ignore_option(
    hass: HomeAssistant, ignore_diagnostic: bool, expected_loaded: bool
) -> None:
    """Config and diagnostic entities are only loaded when the option is off."""
    await _setup_sensors(hass)
    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(
        PLAIN_SENSOR, entity_category=EntityCategory.DIAGNOSTIC
    )
    entity_registry.async_update_entity(
        USER_HIDDEN_SENSOR, entity_category=EntityCategory.CONFIG
    )
    await hass.async_block_till_done()

    config_entry = _area_config_entry(AREA, **{IGNORE_DIAGNOSTIC: ignore_diagnostic})
    await init_integration(hass, [config_entry])
    try:
        loaded = _sensor_ids(hass, config_entry)
        assert (PLAIN_SENSOR in loaded) is expected_loaded
        assert (USER_HIDDEN_SENSOR in loaded) is expected_loaded
    finally:
        await shutdown_integration(hass, [config_entry])


async def test_area_never_loads_its_own_entities(hass: HomeAssistant) -> None:
    """Entities created by the area's own config entry are not loaded, even if assigned to it."""
    await _setup_sensors(hass)
    config_entry = _area_config_entry(AREA)
    await init_integration(hass, [config_entry])
    try:
        own_entity_id = (
            f"{SENSOR_DOMAIN}.magic_areas_aggregates_{AREA.value}_aggregate_temperature"
        )
        er.async_get(hass).async_update_entity(own_entity_id, area_id=AREA.value)
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert own_entity_id not in _sensor_ids(hass, config_entry)
        assert PLAIN_SENSOR in _sensor_ids(hass, config_entry)
    finally:
        await shutdown_integration(hass, [config_entry])


async def test_area_recognises_entities_of_its_own_config_entry(
    hass: HomeAssistant,
) -> None:
    """An entity belongs to the area only when its config entry is the area's own."""
    await _setup_sensors(hass)
    config_entry = _area_config_entry(AREA)
    await init_integration(hass, [config_entry])
    try:
        area = _magic_area(hass, config_entry)
        entity_registry = er.async_get(hass)
        own_entity = entity_registry.async_get(
            f"{SENSOR_DOMAIN}.magic_areas_aggregates_{AREA.value}_aggregate_temperature"
        )
        assert own_entity is not None
        foreign_entity = entity_registry.async_get(PLAIN_SENSOR)
        assert foreign_entity is not None

        # pylint: disable=protected-access
        assert area._is_magic_area_entity(own_entity)
        assert not area._is_magic_area_entity(foreign_entity)
    finally:
        await shutdown_integration(hass, [config_entry])
