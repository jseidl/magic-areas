"""Tests for the media player groups feature and its control switch."""

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
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import (
    DOMAIN,
    Features,
)

from tests.const import DEFAULT_MOCK_AREA, MockAreaIds
from tests.helpers import (
    assert_in_attribute,
    assert_state,
    async_advance_time,
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

AREA_STATE_ID = (
    f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{SLUG}_area_state"
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


MEDIA_PLAYER_CONTROL_ID = (
    f"{SWITCH_DOMAIN}.magic_areas_media_player_groups_{SLUG}_media_player_control"
)


MEDIA_PLAYER_GROUP_ID = (
    f"{MEDIA_PLAYER_DOMAIN}.magic_areas_media_player_groups_{SLUG}_media_player_group"
)


async def _setup_media_player_area(
    hass: HomeAssistant,
    *feature_configs: dict,
    area: MockAreaIds = DEFAULT_MOCK_AREA,
    features: list[str] | None = None,
) -> MockConfigEntry:
    """Enable the given features and load the integration."""
    data = get_basic_config_entry_data(area)
    merge_feature_config(data, *feature_configs)
    for feature in features or []:
        data["features"].setdefault(feature, {})
    config_entry = MockConfigEntry(domain=DOMAIN, data=data)
    await init_integration(hass, [config_entry], areas=[area])
    return config_entry


async def _turn_switch(hass: HomeAssistant, entity_id: str, on: bool) -> None:
    """Call the switch turn_on/turn_off service."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON if on else SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.fixture(name="config_entries_to_unload")
async def fixture_config_entries_to_unload(
    hass: HomeAssistant,
) -> AsyncGenerator[list[MockConfigEntry]]:
    """Unload every entry registered by a test once it is done."""
    entries: list[MockConfigEntry] = []
    yield entries
    await shutdown_integration(hass, entries)


@pytest.fixture(name="motion_sensor")
async def fixture_control_motion_sensor(hass: HomeAssistant) -> MockBinarySensor:
    """Register a motion sensor in the default area."""
    sensor = MockBinarySensor(
        name="motion",
        unique_id="switch_test_motion",
        device_class=BinarySensorDeviceClass.MOTION,
    )
    await setup_mock_entities(hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [sensor]})
    return sensor


class TestMediaPlayerControlSwitch:
    """Test the media player control switch."""

    @pytest.fixture(name="media_player_calls")
    async def fixture_media_player_calls(
        self, hass: HomeAssistant, motion_sensor, config_entries_to_unload
    ):
        """Set up a media player group and capture media_player.turn_off calls."""
        player = MockMediaPlayer(name="player", unique_id="switch_test_player")
        await setup_mock_entities(
            hass, MEDIA_PLAYER_DOMAIN, {DEFAULT_MOCK_AREA: [player]}
        )
        config_entries_to_unload.append(
            await _setup_media_player_area(
                hass, features=[Features.MEDIA_PLAYER_GROUPS]
            )
        )
        return async_mock_service(
            hass=hass, domain=MEDIA_PLAYER_DOMAIN, service=SERVICE_TURN_OFF
        )

    async def test_switch_defaults_to_off(
        self, hass: HomeAssistant, media_player_calls
    ):
        """Test the control switch exists and starts disabled."""
        assert_state(hass.states.get(MEDIA_PLAYER_CONTROL_ID), STATE_OFF)

    async def test_switch_can_be_toggled(self, hass: HomeAssistant, media_player_calls):
        """Test the base switch turns on and back off."""
        await _turn_switch(hass, MEDIA_PLAYER_CONTROL_ID, True)
        assert_state(hass.states.get(MEDIA_PLAYER_CONTROL_ID), STATE_ON)

        await _turn_switch(hass, MEDIA_PLAYER_CONTROL_ID, False)
        assert_state(hass.states.get(MEDIA_PLAYER_CONTROL_ID), STATE_OFF)

    async def test_area_clear_turns_media_players_off(
        self, hass: HomeAssistant, motion_sensor, media_player_calls
    ):
        """Test the group is turned off when the area clears and control is on."""
        await _turn_switch(hass, MEDIA_PLAYER_CONTROL_ID, True)

        await trigger_occupancy(hass, motion_sensor, occupied=True)
        assert media_player_calls == []

        await trigger_occupancy(hass, motion_sensor, occupied=False)
        await async_advance_time(hass)

        assert len(media_player_calls) == 1
        assert media_player_calls[0].data[ATTR_ENTITY_ID] == MEDIA_PLAYER_GROUP_ID

    async def test_disabled_control_does_nothing(
        self, hass: HomeAssistant, motion_sensor, media_player_calls
    ):
        """Test nothing is turned off while the control switch is off."""
        await trigger_occupancy(hass, motion_sensor, occupied=True)
        await trigger_occupancy(hass, motion_sensor, occupied=False)
        await async_advance_time(hass)

        assert media_player_calls == []


class TestMediaPlayerControlSetup:
    """Test when the media player control switch is created."""

    async def test_meta_areas_get_no_control_switch(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test the control switch is never created for a meta area."""
        config_entries_to_unload.append(
            await _setup_media_player_area(
                hass,
                features=[Features.MEDIA_PLAYER_GROUPS],
                area=MockAreaIds.INTERIOR,
            )
        )

        meta_switch_id = (
            f"{SWITCH_DOMAIN}.magic_areas_media_player_groups_interior_"
            "media_player_control"
        )
        assert hass.states.get(meta_switch_id) is None

    async def test_creation_error_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test a failing control switch is logged and the area still loads."""
        with patch(
            "custom_components.magic_areas.switch.MediaPlayerControlSwitch",
            side_effect=RuntimeError("boom"),
        ):
            config_entries_to_unload.append(
                await _setup_media_player_area(
                    hass, features=[Features.MEDIA_PLAYER_GROUPS]
                )
            )

        assert "Error loading media player control switch: boom" in caplog.text
        assert hass.states.get(AREA_STATE_ID) is not None
