"""Tests for the media player groups feature and its control switch."""

import logging
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN, Features

from tests.const import DEFAULT_MOCK_AREA, MockAreaIds
from tests.features.media_player.helpers import (
    AREA_STATE_ID,
    GROUP_ID,
    SLUG,
    make_entry,
)
from tests.helpers import (
    assert_in_attribute,
    assert_state,
    async_advance_time,
    async_mock_service,
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    trigger_occupancy,
)
from tests.mocks import MockMediaPlayer

_LOGGER = logging.getLogger(__name__)


class TestMediaPlayerGroup:
    """Test the media player group creation."""

    async def test_group_contains_the_areas_media_players(
        self, hass: HomeAssistant, player, config_entries_to_unload
    ):
        """Test the group is created and tracks the area's media players."""
        entry = make_entry(DEFAULT_MOCK_AREA, features=[Features.MEDIA_PLAYER_GROUPS])
        config_entries_to_unload.append(entry)
        await init_integration(hass, [entry])

        group_state = hass.states.get(GROUP_ID)
        assert group_state is not None
        assert_in_attribute(group_state, "entity_id", player.entity_id)

    async def test_no_group_without_media_players(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test no group is created for an area without media players."""
        entry = make_entry(DEFAULT_MOCK_AREA, features=[Features.MEDIA_PLAYER_GROUPS])
        config_entries_to_unload.append(entry)
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
