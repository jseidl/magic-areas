"""Tests for the switch platform (control switches and presence hold)."""

from collections.abc import AsyncGenerator
import logging
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache,
)

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from custom_components.magic_areas.const import DOMAIN, Features
from custom_components.magic_areas.const.presence_hold import PresenceHoldOptions

from tests.const import DEFAULT_MOCK_AREA, MockAreaIds
from tests.helpers import (
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
MEDIA_PLAYER_CONTROL_ID = (
    f"{SWITCH_DOMAIN}.magic_areas_media_player_groups_{SLUG}_media_player_control"
)
MEDIA_PLAYER_GROUP_ID = (
    f"{MEDIA_PLAYER_DOMAIN}.magic_areas_media_player_groups_{SLUG}_media_player_group"
)
PRESENCE_HOLD_ID = f"{SWITCH_DOMAIN}.magic_areas_presence_hold_{SLUG}"
AREA_STATE_ID = (
    f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_{SLUG}_area_state"
)
MODULE = "custom_components.magic_areas.switch"


async def _setup(
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


async def _turn(hass: HomeAssistant, entity_id: str, on: bool) -> None:
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
async def fixture_motion_sensor(hass: HomeAssistant) -> MockBinarySensor:
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
            await _setup(hass, features=[Features.MEDIA_PLAYER_GROUPS])
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
        await _turn(hass, MEDIA_PLAYER_CONTROL_ID, True)
        assert_state(hass.states.get(MEDIA_PLAYER_CONTROL_ID), STATE_ON)

        await _turn(hass, MEDIA_PLAYER_CONTROL_ID, False)
        assert_state(hass.states.get(MEDIA_PLAYER_CONTROL_ID), STATE_OFF)

    async def test_area_clear_turns_media_players_off(
        self, hass: HomeAssistant, motion_sensor, media_player_calls
    ):
        """Test the group is turned off when the area clears and control is on."""
        await _turn(hass, MEDIA_PLAYER_CONTROL_ID, True)

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


class TestPresenceHoldSwitch:
    """Test the resettable presence hold switch."""

    async def test_turn_on_and_off_without_timeout(
        self, hass: HomeAssistant, motion_sensor, config_entries_to_unload
    ):
        """Test presence hold keeps the area occupied until it is turned off."""
        config_entries_to_unload.append(
            await _setup(hass, PresenceHoldOptions.to_config({}))
        )
        assert_state(hass.states.get(PRESENCE_HOLD_ID), STATE_OFF)

        await _turn(hass, PRESENCE_HOLD_ID, True)
        assert_state(hass.states.get(PRESENCE_HOLD_ID), STATE_ON)
        assert_state(hass.states.get(AREA_STATE_ID), STATE_ON)

        await _turn(hass, PRESENCE_HOLD_ID, False)
        await async_advance_time(hass)
        assert_state(hass.states.get(PRESENCE_HOLD_ID), STATE_OFF)
        assert_state(hass.states.get(AREA_STATE_ID), STATE_OFF)

    async def test_turns_itself_off_after_timeout(
        self, hass: HomeAssistant, motion_sensor, config_entries_to_unload
    ):
        """Test presence hold turns off by itself once its timeout elapses."""
        config_entries_to_unload.append(
            await _setup(
                hass,
                PresenceHoldOptions.to_config({PresenceHoldOptions.TIMEOUT.key: 1}),
            )
        )

        await _turn(hass, PRESENCE_HOLD_ID, True)
        assert_state(hass.states.get(PRESENCE_HOLD_ID), STATE_ON)

        await async_advance_time(hass, seconds=61)

        assert_state(hass.states.get(PRESENCE_HOLD_ID), STATE_OFF)

    async def test_manual_turn_off_cancels_the_timeout(
        self, hass: HomeAssistant, motion_sensor, config_entries_to_unload
    ):
        """Test turning presence hold off by hand discards its pending timeout."""
        config_entries_to_unload.append(
            await _setup(
                hass,
                PresenceHoldOptions.to_config({PresenceHoldOptions.TIMEOUT.key: 1}),
            )
        )

        await _turn(hass, PRESENCE_HOLD_ID, True)
        await _turn(hass, PRESENCE_HOLD_ID, False)
        await _turn(hass, PRESENCE_HOLD_ID, True)

        # The first timeout was cancelled, so a minute later it is still held.
        await async_advance_time(hass, seconds=30)
        assert_state(hass.states.get(PRESENCE_HOLD_ID), STATE_ON)

    async def test_unloading_cancels_a_pending_timeout(
        self, hass: HomeAssistant, motion_sensor, caplog
    ):
        """Test removing the switch while it is holding leaves no timer behind."""
        config_entry = await _setup(
            hass, PresenceHoldOptions.to_config({PresenceHoldOptions.TIMEOUT.key: 1})
        )

        await _turn(hass, PRESENCE_HOLD_ID, True)
        await shutdown_integration(hass, [config_entry])

        await async_advance_time(hass, seconds=61)

        assert "Traceback" not in caplog.text
        assert "Error" not in caplog.text


class TestSwitchPlatformSetup:
    """Test which control switches the platform creates."""

    @pytest.mark.parametrize(
        ("feature", "switch_id"),
        [
            (
                Features.PRESENCE_HOLD,
                f"{SWITCH_DOMAIN}.magic_areas_presence_hold_interior",
            ),
            (
                Features.LIGHT_GROUPS,
                f"{SWITCH_DOMAIN}.magic_areas_light_groups_interior_light_control",
            ),
            (
                Features.MEDIA_PLAYER_GROUPS,
                f"{SWITCH_DOMAIN}.magic_areas_media_player_groups_interior_media_player_control",
            ),
            (
                Features.FAN_GROUPS,
                f"{SWITCH_DOMAIN}.magic_areas_fan_groups_interior_fan_control",
            ),
        ],
    )
    async def test_meta_areas_get_no_control_switches(
        self,
        hass: HomeAssistant,
        config_entries_to_unload,
        feature: str,
        switch_id: str,
    ):
        """Test per-area control switches are never created for meta areas."""
        config_entries_to_unload.append(
            await _setup(
                hass,
                features=[feature, Features.AGGREGATION],
                area=MockAreaIds.INTERIOR,
            )
        )

        assert hass.states.get(switch_id) is None

    async def test_fan_control_requires_aggregates(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test fan groups without Aggregates warns and creates no control switch."""
        config_entries_to_unload.append(
            await _setup(hass, features=[Features.FAN_GROUPS])
        )

        fan_control_id = f"{SWITCH_DOMAIN}.magic_areas_fan_groups_{SLUG}_fan_control"
        assert hass.states.get(fan_control_id) is None
        assert "Fan Groups feature requires Aggregates feature" in caplog.text

    @pytest.mark.parametrize(
        ("feature", "switch_class", "log_text"),
        [
            (
                Features.PRESENCE_HOLD,
                "PresenceHoldSwitch",
                "Error loading presence hold switch",
            ),
            (
                Features.LIGHT_GROUPS,
                "LightControlSwitch",
                "Error loading light control switch",
            ),
            (
                Features.MEDIA_PLAYER_GROUPS,
                "MediaPlayerControlSwitch",
                "Error loading media player control switch",
            ),
            (
                Features.FAN_GROUPS,
                "FanControlSwitch",
                "Error loading fan control switch",
            ),
        ],
    )
    async def test_switch_creation_errors_are_contained(
        self,
        hass: HomeAssistant,
        config_entries_to_unload,
        caplog,
        *,
        feature: str,
        switch_class: str,
        log_text: str,
    ):
        """Test a switch that fails to build is logged and does not stop the rest."""
        with patch(f"{MODULE}.{switch_class}", side_effect=RuntimeError("boom")):
            config_entries_to_unload.append(
                await _setup(hass, features=[feature, Features.AGGREGATION])
            )

        assert f"{log_text}: boom" in caplog.text
        # The area itself still loads.
        assert hass.states.get(AREA_STATE_ID) is not None

    async def test_climate_control_without_entity_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test climate control without a climate entity logs and creates no switch."""
        config_entries_to_unload.append(
            await _setup(hass, features=[Features.CLIMATE_CONTROL])
        )

        climate_control_id = f"{SWITCH_DOMAIN}.magic_areas_climate_control_{SLUG}"
        assert hass.states.get(climate_control_id) is None
        assert "Error loading climate control switch: Climate entity not set" in (
            caplog.text
        )
        assert hass.states.get(AREA_STATE_ID) is not None

    async def test_disabling_a_feature_removes_its_switch(
        self, hass: HomeAssistant, motion_sensor
    ):
        """Test a switch is removed from the registry once its feature is disabled."""
        config_entry = await _setup(hass, features=[Features.PRESENCE_HOLD])
        registry = er.async_get(hass)
        assert registry.async_get(PRESENCE_HOLD_ID) is not None

        data = dict(config_entry.data)
        data["features"] = {}
        hass.config_entries.async_update_entry(config_entry, data=data)
        await hass.async_block_till_done()

        assert registry.async_get(PRESENCE_HOLD_ID) is None
        assert hass.states.get(PRESENCE_HOLD_ID) is None

        await shutdown_integration(hass, [config_entry])


class TestSwitchStateRestore:
    """Test control switches restore their state after a restart."""

    @pytest.mark.parametrize("restored", [STATE_ON, STATE_OFF])
    async def test_switch_restores_previous_state(
        self,
        hass: HomeAssistant,
        motion_sensor,
        config_entries_to_unload,
        restored: str,
    ):
        """Test the switch comes back in the state it was last in."""
        mock_restore_cache(hass, [State(PRESENCE_HOLD_ID, restored)])

        config_entries_to_unload.append(
            await _setup(hass, features=[Features.PRESENCE_HOLD])
        )

        assert_state(hass.states.get(PRESENCE_HOLD_ID), restored)
