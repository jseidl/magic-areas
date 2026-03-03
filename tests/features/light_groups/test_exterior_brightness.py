"""Tests for exterior brightness turn-off behavior."""

import asyncio

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from custom_components.magic_areas.const import AreaStates, MagicAreasEvents

from tests.helpers import assert_state, trigger_occupancy


class TestExteriorBrightness:
    """Test exterior brightness turn-off behavior."""

    async def test_exterior_bright_turns_off_lights(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that exterior becoming bright turns off lights."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied and dark, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Exterior area becomes bright (dispatch event)
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            "exterior",
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify lights turned off
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_exterior_bright_ignored_if_not_configured(
        self, hass: HomeAssistant, setup_no_exterior_light_group: dict
    ):
        """Test that exterior bright is ignored if not in TURN_OFF_WHEN."""
        light_group_id = setup_no_exterior_light_group["light_group_id"]
        motion_sensor = setup_no_exterior_light_group["motion_sensor"]

        # Make area occupied, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Exterior becomes bright
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            "exterior",
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify lights did NOT turn off (no EXTERIOR_BRIGHT in config)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_own_area_events_dont_trigger_exterior_logic(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that own area bright events don't trigger EXTERIOR_BRIGHT logic."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]
        area_id = setup_basic_light_group["config_entry"].data["id"]

        # Make area occupied and dark, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Own area becomes bright (not exterior) - dispatch as own area
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            area_id,
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Lights should stay ON (own area bright doesn't trigger exterior logic)
        # Note: Lights may turn off via STATE_LOSS if dark is required, but that's
        # a different mechanism - this test verifies exterior-specific logic doesn't fire
        light_state = hass.states.get(light_group_id)
        # In this case, lights stay on because DARK is not in assigned_states
        assert_state(light_state, STATE_ON)

    async def test_manual_mode_doesnt_block_exterior_bright(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that manual mode doesn't block exterior bright turn-off."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Enter manual mode by turning lights off
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Manually turn them back on
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify lights are on and in manual mode
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Exterior becomes bright (should still turn off despite manual mode)
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            "exterior",
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Manual mode doesn't block EXTERIOR_BRIGHT
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_exterior_dark_doesnt_turn_off(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that exterior becoming dark doesn't turn off lights."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Exterior becomes dark (not bright)
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            "exterior",
            ({AreaStates.DARK}, {AreaStates.BRIGHT}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Should NOT turn off (EXTERIOR_BRIGHT only triggers on bright)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_exterior_bright_with_multiple_states(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test exterior bright with multiple simultaneous state changes."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Exterior gains bright along with other states
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            "exterior",
            ({AreaStates.BRIGHT, AreaStates.EXTENDED}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Should still turn off (bright is in new_states)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)
