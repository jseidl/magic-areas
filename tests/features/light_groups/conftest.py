"""Shared fixtures for light groups tests."""

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
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_OFF
from homeassistant.core import Context, HomeAssistant

from custom_components.magic_areas.const import DOMAIN, AreaStates
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.light_groups import (
    LIGHT_GROUP_CONTEXT_PREFIX,
    LightGroupEntryOptions,
    LightGroupOptions,
    LightGroupTurnOffWhen,
    LightGroupTurnOnWhen,
)
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
    trigger_occupancy,
    trigger_secondary_state,
)
from tests.mocks import MockBinarySensor, MockLight

_LOGGER = logging.getLogger(__name__)

# Common Helper Functions


def create_magic_context() -> Context:
    """Create a Magic Areas context (won't trigger manual mode)."""
    return Context(id=f"{LIGHT_GROUP_CONTEXT_PREFIX}_test123")


async def enable_light_control(hass: HomeAssistant, area_id: str) -> None:
    """Enable light control for an area."""
    control_id = f"switch.magic_areas_light_groups_{area_id}_light_control"
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: control_id}, blocking=True
    )
    await hass.async_block_till_done()


# Entity Setup Fixtures


@pytest.fixture
async def setup_test_lights(hass: HomeAssistant) -> list[MockLight]:
    """Create and register mock lights."""
    lights = [
        MockLight(name="light_1", state=STATE_OFF, unique_id="light_1", dimmable=True),
        MockLight(name="light_2", state=STATE_OFF, unique_id="light_2", dimmable=True),
        MockLight(name="light_3", state=STATE_OFF, unique_id="light_3", dimmable=True),
    ]
    await setup_mock_entities(hass, LIGHT_DOMAIN, {DEFAULT_MOCK_AREA: lights})
    return lights


@pytest.fixture
async def setup_all_binary_sensors(hass: HomeAssistant) -> dict[str, MockBinarySensor]:
    """Create and register ALL binary sensors at once (motion + secondary states).

    This avoids registering the binary_sensor platform multiple times.
    """
    motion_sensor = MockBinarySensor(
        name="motion_sensor",
        unique_id="motion_sensor",
        device_class=BinarySensorDeviceClass.MOTION,
    )

    sleep_sensor = MockBinarySensor(
        name="sleep_mode",
        unique_id="sleep_mode",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    )

    # Dark sensor starts OFF (which means dark for a light sensor)
    dark_sensor = MockBinarySensor(
        name="dark_sensor",
        unique_id="dark_sensor",
        device_class=BinarySensorDeviceClass.LIGHT,
        state=STATE_OFF,  # OFF = dark for light sensors
    )

    accent_sensor = MockBinarySensor(
        name="accent_mode",
        unique_id="accent_mode",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    )

    # Register ALL sensors together (single platform setup)
    all_sensors = [motion_sensor, sleep_sensor, dark_sensor, accent_sensor]
    await setup_mock_entities(
        hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: all_sensors}
    )

    return {
        "motion": motion_sensor,
        "sleep": sleep_sensor,
        "dark": dark_sensor,
        "accent": accent_sensor,
    }


@pytest.fixture
async def setup_motion_sensor(
    setup_all_binary_sensors: dict[str, MockBinarySensor],
) -> MockBinarySensor:
    """Get motion sensor from merged fixture (for backwards compatibility)."""
    return setup_all_binary_sensors["motion"]


@pytest.fixture
async def setup_secondary_state_sensors(
    setup_all_binary_sensors: dict[str, MockBinarySensor],
) -> dict[str, MockBinarySensor]:
    """Get secondary state sensors from merged fixture (for backwards compatibility)."""
    return {
        "sleep": setup_all_binary_sensors["sleep"],
        "dark": setup_all_binary_sensors["dark"],
        "accent": setup_all_binary_sensors["accent"],
    }


# Config Entry Fixtures


@pytest.fixture
def light_group_basic_config_entry() -> MockConfigEntry:
    """Basic light group with OCCUPIED state trigger and dark requirement."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Enable aggregates for dark detection
    merge_feature_config(
        data,
        AggregateOptions.to_config(
            {
                AggregateOptions.MIN_ENTITIES.key: 1,
                AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key: [
                    BinarySensorDeviceClass.LIGHT
                ],
            }
        ),
    )

    overhead_group = {
        LightGroupEntryOptions.NAME.key: "Test Group",
        LightGroupEntryOptions.LIGHTS.key: [
            "light.light_1",
            "light.light_2",
            "light.light_3",
        ],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [
            LightGroupTurnOnWhen.AREA_OCCUPIED,
            LightGroupTurnOnWhen.STATE_GAIN,
            LightGroupTurnOnWhen.AREA_DARK,  # Turn on when area becomes dark
        ],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [
            LightGroupTurnOffWhen.AREA_CLEAR,
            LightGroupTurnOffWhen.STATE_LOSS,
            LightGroupTurnOffWhen.EXTERIOR_BRIGHT,  # Include exterior bright
        ],
        LightGroupEntryOptions.REQUIRE_DARK.key: True,
    }

    merge_feature_config(
        data,
        LightGroupOptions.to_config({LightGroupOptions.GROUPS.key: [overhead_group]}),
    )
    return MockConfigEntry(domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data)


@pytest.fixture
def light_group_dark_optional_config_entry() -> MockConfigEntry:
    """Light group without dark requirement."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    overhead_group = {
        LightGroupEntryOptions.NAME.key: "Test Group Dark Optional",
        LightGroupEntryOptions.LIGHTS.key: [
            "light.light_1",
            "light.light_2",
            "light.light_3",
        ],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [
            LightGroupTurnOnWhen.AREA_OCCUPIED,
            LightGroupTurnOnWhen.STATE_GAIN,
        ],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [
            LightGroupTurnOffWhen.AREA_CLEAR,
            LightGroupTurnOffWhen.STATE_LOSS,
        ],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }

    data.update(
        LightGroupOptions.to_config({LightGroupOptions.GROUPS.key: [overhead_group]})
    )
    return MockConfigEntry(domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data)


@pytest.fixture
def light_group_sleep_config_entry() -> MockConfigEntry:
    """Light group configured for sleep state."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Enable aggregates for dark detection
    merge_feature_config(
        data,
        AggregateOptions.to_config(
            {
                AggregateOptions.MIN_ENTITIES.key: 1,
                AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key: [
                    BinarySensorDeviceClass.LIGHT
                ],
            }
        ),
    )

    # Configure secondary state entity
    data.update(
        SecondaryStateOptions.to_config(
            {SecondaryStateOptions.SLEEP_ENTITY.key: "binary_sensor.sleep_mode"}
        )
    )

    sleep_group = {
        LightGroupEntryOptions.NAME.key: "Sleep Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.light_1"],
        LightGroupEntryOptions.STATES.key: [AreaStates.SLEEP],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [LightGroupTurnOnWhen.STATE_GAIN],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [LightGroupTurnOffWhen.STATE_LOSS],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,  # Don't require dark for sleep test
    }

    merge_feature_config(
        data, LightGroupOptions.to_config({LightGroupOptions.GROUPS.key: [sleep_group]})
    )
    return MockConfigEntry(domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data)


@pytest.fixture
def light_group_never_turn_off_config_entry() -> MockConfigEntry:
    """Light group configured to NEVER turn off automatically (empty turn_off_when)."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    never_group = {
        LightGroupEntryOptions.NAME.key: "Never Turn Off Group",
        LightGroupEntryOptions.LIGHTS.key: [
            "light.light_1",
            "light.light_2",
            "light.light_3",
        ],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [
            LightGroupTurnOnWhen.AREA_OCCUPIED,
        ],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [],  # Empty = never turn off
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }

    data.update(
        LightGroupOptions.to_config({LightGroupOptions.GROUPS.key: [never_group]})
    )
    return MockConfigEntry(domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data)


@pytest.fixture
def light_group_no_exterior_config_entry() -> MockConfigEntry:
    """Light group without EXTERIOR_BRIGHT in turn_off_when."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Enable aggregates for dark detection
    merge_feature_config(
        data,
        AggregateOptions.to_config(
            {
                AggregateOptions.MIN_ENTITIES.key: 1,
                AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key: [
                    BinarySensorDeviceClass.LIGHT
                ],
            }
        ),
    )

    no_exterior_group = {
        LightGroupEntryOptions.NAME.key: "No Exterior Group",
        LightGroupEntryOptions.LIGHTS.key: [
            "light.light_1",
            "light.light_2",
            "light.light_3",
        ],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [
            LightGroupTurnOnWhen.AREA_OCCUPIED,
            LightGroupTurnOnWhen.STATE_GAIN,
        ],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [
            LightGroupTurnOffWhen.AREA_CLEAR,
            LightGroupTurnOffWhen.STATE_LOSS,
            # EXTERIOR_BRIGHT intentionally omitted
        ],
        LightGroupEntryOptions.REQUIRE_DARK.key: True,
    }

    merge_feature_config(
        data,
        LightGroupOptions.to_config(
            {LightGroupOptions.GROUPS.key: [no_exterior_group]}
        ),
    )
    return MockConfigEntry(domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data)


# Integration Setup Fixtures


@pytest.fixture
async def setup_basic_light_group(
    hass: HomeAssistant,
    light_group_basic_config_entry: MockConfigEntry,
    setup_test_lights: list[MockLight],
    setup_motion_sensor: MockBinarySensor,
) -> AsyncGenerator[dict[str, Any]]:
    """Set up complete integration with basic light group (requires dark)."""
    await init_integration(hass, [light_group_basic_config_entry])
    await hass.async_block_till_done()

    # Wait for aggregate sensor and area states to initialize
    await asyncio.sleep(1.0)
    await hass.async_block_till_done()

    # Debug: Log aggregate and area states
    aggregate_id = f"binary_sensor.magic_areas_aggregates_{DEFAULT_MOCK_AREA.value}_aggregate_light"
    area_state_id = f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state"

    aggregate_state = hass.states.get(aggregate_id)
    area_state = hass.states.get(area_state_id)

    _LOGGER.debug("=== POST-INIT DEBUG ===")
    _LOGGER.debug(
        "Aggregate light sensor (%s): %s",
        aggregate_id,
        aggregate_state.state if aggregate_state else "NOT FOUND",
    )
    _LOGGER.debug(
        "Area state (%s): %s",
        area_state_id,
        area_state.state if area_state else "NOT FOUND",
    )
    if area_state:
        _LOGGER.debug("Area states attribute: %s", area_state.attributes.get("states"))
    _LOGGER.debug("======================")

    await enable_light_control(hass, DEFAULT_MOCK_AREA.value)

    yield {
        "config_entry": light_group_basic_config_entry,
        "lights": setup_test_lights,
        "motion_sensor": setup_motion_sensor,
        "light_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_test_group",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
        "light_control_id": f"switch.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_light_control",
    }

    await shutdown_integration(hass, [light_group_basic_config_entry])


# State Priority Test Fixtures


@pytest.fixture
def light_group_multi_occupied_and_sleep_config_entry() -> MockConfigEntry:
    """Config with two groups: one for OCCUPIED, one for SLEEP."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Configure sleep entity
    data.update(
        SecondaryStateOptions.to_config(
            {SecondaryStateOptions.SLEEP_ENTITY.key: "binary_sensor.sleep_mode"}
        )
    )

    # Group 1: Overhead lights for OCCUPIED
    occupied_group = {
        LightGroupEntryOptions.NAME.key: "Occupied Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.light_1", "light.light_2"],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [LightGroupTurnOnWhen.STATE_GAIN],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [LightGroupTurnOffWhen.STATE_LOSS],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }

    # Group 2: Night light for SLEEP
    sleep_group = {
        LightGroupEntryOptions.NAME.key: "Sleep Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.light_3"],
        LightGroupEntryOptions.STATES.key: [AreaStates.SLEEP],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [LightGroupTurnOnWhen.STATE_GAIN],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [LightGroupTurnOffWhen.STATE_LOSS],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }

    merge_feature_config(
        data,
        LightGroupOptions.to_config(
            {LightGroupOptions.GROUPS.key: [occupied_group, sleep_group]}
        ),
    )
    return MockConfigEntry(domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data)


@pytest.fixture
async def setup_multi_group_occupied_and_sleep(
    hass: HomeAssistant,
    light_group_multi_occupied_and_sleep_config_entry: MockConfigEntry,
    setup_test_lights: list[MockLight],
    setup_motion_sensor: MockBinarySensor,
    setup_secondary_state_sensors: dict[str, MockBinarySensor],
) -> AsyncGenerator[dict[str, Any]]:
    """Set up integration with both OCCUPIED and SLEEP light groups."""
    await init_integration(hass, [light_group_multi_occupied_and_sleep_config_entry])
    await enable_light_control(hass, DEFAULT_MOCK_AREA.value)

    yield {
        "config_entry": light_group_multi_occupied_and_sleep_config_entry,
        "lights": setup_test_lights,
        "motion_sensor": setup_motion_sensor,
        "secondary_sensors": setup_secondary_state_sensors,
        "occupied_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_occupied_group",
        "sleep_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_sleep_group",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
    }

    await shutdown_integration(
        hass, [light_group_multi_occupied_and_sleep_config_entry]
    )


@pytest.fixture
def light_group_user_defined_state_config_entry() -> MockConfigEntry:
    """Config with user-defined state and matching light groups."""
    from custom_components.magic_areas.const import ConfigDomains
    from custom_components.magic_areas.const.user_defined_states import (
        UserDefinedStateEntryOptions,
        UserDefinedStateOptions,
    )

    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Configure user-defined state "movie_time"
    data[ConfigDomains.USER_DEFINED_STATES.value] = {
        UserDefinedStateOptions.STATES.key: [
            {
                UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                UserDefinedStateEntryOptions.ENTITY.key: "binary_sensor.movie_mode",
            }
        ]
    }

    # Group 1: Overhead for OCCUPIED (should be blocked when movie_time active)
    occupied_group = {
        LightGroupEntryOptions.NAME.key: "Occupied Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.light_1", "light.light_2"],
        LightGroupEntryOptions.STATES.key: [AreaStates.OCCUPIED],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [LightGroupTurnOnWhen.STATE_GAIN],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [LightGroupTurnOffWhen.STATE_LOSS],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }

    # Group 2: Accent lights for movie_time
    movie_group = {
        LightGroupEntryOptions.NAME.key: "Movie Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.light_3"],
        LightGroupEntryOptions.STATES.key: ["movie_time"],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [LightGroupTurnOnWhen.STATE_GAIN],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [LightGroupTurnOffWhen.STATE_LOSS],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }

    merge_feature_config(
        data,
        LightGroupOptions.to_config(
            {LightGroupOptions.GROUPS.key: [occupied_group, movie_group]}
        ),
    )
    return MockConfigEntry(domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data)


@pytest.fixture
async def setup_user_defined_state_light_group(
    hass: HomeAssistant,
    light_group_user_defined_state_config_entry: MockConfigEntry,
    setup_test_lights: list[MockLight],
) -> AsyncGenerator[dict[str, Any]]:
    """Set up integration with user-defined state light groups."""
    # Create ALL sensors inline (don't use setup_all_binary_sensors)
    motion_sensor = MockBinarySensor(
        name="motion_sensor",
        unique_id="motion_sensor",
        device_class=BinarySensorDeviceClass.MOTION,
    )

    movie_mode = MockBinarySensor(
        name="movie_mode",
        unique_id="movie_mode",
        device_class=None,
    )

    # Register ALL sensors at once
    await setup_mock_entities(
        hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [motion_sensor, movie_mode]}
    )

    await init_integration(hass, [light_group_user_defined_state_config_entry])
    await enable_light_control(hass, DEFAULT_MOCK_AREA.value)

    yield {
        "config_entry": light_group_user_defined_state_config_entry,
        "lights": setup_test_lights,
        "motion_sensor": motion_sensor,
        "movie_mode": movie_mode,
        "occupied_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_occupied_group",
        "movie_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_movie_group",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
    }

    await shutdown_integration(hass, [light_group_user_defined_state_config_entry])


@pytest.fixture
def light_group_multi_user_defined_config_entry() -> MockConfigEntry:
    """Config with multiple user-defined states."""
    from custom_components.magic_areas.const import ConfigDomains
    from custom_components.magic_areas.const.user_defined_states import (
        UserDefinedStateEntryOptions,
        UserDefinedStateOptions,
    )

    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Configure two user-defined states
    data[ConfigDomains.USER_DEFINED_STATES.value] = {
        UserDefinedStateOptions.STATES.key: [
            {
                UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                UserDefinedStateEntryOptions.ENTITY.key: "binary_sensor.movie_mode",
            },
            {
                UserDefinedStateEntryOptions.NAME.key: "Gaming",
                UserDefinedStateEntryOptions.ENTITY.key: "binary_sensor.gaming_mode",
            },
        ]
    }

    # Groups for each user-defined state
    movie_group = {
        LightGroupEntryOptions.NAME.key: "Movie Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.light_1"],
        LightGroupEntryOptions.STATES.key: ["movie_time"],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [LightGroupTurnOnWhen.STATE_GAIN],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [LightGroupTurnOffWhen.STATE_LOSS],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }

    gaming_group = {
        LightGroupEntryOptions.NAME.key: "Gaming Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.light_2"],
        LightGroupEntryOptions.STATES.key: ["gaming"],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [LightGroupTurnOnWhen.STATE_GAIN],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [LightGroupTurnOffWhen.STATE_LOSS],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }

    merge_feature_config(
        data,
        LightGroupOptions.to_config(
            {LightGroupOptions.GROUPS.key: [movie_group, gaming_group]}
        ),
    )
    return MockConfigEntry(domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data)


@pytest.fixture
async def setup_multi_user_defined_states(
    hass: HomeAssistant,
    light_group_multi_user_defined_config_entry: MockConfigEntry,
    setup_test_lights: list[MockLight],
) -> AsyncGenerator[dict[str, Any]]:
    """Set up integration with multiple user-defined state light groups."""
    # Create motion sensor
    motion_sensor = MockBinarySensor(
        name="motion_sensor",
        unique_id="motion_sensor",
        device_class=BinarySensorDeviceClass.MOTION,
    )

    # Create both mode sensors
    movie_mode = MockBinarySensor(
        name="movie_mode",
        unique_id="movie_mode",
        device_class=None,
    )

    gaming_mode = MockBinarySensor(
        name="gaming_mode",
        unique_id="gaming_mode",
        device_class=None,
    )

    await setup_mock_entities(
        hass,
        BINARY_SENSOR_DOMAIN,
        {DEFAULT_MOCK_AREA: [motion_sensor, movie_mode, gaming_mode]},
    )

    await init_integration(hass, [light_group_multi_user_defined_config_entry])
    await enable_light_control(hass, DEFAULT_MOCK_AREA.value)

    yield {
        "config_entry": light_group_multi_user_defined_config_entry,
        "lights": setup_test_lights,
        "movie_mode": movie_mode,
        "gaming_mode": gaming_mode,
        "motion_sensor": motion_sensor,
        "movie_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_movie_group",
        "gaming_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_gaming_group",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
    }

    await shutdown_integration(hass, [light_group_multi_user_defined_config_entry])


@pytest.fixture
def light_group_sleep_and_user_defined_config_entry() -> MockConfigEntry:
    """Config with both sleep and user-defined state groups."""
    from custom_components.magic_areas.const import ConfigDomains
    from custom_components.magic_areas.const.user_defined_states import (
        UserDefinedStateEntryOptions,
        UserDefinedStateOptions,
    )

    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)

    # Configure sleep entity
    data.update(
        SecondaryStateOptions.to_config(
            {SecondaryStateOptions.SLEEP_ENTITY.key: "binary_sensor.sleep_mode"}
        )
    )

    # Configure user-defined state
    data[ConfigDomains.USER_DEFINED_STATES.value] = {
        UserDefinedStateOptions.STATES.key: [
            {
                UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                UserDefinedStateEntryOptions.ENTITY.key: "binary_sensor.movie_mode",
            }
        ]
    }

    # Group 1: Sleep group
    sleep_group = {
        LightGroupEntryOptions.NAME.key: "Sleep Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.light_1"],
        LightGroupEntryOptions.STATES.key: [AreaStates.SLEEP],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [LightGroupTurnOnWhen.STATE_GAIN],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [LightGroupTurnOffWhen.STATE_LOSS],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }

    # Group 2: Movie group (user-defined state)
    movie_group = {
        LightGroupEntryOptions.NAME.key: "Movie Group",
        LightGroupEntryOptions.LIGHTS.key: ["light.light_2"],
        LightGroupEntryOptions.STATES.key: ["movie_time"],
        LightGroupEntryOptions.TURN_ON_WHEN.key: [LightGroupTurnOnWhen.STATE_GAIN],
        LightGroupEntryOptions.TURN_OFF_WHEN.key: [LightGroupTurnOffWhen.STATE_LOSS],
        LightGroupEntryOptions.REQUIRE_DARK.key: False,
    }

    merge_feature_config(
        data,
        LightGroupOptions.to_config(
            {LightGroupOptions.GROUPS.key: [sleep_group, movie_group]}
        ),
    )
    return MockConfigEntry(domain=DOMAIN, title=DEFAULT_MOCK_AREA.title(), data=data)


@pytest.fixture
async def setup_sleep_and_user_defined(
    hass: HomeAssistant,
    light_group_sleep_and_user_defined_config_entry: MockConfigEntry,
    setup_test_lights: list[MockLight],
) -> AsyncGenerator[dict[str, Any]]:
    """Set up integration with both sleep and user-defined state groups."""

    # Create motion sensor
    motion_sensor = MockBinarySensor(
        name="motion_sensor",
        unique_id="motion_sensor",
        device_class=BinarySensorDeviceClass.MOTION,
    )

    # Create ALL sensors inline (sleep + movie)
    sleep_sensor = MockBinarySensor(
        name="sleep_mode",
        unique_id="sleep_mode",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    )

    movie_mode = MockBinarySensor(
        name="movie_mode",
        unique_id="movie_mode",
        device_class=None,
    )

    # Register ALL sensors at once
    await setup_mock_entities(
        hass,
        BINARY_SENSOR_DOMAIN,
        {DEFAULT_MOCK_AREA: [motion_sensor, sleep_sensor, movie_mode]},
    )

    await init_integration(hass, [light_group_sleep_and_user_defined_config_entry])
    await enable_light_control(hass, DEFAULT_MOCK_AREA.value)

    yield {
        "config_entry": light_group_sleep_and_user_defined_config_entry,
        "lights": setup_test_lights,
        "secondary_sensors": {"sleep": sleep_sensor},  # Provide in expected format
        "movie_mode": movie_mode,
        "motion_sensor": motion_sensor,
        "sleep_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_sleep_group",
        "movie_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_movie_group",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
    }

    await shutdown_integration(hass, [light_group_sleep_and_user_defined_config_entry])


@pytest.fixture
async def setup_dark_optional_light_group(
    hass: HomeAssistant,
    light_group_dark_optional_config_entry: MockConfigEntry,
    setup_test_lights: list[MockLight],
    setup_motion_sensor: MockBinarySensor,
) -> AsyncGenerator[dict[str, Any]]:
    """Set up complete integration with light group that doesn't require dark."""
    await init_integration(hass, [light_group_dark_optional_config_entry])
    await enable_light_control(hass, DEFAULT_MOCK_AREA.value)

    yield {
        "config_entry": light_group_dark_optional_config_entry,
        "lights": setup_test_lights,
        "motion_sensor": setup_motion_sensor,
        "light_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_test_group_dark_optional",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
        "light_control_id": f"switch.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_light_control",
    }

    await shutdown_integration(hass, [light_group_dark_optional_config_entry])


@pytest.fixture
async def setup_sleep_light_group(
    hass: HomeAssistant,
    light_group_sleep_config_entry: MockConfigEntry,
    setup_test_lights: list[MockLight],
    setup_motion_sensor: MockBinarySensor,
    setup_secondary_state_sensors: dict[str, MockBinarySensor],
) -> AsyncGenerator[dict[str, Any]]:
    """Set up complete integration with sleep light group."""
    await init_integration(hass, [light_group_sleep_config_entry])
    await enable_light_control(hass, DEFAULT_MOCK_AREA.value)

    yield {
        "config_entry": light_group_sleep_config_entry,
        "lights": setup_test_lights,
        "motion_sensor": setup_motion_sensor,
        "secondary_sensors": setup_secondary_state_sensors,
        "light_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_sleep_group",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
        "light_control_id": f"switch.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_light_control",
    }

    await shutdown_integration(hass, [light_group_sleep_config_entry])


@pytest.fixture
async def setup_never_turn_off_light_group(
    hass: HomeAssistant,
    light_group_never_turn_off_config_entry: MockConfigEntry,
    setup_test_lights: list[MockLight],
    setup_motion_sensor: MockBinarySensor,
) -> AsyncGenerator[dict[str, Any]]:
    """Set up complete integration with NEVER turn-off light group."""
    await init_integration(hass, [light_group_never_turn_off_config_entry])
    await enable_light_control(hass, DEFAULT_MOCK_AREA.value)

    yield {
        "config_entry": light_group_never_turn_off_config_entry,
        "lights": setup_test_lights,
        "motion_sensor": setup_motion_sensor,
        "light_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_never_turn_off_group",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
        "light_control_id": f"switch.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_light_control",
    }

    await shutdown_integration(hass, [light_group_never_turn_off_config_entry])


@pytest.fixture
async def setup_no_exterior_light_group(
    hass: HomeAssistant,
    light_group_no_exterior_config_entry: MockConfigEntry,
    setup_test_lights: list[MockLight],
    setup_motion_sensor: MockBinarySensor,
) -> AsyncGenerator[dict[str, Any]]:
    """Set up complete integration with light group that doesn't respond to exterior bright."""
    await init_integration(hass, [light_group_no_exterior_config_entry])
    await enable_light_control(hass, DEFAULT_MOCK_AREA.value)

    yield {
        "config_entry": light_group_no_exterior_config_entry,
        "lights": setup_test_lights,
        "motion_sensor": setup_motion_sensor,
        "light_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_no_exterior_group",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
        "light_control_id": f"switch.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_light_control",
    }

    await shutdown_integration(hass, [light_group_no_exterior_config_entry])


@pytest.fixture
async def setup_basic_light_group_bright(
    hass: HomeAssistant,
    light_group_basic_config_entry: MockConfigEntry,
    setup_test_lights: list[MockLight],
) -> AsyncGenerator[dict[str, Any]]:
    """Set up basic light group with area starting BRIGHT (for timing-sensitive tests).

    This fixture creates sensors, initializes integration, THEN sets dark sensor to bright.
    This avoids entity initialization overwriting the manually-set state.
    """
    from homeassistant.const import STATE_ON

    # Create sensors
    motion_sensor = MockBinarySensor(
        name="motion_sensor",
        unique_id="motion_sensor",
        device_class=BinarySensorDeviceClass.MOTION,
    )

    dark_sensor = MockBinarySensor(
        name="dark_sensor",
        unique_id="dark_sensor",
        device_class=BinarySensorDeviceClass.LIGHT,
    )

    # Register sensors
    await setup_mock_entities(
        hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [motion_sensor, dark_sensor]}
    )

    # Initialize integration FIRST - entities get their default states
    await init_integration(hass, [light_group_basic_config_entry])
    await hass.async_block_till_done()

    # Wait for initial setup
    await asyncio.sleep(0.5)

    # NOW set dark sensor to ON (bright) - after integration is running
    # This way the aggregate sensor will react to the state change
    hass.states.async_set(
        dark_sensor.entity_id,
        STATE_ON,
        {"device_class": BinarySensorDeviceClass.LIGHT, "friendly_name": "dark_sensor"},
    )
    await hass.async_block_till_done()

    # Wait for aggregate sensor to update
    await asyncio.sleep(0.5)
    await hass.async_block_till_done()

    await enable_light_control(hass, DEFAULT_MOCK_AREA.value)

    yield {
        "config_entry": light_group_basic_config_entry,
        "lights": setup_test_lights,
        "motion_sensor": motion_sensor,
        "dark_sensor": dark_sensor,  # Include for tests to flip to dark
        "light_group_id": f"light.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_test_group",
        "area_state_id": f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state",
        "light_control_id": f"switch.magic_areas_light_groups_{DEFAULT_MOCK_AREA.value}_light_control",
    }

    await shutdown_integration(hass, [light_group_basic_config_entry])
