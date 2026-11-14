"""Tests for the media player platform setup (groups and area-aware player)."""

from collections.abc import AsyncGenerator
import logging
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_IDLE, STATE_ON, STATE_PLAYING
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN, AreaStates, Features
from custom_components.magic_areas.const.area_aware_media_player import (
    AreaAwareMediaPlayerOptions,
)

from tests.const import DEFAULT_MOCK_AREA, MockAreaIds
from tests.helpers import (
    assert_in_attribute,
    assert_state,
    async_mock_service,
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
    trigger_occupancy,
)
from tests.mocks import MockBinarySensor, MockMediaPlayer

_LOGGER = logging.getLogger(__name__)

SLUG = DEFAULT_MOCK_AREA.value
GROUP_ID = (
    f"{MEDIA_PLAYER_DOMAIN}.magic_areas_media_player_groups_{SLUG}_media_player_group"
)
AAMP_ID = f"{MEDIA_PLAYER_DOMAIN}.magic_areas_area_aware_media_player_global"
PLAYER_ID = f"{MEDIA_PLAYER_DOMAIN}.setup_player"
AREA_STATE_ID = (
    f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{SLUG}_area_state"
)


def _aamp_options(devices: list[str]) -> dict:
    """Return area-aware media player options for the given notification devices."""
    return AreaAwareMediaPlayerOptions.to_config(
        {
            AreaAwareMediaPlayerOptions.NOTIFICATION_DEVICES.key: devices,
            AreaAwareMediaPlayerOptions.NOTIFICATION_STATES.key: [AreaStates.OCCUPIED],
        }
    )


def _entry(area: MockAreaIds, *feature_configs: dict, features=()) -> MockConfigEntry:
    """Build a config entry with the given features enabled."""
    data = get_basic_config_entry_data(area)
    merge_feature_config(data, *feature_configs)
    for feature in features:
        data["features"].setdefault(feature, {})
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="player")
async def fixture_player(hass: HomeAssistant) -> MockMediaPlayer:
    """Register one media player in the default area."""
    mock_player = MockMediaPlayer(name="setup_player", unique_id="setup_player")
    await setup_mock_entities(
        hass, MEDIA_PLAYER_DOMAIN, {DEFAULT_MOCK_AREA: [mock_player]}
    )
    return mock_player


@pytest.fixture(name="entries")
async def fixture_entries(hass: HomeAssistant) -> AsyncGenerator[list[MockConfigEntry]]:
    """Unload every entry registered by a test once it is done."""
    registered: list[MockConfigEntry] = []
    yield registered
    await shutdown_integration(hass, registered)


class TestMediaPlayerGroup:
    """Test the media player group creation."""

    async def test_group_contains_the_areas_media_players(
        self, hass: HomeAssistant, player, entries
    ):
        """Test the group is created and tracks the area's media players."""
        entry = _entry(DEFAULT_MOCK_AREA, features=[Features.MEDIA_PLAYER_GROUPS])
        entries.append(entry)
        await init_integration(hass, [entry])

        group_state = hass.states.get(GROUP_ID)
        assert group_state is not None
        assert_in_attribute(group_state, "entity_id", player.entity_id)

    async def test_no_group_without_media_players(self, hass: HomeAssistant, entries):
        """Test no group is created for an area without media players."""
        entry = _entry(DEFAULT_MOCK_AREA, features=[Features.MEDIA_PLAYER_GROUPS])
        entries.append(entry)
        await init_integration(hass, [entry])

        assert hass.states.get(GROUP_ID) is None


class TestAreaAwareMediaPlayerSetup:
    """Test which areas the global area-aware media player includes."""

    async def test_created_when_an_area_qualifies(
        self, hass: HomeAssistant, player, entries
    ):
        """Test the area-aware media player exists with a qualifying area."""
        area_entry = _entry(
            DEFAULT_MOCK_AREA,
            _aamp_options([player.entity_id]),
        )
        global_entry = _entry(MockAreaIds.GLOBAL)
        entries.extend([area_entry, global_entry])
        await init_integration(hass, [area_entry, global_entry])

        assert_state(hass.states.get(AAMP_ID), STATE_IDLE)

    async def test_area_without_the_feature_is_skipped(
        self, hass: HomeAssistant, player, entries, caplog
    ):
        """Test an area that did not enable the feature does not qualify."""
        area_entry = _entry(DEFAULT_MOCK_AREA)
        global_entry = _entry(MockAreaIds.GLOBAL)
        entries.extend([area_entry, global_entry])
        caplog.set_level(logging.DEBUG)
        await init_integration(hass, [area_entry, global_entry])

        assert hass.states.get(AAMP_ID) is None
        assert "Does not have Area-aware media player feature enabled" in caplog.text

    async def test_area_without_media_players_is_skipped(
        self, hass: HomeAssistant, entries, caplog
    ):
        """Test an area with the feature but no media players does not qualify."""
        area_entry = _entry(
            DEFAULT_MOCK_AREA, _aamp_options([f"{MEDIA_PLAYER_DOMAIN}.nowhere"])
        )
        global_entry = _entry(MockAreaIds.GLOBAL)
        entries.extend([area_entry, global_entry])
        caplog.set_level(logging.DEBUG)
        await init_integration(hass, [area_entry, global_entry])

        assert hass.states.get(AAMP_ID) is None
        assert "Has no media player entities" in caplog.text

    async def test_area_without_notification_devices_is_skipped(
        self, hass: HomeAssistant, player, entries, caplog
    ):
        """Test an area with the feature but no notification devices does not qualify."""
        area_entry = _entry(DEFAULT_MOCK_AREA, _aamp_options([]))
        global_entry = _entry(MockAreaIds.GLOBAL)
        entries.extend([area_entry, global_entry])
        caplog.set_level(logging.DEBUG)
        await init_integration(hass, [area_entry, global_entry])

        assert hass.states.get(AAMP_ID) is None
        assert "Has no notification devices" in caplog.text

    async def test_meta_areas_are_skipped(
        self, hass: HomeAssistant, player, entries, caplog
    ):
        """Test other meta areas never count towards the area-aware media player."""
        area_entry = _entry(
            DEFAULT_MOCK_AREA,
            _aamp_options([player.entity_id]),
        )
        interior_entry = _entry(MockAreaIds.INTERIOR)
        global_entry = _entry(MockAreaIds.GLOBAL)
        entries.extend([area_entry, interior_entry, global_entry])
        caplog.set_level(logging.DEBUG)
        await init_integration(hass, [area_entry, interior_entry, global_entry])

        assert hass.states.get(AAMP_ID) is not None
        assert "Is meta-area, skipping" in caplog.text


class TestAreaAwarePlayback:
    """Test how the area-aware media player routes playback."""

    @pytest.fixture(name="playback_calls")
    async def fixture_playback_calls(self, hass: HomeAssistant, player, entries):
        """Load a qualifying area plus Global and capture play_media calls."""
        motion = MockBinarySensor(
            name="playback_motion",
            unique_id="playback_motion",
            device_class=BinarySensorDeviceClass.MOTION,
        )
        await setup_mock_entities(
            hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [motion]}
        )
        area_entry = _entry(DEFAULT_MOCK_AREA, _aamp_options([player.entity_id]))
        global_entry = _entry(MockAreaIds.GLOBAL)
        entries.extend([area_entry, global_entry])
        await init_integration(hass, [area_entry, global_entry])

        calls = async_mock_service(
            hass=hass, domain=MEDIA_PLAYER_DOMAIN, service=SERVICE_PLAY_MEDIA
        )
        return {"calls": calls, "motion": motion}

    @staticmethod
    async def _play(hass: HomeAssistant) -> None:
        """Ask the area-aware media player to play something."""
        # The service is mocked on the media_player domain, so call the entity
        # directly through its platform instead of through the mocked service.
        entity = hass.data["media_player"].get_entity(AAMP_ID)
        await entity.async_play_media(MediaType.MUSIC, "42")

    async def test_nothing_plays_when_no_area_is_active(
        self, hass: HomeAssistant, playback_calls
    ):
        """Test playback is ignored while every area is clear."""
        await self._play(hass)

        assert playback_calls["calls"] == []

    async def test_playback_is_forwarded_to_the_active_areas_players(
        self, hass: HomeAssistant, player, playback_calls
    ):
        """Test playback goes to the media players of the occupied area."""
        await trigger_occupancy(hass, playback_calls["motion"], occupied=True)
        assert_state(hass.states.get(AREA_STATE_ID), STATE_ON)

        await self._play(hass)

        assert len(playback_calls["calls"]) == 1
        data = playback_calls["calls"][0].data
        assert data[ATTR_ENTITY_ID] == [player.entity_id]
        assert data[ATTR_MEDIA_CONTENT_ID] == "42"
        assert data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC

    async def test_area_in_sleep_is_skipped_unless_it_allows_sleep(
        self, hass: HomeAssistant, playback_calls
    ):
        """Test an area in sleep mode only receives playback if it opted in."""
        await trigger_occupancy(hass, playback_calls["motion"], occupied=True)
        area = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
        with patch.object(
            type(area),
            "has_state",
            lambda self, state: state in (AreaStates.SLEEP, AreaStates.OCCUPIED),
        ):
            await self._play(hass)

        assert playback_calls["calls"] == []

    async def test_area_without_a_state_entity_is_skipped(
        self, hass: HomeAssistant, playback_calls
    ):
        """Test an area whose presence sensor has no state cannot receive playback."""
        await trigger_occupancy(hass, playback_calls["motion"], occupied=True)
        hass.states.async_remove(AREA_STATE_ID)
        await hass.async_block_till_done()

        await self._play(hass)

        assert playback_calls["calls"] == []

    async def test_area_without_media_players_to_forward_is_ignored(
        self, hass: HomeAssistant, playback_calls
    ):
        """Test an active area with no notification devices forwards nothing."""
        await trigger_occupancy(hass, playback_calls["motion"], occupied=True)
        entity = hass.data["media_player"].get_entity(AAMP_ID)
        with patch.object(
            type(entity), "get_media_players_for_area", lambda self, area: set()
        ):
            await self._play(hass)

        assert playback_calls["calls"] == []

    async def test_set_state_updates_the_entity(
        self, hass: HomeAssistant, playback_calls
    ):
        """Test the entity reports an explicitly set state."""
        entity = hass.data["media_player"].get_entity(AAMP_ID)

        entity.set_state(STATE_PLAYING)
        await hass.async_block_till_done()

        assert_state(hass.states.get(AAMP_ID), STATE_PLAYING)
