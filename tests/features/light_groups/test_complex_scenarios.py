"""Tests for complex multi-step integration scenarios.

These tests verify complete workflows from start to finish.
"""

import asyncio

from homeassistant.const import STATE_OFF, STATE_ON

from custom_components.magic_areas.const import AreaStates

from tests.features.light_groups.conftest import create_magic_context
from tests.helpers import (
    assert_in_attribute,
    assert_state,
    trigger_occupancy,
    trigger_secondary_state,
)


class TestComplexScenarios:
    """Test complex multi-step integration scenarios."""

    async def test_full_room_scenario(self, hass, setup_basic_light_group):
        """Test full room scenario: enter dark room → lights on → leave → lights off."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]
        area_state_id = setup_basic_light_group["area_state_id"]

        # Step 1: Enter room (dark by default with aggregate sensor OFF)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Verify area is occupied and dark
        area_state = hass.states.get(area_state_id)
        assert_state(area_state, STATE_ON)
        assert_in_attribute(area_state, "states", AreaStates.OCCUPIED)
        assert_in_attribute(area_state, "states", AreaStates.DARK)

        # Verify lights turned on
        assert_state(hass.states.get(light_group_id), STATE_ON)

        # Step 2: Leave room
        await trigger_occupancy(hass, motion_sensor, occupied=False)

        # Verify area is clear
        area_state = hass.states.get(area_state_id)
        assert_state(area_state, STATE_OFF)

        # Verify lights turned off
        assert_state(hass.states.get(light_group_id), STATE_OFF)

    async def test_sleep_mode_scenario(
        self, hass, setup_sleep_light_group, setup_all_binary_sensors
    ):
        """Test sleep mode: area occupied → sleep activates → sleep lights on."""
        light_group_id = setup_sleep_light_group["light_group_id"]
        motion_sensor = setup_all_binary_sensors["motion"]
        sleep_sensor = setup_all_binary_sensors["sleep"]
        area_state_id = setup_sleep_light_group["area_state_id"]

        # Step 1: Area becomes occupied (no sleep yet)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Verify area is occupied
        area_state = hass.states.get(area_state_id)
        assert_state(area_state, STATE_ON)
        assert_in_attribute(area_state, "states", AreaStates.OCCUPIED)

        # Sleep lights should NOT be on yet (no sleep state)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

        # Step 2: Sleep mode activates
        await trigger_secondary_state(hass, sleep_sensor, active=True)

        # Verify sleep state added
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, "states", AreaStates.SLEEP)

        # Sleep lights should now turn on
        assert_state(hass.states.get(light_group_id), STATE_ON)

        # Step 3: Wake up - sleep mode deactivates
        await trigger_secondary_state(hass, sleep_sensor, active=False)

        # Verify sleep state removed
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, "states", AreaStates.SLEEP, negate=True)

        # Sleep lights turn off (lost sleep state)
        assert_state(hass.states.get(light_group_id), STATE_OFF)

    async def test_manual_override_then_automatic_resume(
        self, hass, setup_basic_light_group
    ):
        """Test manual override → leave → return → automatic control resumed."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Step 1: Enter room, lights turn on automatically
        await trigger_occupancy(hass, motion_sensor, occupied=True)
        assert_state(hass.states.get(light_group_id), STATE_ON)

        # Step 2: User manually turns off lights (without magic context)
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # Lights are off, manual mode active
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)
        assert light_state.attributes.get("mode") == "manual"

        # Step 3: Leave room
        await trigger_occupancy(hass, motion_sensor, occupied=False)

        # Lights remain off, manual mode should be reset to automatic (magic)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)
        assert light_state.attributes.get("mode") == "magic"

        # Step 4: Return to room
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Automatic control resumed - lights turn on
        assert_state(hass.states.get(light_group_id), STATE_ON)

    async def test_programmatic_control_preserves_auto_mode(
        self, hass, setup_basic_light_group
    ):
        """Test that programmatic control with magic context doesn't enter manual mode."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Occupy area
        await trigger_occupancy(hass, motion_sensor, occupied=True)
        assert_state(hass.states.get(light_group_id), STATE_ON)

        # Turn off lights WITH magic context (programmatic)
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": light_group_id},
            blocking=True,
            context=create_magic_context(),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # Lights are off, but should STILL be in automatic mode (not manual)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)
        # With magic context, should remain in magic mode (not enter manual)
        assert light_state.attributes.get("mode") == "magic"

        # Re-triggering occupancy should turn lights back on
        await trigger_occupancy(hass, motion_sensor, occupied=False)
        await asyncio.sleep(0.2)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Lights should turn on (still in auto mode)
        assert_state(hass.states.get(light_group_id), STATE_ON)
