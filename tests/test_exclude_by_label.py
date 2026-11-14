"""Tests for excluding entities from areas by label."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor.const import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.const import ATTR_ENTITY_ID, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    DOMAIN,
    EXCLUDE_DEFAULT_LABEL_ID,
    EXCLUDE_DEFAULT_LABEL_NAME,
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

CUSTOM_LABEL = "comfort"

EXCLUDE_DEFAULT_LABEL = AreaConfigOptions.EXCLUDE_DEFAULT_LABEL.key
EXCLUDE_LABELS = AreaConfigOptions.EXCLUDE_LABELS.key
EXCLUDE_ENTITIES = AreaConfigOptions.EXCLUDE_ENTITIES.key
INCLUDE_ENTITIES = AreaConfigOptions.INCLUDE_ENTITIES.key

PLAIN_SENSOR = f"{SENSOR_DOMAIN}.plain_temperature"
LABELLED_SENSOR = f"{SENSOR_DOMAIN}.labelled_temperature"
CUSTOM_LABELLED_SENSOR = f"{SENSOR_DOMAIN}.comfort_temperature"
DEVICE_SENSORS = [
    f"{SENSOR_DOMAIN}.printer_bed_temperature",
    f"{SENSOR_DOMAIN}.printer_nozzle_temperature",
]
OTHER_AREA_SENSOR = f"{SENSOR_DOMAIN}.other_area_temperature"

ALL_AREA_SENSORS = [
    PLAIN_SENSOR,
    LABELLED_SENSOR,
    CUSTOM_LABELLED_SENSOR,
    *DEVICE_SENSORS,
]


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


async def _setup_labelled_sensors(
    hass: HomeAssistant, *, create_default_label: bool = True
) -> None:
    """Create AREA sensors: plain, labelled, custom-labelled, and on a labelled device.

    The labels are always applied; `create_default_label` controls whether the
    default label also exists in the label registry.
    """
    await setup_mock_entities(
        hass,
        SENSOR_DOMAIN,
        {
            AREA: [_temperature_sensor(entity_id) for entity_id in ALL_AREA_SENSORS],
            OTHER_AREA: [_temperature_sensor(OTHER_AREA_SENSOR)],
        },
    )

    label_registry = lr.async_get(hass)
    if create_default_label:
        default_label = label_registry.async_create(EXCLUDE_DEFAULT_LABEL_NAME)
        assert default_label.label_id == EXCLUDE_DEFAULT_LABEL_ID
    label_registry.async_create(CUSTOM_LABEL)

    device_config_entry = MockConfigEntry(domain="test")
    device_config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    printer = device_registry.async_get_or_create(
        config_entry_id=device_config_entry.entry_id,
        identifiers={("test", "printer")},
        name="3D printer",
    )
    device_registry.async_update_device(printer.id, labels={EXCLUDE_DEFAULT_LABEL_ID})

    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(
        LABELLED_SENSOR, labels={EXCLUDE_DEFAULT_LABEL_ID}
    )
    entity_registry.async_update_entity(CUSTOM_LABELLED_SENSOR, labels={CUSTOM_LABEL})
    for entity_id in DEVICE_SENSORS:
        entity_registry.async_update_entity(entity_id, device_id=printer.id)
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


def _entity_ids(
    hass: HomeAssistant, config_entry: MockConfigEntry, domain: str = SENSOR_DOMAIN
) -> set[str]:
    area = _magic_area(hass, config_entry)
    return {entity[ATTR_ENTITY_ID] for entity in area.entities.get(domain, [])}


async def _area_sensor_ids(
    hass: HomeAssistant,
    *,
    create_default_label: bool = True,
    **options: Any,
) -> set[str]:
    """Set up AREA with the given options and return the sensors it loaded."""
    await _setup_labelled_sensors(hass, create_default_label=create_default_label)
    config_entry = _area_config_entry(AREA, **options)
    await init_integration(hass, [config_entry])
    try:
        return _entity_ids(hass, config_entry)
    finally:
        await shutdown_integration(hass, [config_entry])


async def test_default_label_excludes_entities_and_devices(
    hass: HomeAssistant,
) -> None:
    """Regular areas ignore the default label on entities and on devices."""
    assert await _area_sensor_ids(hass) == {PLAIN_SENSOR, CUSTOM_LABELLED_SENSOR}


async def test_default_label_can_be_turned_off(hass: HomeAssistant) -> None:
    """Turning off the default label includes everything again."""
    assert await _area_sensor_ids(hass, **{EXCLUDE_DEFAULT_LABEL: False}) == set(
        ALL_AREA_SENSORS
    )


async def test_additional_labels_are_excluded(hass: HomeAssistant) -> None:
    """Labels picked in exclude_labels are ignored as well as the default."""
    assert await _area_sensor_ids(hass, **{EXCLUDE_LABELS: [CUSTOM_LABEL]}) == {
        PLAIN_SENSOR
    }


async def test_missing_default_label_excludes_nothing(hass: HomeAssistant) -> None:
    """Without the default label in the registry, nothing is excluded by it."""
    assert await _area_sensor_ids(hass, create_default_label=False) == set(
        ALL_AREA_SENSORS
    )


async def test_renamed_default_label_still_excluded(hass: HomeAssistant) -> None:
    """The default label keeps working after being renamed, via its id."""
    await _setup_labelled_sensors(hass)
    lr.async_get(hass).async_update(
        EXCLUDE_DEFAULT_LABEL_ID, name="Not for Magic Areas"
    )

    config_entry = _area_config_entry(AREA)
    await init_integration(hass, [config_entry])
    try:
        assert _entity_ids(hass, config_entry) == {PLAIN_SENSOR, CUSTOM_LABELLED_SENSOR}
    finally:
        await shutdown_integration(hass, [config_entry])


async def test_include_entities_overrides_labels(hass: HomeAssistant) -> None:
    """Entities listed in include_entities are kept despite excluded labels."""
    assert await _area_sensor_ids(hass, **{INCLUDE_ENTITIES: [LABELLED_SENSOR]}) == {
        PLAIN_SENSOR,
        LABELLED_SENSOR,
        CUSTOM_LABELLED_SENSOR,
    }


async def test_meta_area_excludes_only_selected_labels(hass: HomeAssistant) -> None:
    """Meta-areas exclude child entities by exclude_labels, not the default label."""
    await _setup_labelled_sensors(hass)

    area_entry = _area_config_entry(AREA)
    meta_entry = _area_config_entry(META_AREA, **{EXCLUDE_LABELS: [CUSTOM_LABEL]})
    await init_integration(hass, [area_entry, meta_entry], areas=[AREA])
    try:
        aggregate = (
            f"{SENSOR_DOMAIN}.magic_areas_aggregates_{AREA.value}_aggregate_temperature"
        )
        area_state = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{AREA.value}_area_state"
        assert aggregate in _entity_ids(hass, meta_entry)

        entity_registry = er.async_get(hass)
        entity_registry.async_update_entity(aggregate, labels={CUSTOM_LABEL})
        entity_registry.async_update_entity(
            area_state, labels={EXCLUDE_DEFAULT_LABEL_ID}
        )
        await hass.config_entries.async_reload(meta_entry.entry_id)
        await hass.async_block_till_done()

        assert aggregate not in _entity_ids(hass, meta_entry)
        assert area_state in _entity_ids(hass, meta_entry, BINARY_SENSOR_DOMAIN)
    finally:
        await shutdown_integration(hass, [area_entry, meta_entry])


async def test_label_changes_reload_affected_area(hass: HomeAssistant) -> None:
    """Label changes reload an area for its loaded and its excluded entities."""
    await _setup_labelled_sensors(hass)
    config_entry = _area_config_entry(AREA)
    await init_integration(hass, [config_entry])
    try:
        area = _magic_area(hass, config_entry)
        # The filter ignores events shortly after an area loads.
        area.timestamp = datetime.now(UTC) - timedelta(
            seconds=MetaAreaAutoReloadSettings.DELAY + 1
        )
        registry_filter = area.make_entity_registry_filter()

        def _label_change(entity_id: str) -> bool:
            event_data: Any = {
                "action": "update",
                "entity_id": entity_id,
                "changes": {"labels": set()},
            }
            return registry_filter(event_data)

        assert _label_change(PLAIN_SENSOR)  # loaded: might now be excluded
        assert _label_change(LABELLED_SENSOR)  # excluded: might now be included
        assert not _label_change(OTHER_AREA_SENSOR)  # not ours
    finally:
        await shutdown_integration(hass, [config_entry])


async def test_options_flow_label_fields(hass: HomeAssistant) -> None:
    """Regular areas offer the default-label toggle and picker; meta-areas only the picker."""
    await _setup_labelled_sensors(hass)
    area_entry = _area_config_entry(AREA)
    meta_entry = _area_config_entry(META_AREA)
    await init_integration(hass, [area_entry, meta_entry], areas=[AREA])
    try:

        async def _open_area_config(config_entry: MockConfigEntry) -> Any:
            result = await hass.config_entries.options.async_init(config_entry.entry_id)
            assert result["type"] == "menu"
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "area_config"}
            )
            assert result["type"] == "form"
            assert result["step_id"] == "area_config"
            return result

        def _fields(result: Any) -> list[str]:
            return [str(key) for key in result["data_schema"].schema]

        # Meta-areas: label picker only, no default-label toggle.
        meta_result = await _open_area_config(meta_entry)
        assert EXCLUDE_LABELS in _fields(meta_result)
        assert EXCLUDE_DEFAULT_LABEL not in _fields(meta_result)
        hass.config_entries.options.async_abort(meta_result["flow_id"])

        # Regular areas: both, just above the entity exclusion list; saving keeps them.
        result = await _open_area_config(area_entry)
        fields = _fields(result)
        assert fields.index(EXCLUDE_DEFAULT_LABEL) < fields.index(EXCLUDE_LABELS)
        assert fields.index(EXCLUDE_LABELS) == fields.index(EXCLUDE_ENTITIES) - 1

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {EXCLUDE_DEFAULT_LABEL: False, EXCLUDE_LABELS: [CUSTOM_LABEL]},
        )
        assert result["type"] == "menu"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "finish"}
        )
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()

        area_options = area_entry.options[ConfigDomains.AREA.value]
        assert area_options[EXCLUDE_DEFAULT_LABEL] is False
        assert area_options[EXCLUDE_LABELS] == [CUSTOM_LABEL]
        assert _entity_ids(hass, area_entry) == {
            PLAIN_SENSOR,
            LABELLED_SENSOR,
            *DEVICE_SENSORS,
        }
    finally:
        await shutdown_integration(hass, [area_entry, meta_entry])
