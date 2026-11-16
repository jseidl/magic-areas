"""Tests for Magic Areas diagnostics."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.binary_sensor.const import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.magic_areas.const import CONF_AREA_ID, DOMAIN, AreaStates
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.presence_hold import PresenceHoldOptions
from custom_components.magic_areas.diagnostics import (
    async_get_config_entry_diagnostics,
)

from tests.const import DEFAULT_MOCK_AREA, MockAreaIds
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor

AREA_STATE_ID = (
    f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state"
)


async def test_diagnostics_regular_area(hass: HomeAssistant) -> None:
    """A regular area reports its config, states, entities and presence sensors."""
    motion = MockBinarySensor(
        name="motion_sensor",
        unique_id="motion_sensor",
        device_class=BinarySensorDeviceClass.MOTION,
    )
    await setup_mock_entities(hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [motion]})

    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    merge_feature_config(
        data,
        AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
        PresenceHoldOptions.to_config({}),
    )
    config_entry = MockConfigEntry(domain=DOMAIN, data=data)
    await init_integration(hass, [config_entry])

    hass.states.async_set(motion.entity_id, STATE_ON)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result["entry"]["data"][CONF_AREA_ID] == DEFAULT_MOCK_AREA.value
    assert result["entry"]["options"] == {}

    area = result["area"]
    assert area["id"] == DEFAULT_MOCK_AREA.value
    assert area["is_meta"] is False
    assert area["initialized"] is True
    assert area["is_occupied"] is True
    assert AreaStates.OCCUPIED.value in area["states"]
    assert "aggregates" in area["features"]
    assert "presence_hold" in area["features"]
    assert motion.entity_id in area["presence_sensors"]
    assert motion.entity_id in area["entities"][BINARY_SENSOR_DOMAIN]
    assert AREA_STATE_ID in area["magic_entities"][BINARY_SENSOR_DOMAIN]
    assert area["area_state_entity"]["entity_id"] == AREA_STATE_ID
    assert area["area_state_entity"]["state"] == STATE_ON
    assert "child_areas" not in area

    await shutdown_integration(hass, [config_entry])


async def test_diagnostics_meta_area(hass: HomeAssistant) -> None:
    """A meta-area also reports its child areas."""
    area_entry = MockConfigEntry(
        domain=DOMAIN, data=get_basic_config_entry_data(MockAreaIds.KITCHEN)
    )
    meta_entry = MockConfigEntry(
        domain=DOMAIN, data=get_basic_config_entry_data(MockAreaIds.INTERIOR)
    )
    await init_integration(hass, [area_entry, meta_entry], areas=[MockAreaIds.KITCHEN])

    result = await async_get_config_entry_diagnostics(hass, meta_entry)

    assert result["area"]["is_meta"] is True
    assert result["area"]["child_areas"] == [MockAreaIds.KITCHEN.value]

    await shutdown_integration(hass, [area_entry, meta_entry])


async def test_diagnostics_without_runtime_data(hass: HomeAssistant) -> None:
    """An entry that is not set up still returns its entry data."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kitchen",
        data={CONF_AREA_ID: "kitchen", "api_key": "secret"},
    )
    config_entry.add_to_hass(hass)

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result["area"] is None
    assert result["entry"]["title"] == "Kitchen"
    assert result["entry"]["data"][CONF_AREA_ID] == "kitchen"
    # Sensitive keys are redacted.
    assert result["entry"]["data"]["api_key"] == "**REDACTED**"


async def test_diagnostics_area_state_missing(hass: HomeAssistant) -> None:
    """No area state entity yields None for that section."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    )
    await init_integration(hass, [config_entry])

    hass.states.async_remove(AREA_STATE_ID)
    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result["area"]["area_state_entity"] is None

    await shutdown_integration(hass, [config_entry])
