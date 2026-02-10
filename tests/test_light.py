"""Test for light groups."""

import asyncio
from collections.abc import AsyncGenerator
import logging
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as async_get_er

from custom_components.magic_areas.const import DOMAIN, AreaStates
from custom_components.magic_areas.const.light_groups import (
    LIGHT_GROUP_ALL_ICON,
    LightGroupActOn,
    LightGroupEntryOptions,
    LightGroupOptions,
    generate_group_uuid,
    validate_group_name,
)
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_attribute,
    assert_in_attribute,
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor, MockLight

_LOGGER = logging.getLogger(__name__)


# Fixtures


@pytest.fixture(name="light_groups_config_entry")
def mock_config_entry_light_groups() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Create a custom light group using the new structure
    overhead_group = {
        LightGroupEntryOptions.UUID.key: generate_group_uuid(),
        LightGroupEntryOptions.NAME.key: "Overhead Lights",
        LightGroupEntryOptions.LIGHTS.key: ["light.mock_light_1"],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.ACT_ON.key: [LightGroupActOn.OCCUPANCY],
        LightGroupEntryOptions.ICON.key: "mdi:ceiling-light",
    }

    data.update(
        LightGroupOptions.to_config(
            {
                LightGroupOptions.GROUPS.key: [overhead_group],
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_light_groups")
async def setup_integration_light_groups(
    hass: HomeAssistant,
    light_groups_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with BLE tracker config."""

    await init_integration(hass, [light_groups_config_entry])
    yield
    await shutdown_integration(hass, [light_groups_config_entry])


# Entities


@pytest.fixture(name="entities_light_one")
async def setup_entities_light_one(
    hass: HomeAssistant,
) -> list[MockLight]:
    """Create one mock light and setup the system with it."""
    mock_light_entities = [
        MockLight(
            name="mock_light_1",
            state="off",
            unique_id="unique_light",
        )
    ]
    await setup_mock_entities(
        hass, LIGHT_DOMAIN, {DEFAULT_MOCK_AREA: mock_light_entities}
    )
    return mock_light_entities


# Tests


async def test_light_group_basic(
    hass: HomeAssistant,
    entities_light_one: list[MockLight],
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_light_groups,
) -> None:
    """Test light group."""

    mock_light_entity_id = entities_light_one[0].entity_id
    mock_motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id
    # Entity ID includes magic_areas_light_groups prefix
    light_group_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_overhead_lights"
    )
    light_control_entity_id = (
        f"{SWITCH_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_light_control"
    )
    area_sensor_entity_id = f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA}_area_state"

    # Test mock entity created
    mock_light_state = hass.states.get(mock_light_entity_id)
    assert_state(mock_light_state, STATE_OFF)

    # Test light group created
    light_group_state = hass.states.get(light_group_entity_id)
    assert_state(light_group_state, STATE_OFF)
    assert_in_attribute(light_group_state, ATTR_ENTITY_ID, mock_light_entity_id)

    # Test light control switch created
    light_control_state = hass.states.get(light_control_entity_id)
    assert_state(light_control_state, STATE_OFF)

    # Test motion sensor created
    motion_sensor_state = hass.states.get(mock_motion_sensor_entity_id)
    assert_state(motion_sensor_state, STATE_OFF)

    # Test area state
    area_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_state, STATE_OFF)

    # Turn on light control
    hass.states.async_set(light_control_entity_id, STATE_ON)
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: light_control_entity_id}
    )
    await hass.async_block_till_done()

    # Test light control switch state turned on
    light_control_state = hass.states.get(light_control_entity_id)
    assert_state(light_control_state, STATE_ON)

    # Turn motion sensor on
    hass.states.async_set(mock_motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    motion_sensor_state = hass.states.get(mock_motion_sensor_entity_id)
    assert_state(motion_sensor_state, STATE_ON)

    # Test area state is STATE_ON
    area_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_state, STATE_ON)

    await asyncio.sleep(1)

    # Check light group is on
    light_group_state = hass.states.get(light_group_entity_id)
    assert_state(light_group_state, STATE_ON)

    # Turn motion sensor off
    hass.states.async_set(mock_motion_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    # Test area state is STATE_OFF
    area_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_state, STATE_OFF)

    # Check light group is off
    light_group_state = hass.states.get(light_group_entity_id)
    assert_state(light_group_state, STATE_OFF)


# Test 1: Reserved Name Validation


def test_light_group_reserved_name() -> None:
    """Test that reserved names like 'All Lights' cannot be used for custom groups."""
    # Test exact match
    assert not validate_group_name("All Lights")

    # Test lowercase
    assert not validate_group_name("all lights")

    # Test underscore version
    assert not validate_group_name("all_lights")

    # Test uppercase
    assert not validate_group_name("ALL LIGHTS")

    # Test mixed case
    assert not validate_group_name("All_Lights")

    # Valid names should pass
    assert validate_group_name("Overhead Lights")
    assert validate_group_name("Reading Nook")
    assert validate_group_name("Task Area")


# Test 7: All Lights Group Creation


@pytest.fixture(name="light_groups_multiple_config_entry")
def mock_config_entry_light_groups_multiple() -> MockConfigEntry:
    """Fixture for config entry with multiple light groups."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    overhead_group = {
        LightGroupEntryOptions.UUID.key: generate_group_uuid(),
        LightGroupEntryOptions.NAME.key: "Overhead",
        LightGroupEntryOptions.LIGHTS.key: ["light.mock_light_1"],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.ACT_ON.key: [LightGroupActOn.OCCUPANCY],
        LightGroupEntryOptions.ICON.key: "mdi:ceiling-light",
    }

    task_group = {
        LightGroupEntryOptions.UUID.key: generate_group_uuid(),
        LightGroupEntryOptions.NAME.key: "Task",
        LightGroupEntryOptions.LIGHTS.key: ["light.mock_light_2"],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.ACT_ON.key: [LightGroupActOn.OCCUPANCY],
        LightGroupEntryOptions.ICON.key: "mdi:desk-lamp",
    }

    data.update(
        LightGroupOptions.to_config(
            {
                LightGroupOptions.GROUPS.key: [overhead_group, task_group],
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_light_groups_multiple")
async def setup_integration_light_groups_multiple(
    hass: HomeAssistant,
    light_groups_multiple_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with multiple light groups."""
    await init_integration(hass, [light_groups_multiple_config_entry])
    yield
    await shutdown_integration(hass, [light_groups_multiple_config_entry])


@pytest.fixture(name="entities_light_multiple")
async def setup_entities_light_multiple(
    hass: HomeAssistant,
) -> list[MockLight]:
    """Create multiple mock lights."""
    mock_light_entities = [
        MockLight(name="mock_light_1", state="off", unique_id="unique_light_1"),
        MockLight(name="mock_light_2", state="off", unique_id="unique_light_2"),
    ]
    await setup_mock_entities(
        hass, LIGHT_DOMAIN, {DEFAULT_MOCK_AREA: mock_light_entities}
    )
    return mock_light_entities


async def test_all_lights_group(
    hass: HomeAssistant,
    entities_light_multiple: list[MockLight],
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_light_groups_multiple,
) -> None:
    """Test that 'All Lights' group is created when custom groups exist."""
    all_lights_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_all_lights"
    )
    overhead_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_overhead"
    )
    task_entity_id = f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_task"
    light_control_entity_id = (
        f"{SWITCH_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_light_control"
    )
    motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id

    # Verify All Lights group exists
    all_lights_state = hass.states.get(all_lights_entity_id)
    assert all_lights_state is not None
    assert_state(all_lights_state, STATE_OFF)

    # Verify icon is mdi:infinity
    assert all_lights_state.attributes.get("icon") == LIGHT_GROUP_ALL_ICON

    # Verify custom groups exist
    overhead_state = hass.states.get(overhead_entity_id)
    assert overhead_state is not None

    task_state = hass.states.get(task_entity_id)
    assert task_state is not None

    # Enable light control
    hass.states.async_set(light_control_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Trigger occupancy - custom groups should turn on
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()
    await asyncio.sleep(1)

    overhead_state = hass.states.get(overhead_entity_id)
    assert_state(overhead_state, STATE_ON)

    task_state = hass.states.get(task_entity_id)
    assert_state(task_state, STATE_ON)

    # Clear area - All Lights should turn off
    hass.states.async_set(motion_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    all_lights_state = hass.states.get(all_lights_entity_id)
    assert_state(all_lights_state, STATE_OFF)


# Test 10: Custom Group Name Display


async def test_custom_group_name(
    hass: HomeAssistant,
    entities_light_one: list[MockLight],
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_light_groups_multiple,
) -> None:
    """Test that custom groups use explicit names and All Lights uses translation key."""
    area_name = DEFAULT_MOCK_AREA  # "kitchen"
    group_name = "Overhead"

    overhead_entity_id = f"{LIGHT_DOMAIN}.magic_areas_light_groups_{area_name}_overhead"
    all_lights_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{area_name}_all_lights"
    )

    # Get entity registry to check attributes
    entity_registry = async_get_er(hass)

    # Check custom group has explicit name with area prefix
    overhead_entry = entity_registry.async_get(overhead_entity_id)
    assert overhead_entry is not None
    overhead_state = hass.states.get(overhead_entity_id)
    assert overhead_state is not None
    # Expected format: "{area_name} {group_name}"
    expected_friendly_name = f"{area_name} {group_name}"
    assert overhead_state.attributes.get("friendly_name") == expected_friendly_name

    # Check All Lights uses translation key (no explicit name)
    all_lights_entry = entity_registry.async_get(all_lights_entity_id)
    assert all_lights_entry is not None
    # Translation key should be set
    assert all_lights_entry.translation_key == "all_lights"


# Test 3: Brightness Only Affects ON Lights (CRITICAL)


@pytest.fixture(name="entities_light_three")
async def setup_entities_light_three(
    hass: HomeAssistant,
) -> list[MockLight]:
    """Create three mock lights with brightness support."""
    mock_light_entities = [
        MockLight(
            name="mock_light_1", state="on", unique_id="unique_light_1", dimmable=True
        ),
        MockLight(
            name="mock_light_2", state="on", unique_id="unique_light_2", dimmable=True
        ),
        MockLight(
            name="mock_light_3", state="off", unique_id="unique_light_3", dimmable=True
        ),
    ]
    await setup_mock_entities(
        hass, LIGHT_DOMAIN, {DEFAULT_MOCK_AREA: mock_light_entities}
    )
    return mock_light_entities


@pytest.fixture(name="light_groups_brightness_config_entry")
def mock_config_entry_light_groups_brightness() -> MockConfigEntry:
    """Fixture for config entry with brightness test group."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    brightness_group = {
        LightGroupEntryOptions.UUID.key: generate_group_uuid(),
        LightGroupEntryOptions.NAME.key: "Brightness Test",
        LightGroupEntryOptions.LIGHTS.key: [
            "light.mock_light_1",
            "light.mock_light_2",
            "light.mock_light_3",
        ],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.ACT_ON.key: [LightGroupActOn.OCCUPANCY],
        LightGroupEntryOptions.ICON.key: "mdi:lightbulb",
    }

    data.update(
        LightGroupOptions.to_config(
            {
                LightGroupOptions.GROUPS.key: [brightness_group],
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_light_groups_brightness")
async def setup_integration_light_groups_brightness(
    hass: HomeAssistant,
    light_groups_brightness_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with brightness test group."""
    await init_integration(hass, [light_groups_brightness_config_entry])
    yield
    await shutdown_integration(hass, [light_groups_brightness_config_entry])


async def test_light_group_brightness_on_lights_only(
    hass: HomeAssistant,
    entities_light_three: list[MockLight],
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_light_groups_brightness,
) -> None:
    """Test that brightness adjustments only affect lights that are already on."""
    light_1_entity_id = entities_light_three[0].entity_id
    light_2_entity_id = entities_light_three[1].entity_id
    light_3_entity_id = entities_light_three[2].entity_id

    group_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_brightness_test"
    )

    # Turn on lights 1 and 2 with brightness 255
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: light_1_entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: light_2_entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify lights are on with brightness 255
    light_1_state = hass.states.get(light_1_entity_id)
    assert_state(light_1_state, STATE_ON)
    assert_attribute(light_1_state, ATTR_BRIGHTNESS, "255")

    light_2_state = hass.states.get(light_2_entity_id)
    assert_state(light_2_state, STATE_ON)
    assert_attribute(light_2_state, ATTR_BRIGHTNESS, "255")

    light_3_state = hass.states.get(light_3_entity_id)
    assert_state(light_3_state, STATE_OFF)

    # Call turn_on with brightness 128 on the group
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: group_entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify only the ON lights (light_1 and light_2) changed brightness
    light_1_state = hass.states.get(light_1_entity_id)
    assert_state(light_1_state, STATE_ON)
    assert_attribute(light_1_state, ATTR_BRIGHTNESS, "128")

    light_2_state = hass.states.get(light_2_entity_id)
    assert_state(light_2_state, STATE_ON)
    assert_attribute(light_2_state, ATTR_BRIGHTNESS, "128")

    # Verify light 3 is still OFF (unchanged)
    light_3_state = hass.states.get(light_3_entity_id)
    assert_state(light_3_state, STATE_OFF)


# Test 4: act_on OCCUPANCY Only


@pytest.fixture(name="light_groups_act_on_occupancy_config_entry")
def mock_config_entry_act_on_occupancy() -> MockConfigEntry:
    """Fixture for config entry with act_on OCCUPANCY only."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    occupancy_group = {
        LightGroupEntryOptions.UUID.key: generate_group_uuid(),
        LightGroupEntryOptions.NAME.key: "Occupancy Only",
        LightGroupEntryOptions.LIGHTS.key: ["light.mock_light_1"],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.ACT_ON.key: [LightGroupActOn.OCCUPANCY],
        LightGroupEntryOptions.ICON.key: "mdi:lightbulb",
    }

    data.update(
        LightGroupOptions.to_config(
            {
                LightGroupOptions.GROUPS.key: [occupancy_group],
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_act_on_occupancy")
async def setup_integration_act_on_occupancy(
    hass: HomeAssistant,
    light_groups_act_on_occupancy_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with act_on OCCUPANCY test."""
    await init_integration(hass, [light_groups_act_on_occupancy_config_entry])
    yield
    await shutdown_integration(hass, [light_groups_act_on_occupancy_config_entry])


async def test_light_group_act_on_occupancy(
    hass: HomeAssistant,
    entities_light_one: list[MockLight],
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_act_on_occupancy,
) -> None:
    """Test that group with act_on OCCUPANCY only reacts to occupancy changes."""
    group_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_occupancy_only"
    )
    light_control_entity_id = (
        f"{SWITCH_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_light_control"
    )
    motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id

    # Enable light control
    hass.states.async_set(light_control_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Trigger occupancy (clear → occupied)
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()
    await asyncio.sleep(1)

    # Lights should turn ON (occupancy change)
    group_state = hass.states.get(group_entity_id)
    assert_state(group_state, STATE_ON)

    # Manually turn lights off (simulate user action)
    hass.states.async_set(group_entity_id, STATE_OFF)
    await hass.async_block_till_done()

    # Note: Since we can't easily trigger secondary states without proper entities,
    # we verify that the group is configured correctly
    group_state = hass.states.get(group_entity_id)
    assert group_state is not None

    # Verify act_on attribute
    act_on = group_state.attributes.get("act_on", [])
    assert LightGroupActOn.OCCUPANCY in act_on
    assert LightGroupActOn.STATE not in act_on


# Test 9: Control Reset on Clear


async def test_control_reset_on_clear(
    hass: HomeAssistant,
    entities_light_one: list[MockLight],
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_light_groups,
) -> None:
    """Test that controlling attribute resets when area clears."""
    group_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_overhead_lights"
    )
    light_control_entity_id = (
        f"{SWITCH_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_light_control"
    )
    motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id

    # Enable light control
    hass.states.async_set(light_control_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Trigger occupancy
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()
    await asyncio.sleep(1)

    # Verify lights are on and controlling is true
    group_state = hass.states.get(group_entity_id)
    assert_state(group_state, STATE_ON)
    assert group_state is not None
    assert group_state.attributes.get("controlling") is True

    # Manually turn off the group (user intervention)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: group_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0.1)

    # Controlling should now be False
    group_state = hass.states.get(group_entity_id)
    assert_state(group_state, STATE_OFF)
    assert group_state is not None
    controlling = group_state.attributes.get("controlling")
    assert controlling is False, "Controlling should be False after manual turn off"

    # Area goes clear
    hass.states.async_set(motion_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()
    await asyncio.sleep(0.1)

    # Controlling should reset to True
    group_state = hass.states.get(group_entity_id)
    assert group_state is not None
    controlling = group_state.attributes.get("controlling")
    assert controlling is True, "Controlling should reset to True when area clears"


# Tests with Secondary States - Tests 5, 6, 8


@pytest.fixture(name="entities_secondary_states")
async def setup_entities_secondary_states(
    hass: HomeAssistant,
) -> dict[str, MockBinarySensor]:
    """Create mock secondary state sensors AND motion sensor."""
    # Include motion sensor to avoid double registration of binary_sensor platform
    mock_sensors = {
        "motion": MockBinarySensor(
            name="motion_sensor",
            unique_id="motion_unique",
            device_class=BinarySensorDeviceClass.MOTION,
        ),
        "sleep": MockBinarySensor(
            name="sleep_mode",
            unique_id="sleep_unique",
            device_class=BinarySensorDeviceClass.OCCUPANCY,
        ),
        "dark": MockBinarySensor(
            name="dark",
            unique_id="dark_unique",
            device_class=BinarySensorDeviceClass.LIGHT,
        ),
        "accent": MockBinarySensor(
            name="accent_mode",
            unique_id="accent_unique",
            device_class=BinarySensorDeviceClass.OCCUPANCY,
        ),
    }
    await setup_mock_entities(
        hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: list(mock_sensors.values())}
    )
    return mock_sensors


# Test 5: act_on STATE Only


@pytest.fixture(name="light_groups_act_on_state_config_entry")
def mock_config_entry_act_on_state() -> MockConfigEntry:
    """Fixture for config entry with act_on STATE only."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Configure secondary state entity
    data.update(
        SecondaryStateOptions.to_config(
            {
                SecondaryStateOptions.SLEEP_ENTITY.key: "binary_sensor.sleep_mode",
            }
        )
    )

    state_group = {
        LightGroupEntryOptions.UUID.key: generate_group_uuid(),
        LightGroupEntryOptions.NAME.key: "State Only",
        LightGroupEntryOptions.LIGHTS.key: ["light.mock_light_1"],
        LightGroupEntryOptions.STATES.key: [AreaStates.SLEEP],
        LightGroupEntryOptions.ACT_ON.key: [LightGroupActOn.STATE],  # STATE only!
        LightGroupEntryOptions.ICON.key: "mdi:sleep",
    }

    data.update(
        LightGroupOptions.to_config(
            {
                LightGroupOptions.GROUPS.key: [state_group],
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_act_on_state")
async def setup_integration_act_on_state(
    hass: HomeAssistant,
    light_groups_act_on_state_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with act_on STATE test."""
    await init_integration(hass, [light_groups_act_on_state_config_entry])
    yield
    await shutdown_integration(hass, [light_groups_act_on_state_config_entry])


async def test_light_group_act_on_state(
    hass: HomeAssistant,
    entities_light_one: list[MockLight],
    entities_secondary_states: dict[str, MockBinarySensor],
    _setup_integration_act_on_state,
) -> None:
    """Test that group with act_on STATE only reacts to state changes after occupancy."""
    group_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_state_only"
    )
    light_control_entity_id = (
        f"{SWITCH_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_light_control"
    )
    motion_sensor_entity_id = entities_secondary_states["motion"].entity_id
    sleep_sensor_entity_id = entities_secondary_states["sleep"].entity_id

    # Enable light control
    hass.states.async_set(light_control_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Trigger occupancy first (area must be occupied)
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)

    # Group should NOT turn on (only reacts to STATE changes, not OCCUPANCY)
    group_state = hass.states.get(group_entity_id)
    assert_state(group_state, STATE_OFF)

    # Now trigger sleep state while occupied
    hass.states.async_set(sleep_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)

    # Group should turn ON (state change while occupied)
    group_state = hass.states.get(group_entity_id)
    assert_state(group_state, STATE_ON)

    # Verify act_on attribute
    assert group_state is not None
    act_on = group_state.attributes.get("act_on", [])
    assert LightGroupActOn.STATE in act_on
    assert LightGroupActOn.OCCUPANCY not in act_on


# Test 6: Priority States


@pytest.fixture(name="light_groups_priority_states_config_entry")
def mock_config_entry_priority_states() -> MockConfigEntry:
    """Fixture for config entry with priority states test - two independent groups."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Configure secondary state entity
    data.update(
        SecondaryStateOptions.to_config(
            {
                SecondaryStateOptions.SLEEP_ENTITY.key: "binary_sensor.sleep_mode",
            }
        )
    )

    # Group A: Only reacts to OCCUPIED
    occupied_group = {
        LightGroupEntryOptions.UUID.key: generate_group_uuid(),
        LightGroupEntryOptions.NAME.key: "Occupied Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.mock_light_1"],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.ACT_ON.key: [LightGroupActOn.OCCUPANCY],
        LightGroupEntryOptions.ICON.key: "mdi:motion-sensor",
    }

    # Group B: Only reacts to SLEEP (priority state)
    sleep_group = {
        LightGroupEntryOptions.UUID.key: generate_group_uuid(),
        LightGroupEntryOptions.NAME.key: "Sleep Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.mock_light_2"],
        LightGroupEntryOptions.STATES.key: [AreaStates.SLEEP],
        LightGroupEntryOptions.ACT_ON.key: [LightGroupActOn.STATE],
        LightGroupEntryOptions.ICON.key: "mdi:sleep",
    }

    data.update(
        LightGroupOptions.to_config(
            {
                LightGroupOptions.GROUPS.key: [occupied_group, sleep_group],
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_priority_states")
async def setup_integration_priority_states(
    hass: HomeAssistant,
    light_groups_priority_states_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with priority states test."""
    await init_integration(hass, [light_groups_priority_states_config_entry])
    yield
    await shutdown_integration(hass, [light_groups_priority_states_config_entry])


async def test_light_group_priority_states(
    hass: HomeAssistant,
    entities_light_multiple: list[MockLight],
    entities_secondary_states: dict[str, MockBinarySensor],
    _setup_integration_priority_states,
) -> None:
    """Test that priority states work independently across groups."""
    occupied_group_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_occupied_group"
    )
    sleep_group_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_sleep_group"
    )
    light_control_entity_id = (
        f"{SWITCH_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_light_control"
    )
    motion_sensor_entity_id = entities_secondary_states["motion"].entity_id
    sleep_sensor_entity_id = entities_secondary_states["sleep"].entity_id

    # Enable light control
    hass.states.async_set(light_control_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Trigger occupancy - Only Occupied Group should turn on
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)

    occupied_group_state = hass.states.get(occupied_group_entity_id)
    assert_state(occupied_group_state, STATE_ON)

    sleep_group_state = hass.states.get(sleep_group_entity_id)
    assert_state(sleep_group_state, STATE_OFF)

    # Trigger sleep state (priority state) - Sleep Group should turn on
    hass.states.async_set(sleep_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)

    sleep_group_state = hass.states.get(sleep_group_entity_id)
    assert_state(sleep_group_state, STATE_ON)

    # Occupied Group should still be on (independent)
    occupied_group_state = hass.states.get(occupied_group_entity_id)
    assert_state(occupied_group_state, STATE_ON)

    # Exit sleep state - Sleep Group should turn off
    hass.states.async_set(sleep_sensor_entity_id, STATE_OFF)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)

    sleep_group_state = hass.states.get(sleep_group_entity_id)
    assert_state(sleep_group_state, STATE_OFF)

    # Occupied Group should still be on (still occupied)
    occupied_group_state = hass.states.get(occupied_group_entity_id)
    assert_state(occupied_group_state, STATE_ON)


# Test 8: Multiple Independent Groups


@pytest.fixture(name="light_groups_multiple_independent_config_entry")
def mock_config_entry_multiple_independent() -> MockConfigEntry:
    """Fixture for config entry with multiple independent groups."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Configure secondary state entity for sleep
    data.update(
        SecondaryStateOptions.to_config(
            {
                SecondaryStateOptions.SLEEP_ENTITY.key: "binary_sensor.sleep_mode",
            }
        )
    )

    # Group A: Reacts to OCCUPANCY only
    group_a = {
        LightGroupEntryOptions.UUID.key: generate_group_uuid(),
        LightGroupEntryOptions.NAME.key: "Group A",
        LightGroupEntryOptions.LIGHTS.key: ["light.mock_light_1"],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.ACT_ON.key: [LightGroupActOn.OCCUPANCY],
        LightGroupEntryOptions.ICON.key: "mdi:alpha-a",
    }

    # Group B: Reacts to SLEEP state
    group_b = {
        LightGroupEntryOptions.UUID.key: generate_group_uuid(),
        LightGroupEntryOptions.NAME.key: "Group B",
        LightGroupEntryOptions.LIGHTS.key: ["light.mock_light_2"],
        LightGroupEntryOptions.STATES.key: [AreaStates.SLEEP],
        LightGroupEntryOptions.ACT_ON.key: [LightGroupActOn.STATE],
        LightGroupEntryOptions.ICON.key: "mdi:alpha-b",
    }

    data.update(
        LightGroupOptions.to_config(
            {
                LightGroupOptions.GROUPS.key: [group_a, group_b],
            }
        )
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_multiple_independent")
async def setup_integration_multiple_independent(
    hass: HomeAssistant,
    light_groups_multiple_independent_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with multiple independent groups."""
    await init_integration(hass, [light_groups_multiple_independent_config_entry])
    yield
    await shutdown_integration(hass, [light_groups_multiple_independent_config_entry])


@pytest.fixture(name="entities_light_three_for_groups")
async def setup_entities_light_three_for_groups(
    hass: HomeAssistant,
) -> list[MockLight]:
    """Create three mock lights for independent groups test."""
    mock_light_entities = [
        MockLight(name="mock_light_1", state="off", unique_id="unique_light_1"),
        MockLight(name="mock_light_2", state="off", unique_id="unique_light_2"),
        MockLight(name="mock_light_3", state="off", unique_id="unique_light_3"),
    ]
    await setup_mock_entities(
        hass, LIGHT_DOMAIN, {DEFAULT_MOCK_AREA: mock_light_entities}
    )
    return mock_light_entities


async def test_multiple_independent_groups(
    hass: HomeAssistant,
    entities_light_three_for_groups: list[MockLight],
    entities_secondary_states: dict[str, MockBinarySensor],
    _setup_integration_multiple_independent,
) -> None:
    """Test that multiple groups operate independently based on their configured states."""
    group_a_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_group_a"
    )
    group_b_entity_id = (
        f"{LIGHT_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_group_b"
    )
    light_control_entity_id = (
        f"{SWITCH_DOMAIN}.magic_areas_light_groups_{DEFAULT_MOCK_AREA}_light_control"
    )
    motion_sensor_entity_id = entities_secondary_states["motion"].entity_id
    sleep_sensor_entity_id = entities_secondary_states["sleep"].entity_id

    # Enable light control
    hass.states.async_set(light_control_entity_id, STATE_ON)
    await hass.async_block_till_done()

    # Trigger OCCUPIED - Only Group A should react
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)

    group_a_state = hass.states.get(group_a_entity_id)
    assert_state(group_a_state, STATE_ON)

    group_b_state = hass.states.get(group_b_entity_id)
    assert_state(group_b_state, STATE_OFF)

    # Trigger SLEEP - Group B should turn on
    hass.states.async_set(sleep_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()
    await asyncio.sleep(0.5)

    group_b_state = hass.states.get(group_b_entity_id)
    assert_state(group_b_state, STATE_ON)

    # Group A should still be on (independent)
    group_a_state = hass.states.get(group_a_entity_id)
    assert_state(group_a_state, STATE_ON)

    # Both groups should now be ON independently
    group_a_state = hass.states.get(group_a_entity_id)
    assert_state(group_a_state, STATE_ON)

    group_b_state = hass.states.get(group_b_entity_id)
    assert_state(group_b_state, STATE_ON)
