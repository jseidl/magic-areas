"""Test for aggregate (group) sensor behavior."""

from collections.abc import AsyncGenerator
import logging
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.assist_satellite.const import (
    DOMAIN as ASSIST_SATELLITE_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_STOP,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import (
    ATTR_STATES,
    CONF_ENABLED_FEATURES,
    CONF_FEATURE_AREA_AWARE_MEDIA_PLAYER,
    CONF_NOTIFICATION_DEVICES,
    CONF_NOTIFY_STATES,
    CONF_ROUTE_NOTIFICATIONS_TO_SATELLITES,
    DOMAIN,
    AreaStates,
)

from tests.const import DEFAULT_MOCK_AREA, MockAreaIds
from tests.helpers import (
    assert_in_attribute,
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor, MockMediaPlayer

_LOGGER = logging.getLogger(__name__)


# Fixtures


@pytest.fixture(name="area_aware_media_player_global_config_entry")
def mock_config_entry_area_aware_media_player_global() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(MockAreaIds.GLOBAL)
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="area_aware_media_player_area_config_entry")
def mock_config_entry_area_aware_media_player_area() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        {
            CONF_ENABLED_FEATURES: {
                CONF_FEATURE_AREA_AWARE_MEDIA_PLAYER: {
                    CONF_NOTIFICATION_DEVICES: ["media_player.media_player_1"],
                    CONF_NOTIFY_STATES: [AreaStates.OCCUPIED],
                }
            }
        }
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="area_aware_media_player_satellite_config_entry")
def mock_config_entry_area_aware_media_player_satellite() -> MockConfigEntry:
    """Fixture for mock configuration entry with satellite routing enabled."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update(
        {
            CONF_ENABLED_FEATURES: {
                CONF_FEATURE_AREA_AWARE_MEDIA_PLAYER: {
                    CONF_NOTIFICATION_DEVICES: ["media_player.media_player_1"],
                    CONF_NOTIFY_STATES: [AreaStates.OCCUPIED],
                    CONF_ROUTE_NOTIFICATIONS_TO_SATELLITES: True,
                }
            }
        }
    )
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_area_aware_media_player")
async def setup_integration_area_aware_media_player(
    hass: HomeAssistant,
    area_aware_media_player_global_config_entry: MockConfigEntry,
    area_aware_media_player_area_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with secondary states config."""

    await init_integration(
        hass,
        [
            area_aware_media_player_area_config_entry,
            area_aware_media_player_global_config_entry,
        ],
    )
    yield
    await shutdown_integration(
        hass,
        [
            area_aware_media_player_area_config_entry,
            area_aware_media_player_global_config_entry,
        ],
    )


# Entities


@pytest.fixture(name="entities_media_player_single")
async def setup_entities_media_player_single(
    hass: HomeAssistant,
) -> list[MockMediaPlayer]:
    """Create multiple mock sensor and setup the system with it."""

    mock_media_player_entities = []

    mock_media_player_entities.append(
        MockMediaPlayer(name="media_player_1", unique_id="media_player_1")
    )
    await setup_mock_entities(
        hass, MEDIA_PLAYER_DOMAIN, {DEFAULT_MOCK_AREA: mock_media_player_entities}
    )
    return mock_media_player_entities


# Tests


async def test_area_aware_media_player(
    hass: HomeAssistant,
    entities_media_player_single: list[MockMediaPlayer],
    entities_binary_sensor_motion_one: list[MockBinarySensor],
    _setup_integration_area_aware_media_player: AsyncGenerator[Any, None],
) -> None:
    """Test the area aware media player."""

    area_aware_media_player_id = (
        f"{MEDIA_PLAYER_DOMAIN}.magic_areas_area_aware_media_player_global"
    )

    area_sensor_entity_id = (
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_kitchen_area_state"
    )
    motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id

    # Initialization tests

    # Mock media player
    media_player_state = hass.states.get(entities_media_player_single[0].entity_id)
    assert_state(media_player_state, STATE_OFF)

    # Area-Aware media player
    area_aware_media_player_state = hass.states.get(area_aware_media_player_id)
    assert_state(area_aware_media_player_state, STATE_IDLE)

    # Test area clear

    # Ensure area is clear
    area_state = hass.states.get(area_sensor_entity_id)
    assert_state(area_state, STATE_OFF)

    # Send play to AAMP
    service_data = {
        ATTR_ENTITY_ID: area_aware_media_player_id,
        ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
        ATTR_MEDIA_CONTENT_ID: 42,
    }
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA, service_data
    )
    await hass.async_block_till_done()

    # Ensure area MP & AAMP is NOT playing
    media_player_state = hass.states.get(entities_media_player_single[0].entity_id)
    assert_state(media_player_state, STATE_OFF)

    area_aware_media_player_state = hass.states.get(area_aware_media_player_id)
    assert_state(area_aware_media_player_state, STATE_IDLE)

    # Test area occupied

    # Ensure area is occupied
    # Turn on motion sensor
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    area_binary_sensor = hass.states.get(area_sensor_entity_id)
    motion_sensor = hass.states.get(motion_sensor_entity_id)

    assert_state(motion_sensor, STATE_ON)
    assert_state(area_binary_sensor, STATE_ON)
    assert_in_attribute(area_binary_sensor, ATTR_STATES, AreaStates.OCCUPIED)

    # Send play to AAMP
    service_data = {
        ATTR_ENTITY_ID: area_aware_media_player_id,
        ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
        ATTR_MEDIA_CONTENT_ID: 42,
    }
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA, service_data
    )
    await hass.async_block_till_done()

    # Ensure area MP is playing
    media_player_state = hass.states.get(entities_media_player_single[0].entity_id)
    assert_state(media_player_state, STATE_PLAYING)

    area_aware_media_player_state = hass.states.get(area_aware_media_player_id)
    assert_state(area_aware_media_player_state, STATE_IDLE)

    # Turn off area MP
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: entities_media_player_single[0].entity_id},
    )
    await hass.async_block_till_done()

    # Ensure area MP is stopped
    media_player_state = hass.states.get(entities_media_player_single[0].entity_id)
    assert_state(media_player_state, STATE_IDLE)

    # Test area occupied + sleep

    # Ensure area is occupied + sleep

    # Send play to AAMP

    # Ensure area MP is NOT playing

    # Turn off AAMP


class MockAssistSatellite:
    """Mock assist satellite entity."""

    def __init__(self, entity_id: str, area_id: str = None):
        """Initialize mock satellite."""
        self.entity_id = entity_id
        self.attributes = {"area_id": area_id} if area_id else {}


async def test_satellite_auto_discovery(
    hass: HomeAssistant,
    area_aware_media_player_satellite_config_entry: MockConfigEntry,
    area_aware_media_player_global_config_entry: MockConfigEntry,
) -> None:
    """Test satellite auto-discovery by area assignment."""

    # Create mock assist satellite assigned to kitchen area
    mock_satellite = MockAssistSatellite(
        "assist_satellite.kitchen_satellite", DEFAULT_MOCK_AREA
    )

    # Mock the hass.states.async_all method to return our mock satellite
    def mock_async_all(domain):
        if domain == ASSIST_SATELLITE_DOMAIN:
            return [mock_satellite]
        return []

    hass.states.async_all = mock_async_all

    await init_integration(
        hass,
        [
            area_aware_media_player_satellite_config_entry,
            area_aware_media_player_global_config_entry,
        ],
    )

    # Test that satellite is discovered
    area_aware_mp = hass.data[DOMAIN][
        area_aware_media_player_satellite_config_entry.entry_id
    ]["area"]
    satellites = area_aware_mp.entities[MEDIA_PLAYER_DOMAIN][
        0
    ].get_assist_satellites_for_area(area_aware_mp)

    assert "assist_satellite.kitchen_satellite" in satellites


async def test_notification_routing_to_satellites(
    hass: HomeAssistant,
    entities_media_player_single: list,
    entities_binary_sensor_motion_one: list,
    area_aware_media_player_satellite_config_entry: MockConfigEntry,
    area_aware_media_player_global_config_entry: MockConfigEntry,
) -> None:
    """Test notification content routing to satellites."""

    # Mock assist satellite service
    satellite_calls = []

    async def mock_satellite_announce(domain, service, data):
        if domain == "assist_satellite" and service == "announce":
            satellite_calls.append(data)

    hass.services.async_call = mock_satellite_announce
    hass.services.has_service = (
        lambda domain, service: domain == "assist_satellite" and service == "announce"
    )

    # Create mock satellite
    mock_satellite = MockAssistSatellite(
        "assist_satellite.kitchen_satellite", DEFAULT_MOCK_AREA
    )
    hass.states.async_all = lambda domain: (
        [mock_satellite] if domain == ASSIST_SATELLITE_DOMAIN else []
    )

    await init_integration(
        hass,
        [
            area_aware_media_player_satellite_config_entry,
            area_aware_media_player_global_config_entry,
        ],
    )

    # Activate area
    motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    area_aware_media_player_id = (
        f"{MEDIA_PLAYER_DOMAIN}.magic_areas_area_aware_media_player_global"
    )

    # Test TTS content (should go to satellite)
    service_data = {
        ATTR_ENTITY_ID: area_aware_media_player_id,
        ATTR_MEDIA_CONTENT_TYPE: "tts",
        ATTR_MEDIA_CONTENT_ID: "Kitchen timer finished",
    }
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA, service_data
    )
    await hass.async_block_till_done()

    # Verify satellite was called
    assert len(satellite_calls) == 1
    assert satellite_calls[0]["message"] == "Kitchen timer finished"
    assert satellite_calls[0][ATTR_ENTITY_ID] == "assist_satellite.kitchen_satellite"


async def test_media_routing_to_players(
    hass: HomeAssistant,
    entities_media_player_single: list,
    entities_binary_sensor_motion_one: list,
    area_aware_media_player_satellite_config_entry: MockConfigEntry,
    area_aware_media_player_global_config_entry: MockConfigEntry,
) -> None:
    """Test media content routing to media players (not satellites)."""

    # Track media player calls
    media_player_calls = []

    async def mock_media_player_service(domain, service, data):
        if domain == MEDIA_PLAYER_DOMAIN and service == SERVICE_PLAY_MEDIA:
            media_player_calls.append(data)

    hass.services.async_call = mock_media_player_service

    # Create mock satellite
    mock_satellite = MockAssistSatellite(
        "assist_satellite.kitchen_satellite", DEFAULT_MOCK_AREA
    )
    hass.states.async_all = lambda domain: (
        [mock_satellite] if domain == ASSIST_SATELLITE_DOMAIN else []
    )

    await init_integration(
        hass,
        [
            area_aware_media_player_satellite_config_entry,
            area_aware_media_player_global_config_entry,
        ],
    )

    # Activate area
    motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    area_aware_media_player_id = (
        f"{MEDIA_PLAYER_DOMAIN}.magic_areas_area_aware_media_player_global"
    )

    # Test music content (should go to media player)
    service_data = {
        ATTR_ENTITY_ID: area_aware_media_player_id,
        ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
        ATTR_MEDIA_CONTENT_ID: "spotify:playlist:123",
    }
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA, service_data
    )
    await hass.async_block_till_done()

    # Verify media player was called (not satellite)
    assert len(media_player_calls) == 1
    assert "media_player.media_player_1" in media_player_calls[0][ATTR_ENTITY_ID]


async def test_satellite_fallback_behavior(
    hass: HomeAssistant,
    entities_media_player_single: list,
    entities_binary_sensor_motion_one: list,
    area_aware_media_player_satellite_config_entry: MockConfigEntry,
    area_aware_media_player_global_config_entry: MockConfigEntry,
) -> None:
    """Test fallback to media players when satellites unavailable."""

    # Track all service calls
    service_calls = []

    async def mock_service_call(domain, service, data):
        service_calls.append({"domain": domain, "service": service, "data": data})

    hass.services.async_call = mock_service_call
    hass.services.has_service = (
        lambda domain, service: False
    )  # No satellite service available

    # No satellites available
    hass.states.async_all = lambda domain: []

    await init_integration(
        hass,
        [
            area_aware_media_player_satellite_config_entry,
            area_aware_media_player_global_config_entry,
        ],
    )

    # Activate area
    motion_sensor_entity_id = entities_binary_sensor_motion_one[0].entity_id
    hass.states.async_set(motion_sensor_entity_id, STATE_ON)
    await hass.async_block_till_done()

    area_aware_media_player_id = (
        f"{MEDIA_PLAYER_DOMAIN}.magic_areas_area_aware_media_player_global"
    )

    # Test TTS content (should fallback to media player)
    service_data = {
        ATTR_ENTITY_ID: area_aware_media_player_id,
        ATTR_MEDIA_CONTENT_TYPE: "tts",
        ATTR_MEDIA_CONTENT_ID: "Kitchen timer finished",
    }
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA, service_data
    )
    await hass.async_block_till_done()

    # Verify fallback to media player
    media_player_calls = [
        call for call in service_calls if call["domain"] == MEDIA_PLAYER_DOMAIN
    ]
    assert len(media_player_calls) == 1
    assert (
        "media_player.media_player_1" in media_player_calls[0]["data"][ATTR_ENTITY_ID]
    )
