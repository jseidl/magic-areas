"""Tests for the presence hold feature."""

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache,
)

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
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
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    shutdown_integration,
)

SLUG = DEFAULT_MOCK_AREA.value


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


class TestPresenceHoldStateRestore:
    """Test presence hold restores its state after a restart."""

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


class TestPresenceHoldSetup:
    """Test when the presence hold switch is created."""

    async def test_meta_areas_get_no_presence_hold_switch(
        self, hass: HomeAssistant, config_entries_to_unload
    ):
        """Test presence hold is never created for a meta area."""
        config_entries_to_unload.append(
            await _setup(
                hass,
                features=[Features.PRESENCE_HOLD],
                area=MockAreaIds.INTERIOR,
            )
        )

        meta_switch_id = f"{SWITCH_DOMAIN}.magic_areas_presence_hold_interior"
        assert hass.states.get(meta_switch_id) is None

    async def test_switch_creation_error_is_contained(
        self, hass: HomeAssistant, config_entries_to_unload, caplog
    ):
        """Test a failing presence hold switch is logged and the area still loads."""
        with patch(f"{MODULE}.PresenceHoldSwitch", side_effect=RuntimeError("boom")):
            config_entries_to_unload.append(
                await _setup(hass, features=[Features.PRESENCE_HOLD])
            )

        assert "Error loading presence hold switch: boom" in caplog.text
        assert hass.states.get(AREA_STATE_ID) is not None

    async def test_disabling_the_feature_removes_the_switch(
        self, hass: HomeAssistant, motion_sensor
    ):
        """Test the switch is removed from the registry once the feature is disabled."""
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
