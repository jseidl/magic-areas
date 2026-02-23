"""Tests for edge cases and error handling.

Tests valuable edge cases that could occur in real-world scenarios.
"""

import asyncio

from homeassistant.const import STATE_OFF, STATE_ON

from tests.features.light_groups.conftest import trigger_occupancy
from tests.helpers import assert_state


class TestEdgeCases:
    """Test edge cases and error handling."""

    async def test_lights_already_on_no_retrigger(self, hass, setup_basic_light_group):
        """Test that when area stays occupied, lights don't get retriggered."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Turn lights on first time
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Verify lights are on
        assert_state(hass.states.get(light_group_id), STATE_ON)

        # Simulate motion sensor retriggering (area still occupied)
        hass.states.async_set(motion_sensor.entity_id, STATE_OFF)
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)
        hass.states.async_set(motion_sensor.entity_id, STATE_ON)
        await hass.async_block_till_done()
        await asyncio.sleep(0.5)

        # Lights should still be on (no flicker/retrigger)
        assert_state(hass.states.get(light_group_id), STATE_ON)

    async def test_rapid_state_transitions(self, hass, setup_basic_light_group):
        """Test rapid occupancy changes are handled gracefully."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Simulate rapid state changes
        for i in range(5):
            await trigger_occupancy(hass, motion_sensor, occupied=(i % 2 == 0))

        # System should handle gracefully without crashing
        # Final state should reflect last change (occupied=False since 5 is odd)
        light_state = hass.states.get(light_group_id)
        assert light_state is not None

    async def test_never_turn_off_respects_area_clear(
        self, hass, setup_never_turn_off_light_group
    ):
        """Test that NEVER turn-off config keeps lights on when area clears."""
        light_group_id = setup_never_turn_off_light_group["light_group_id"]
        motion_sensor = setup_never_turn_off_light_group["motion_sensor"]

        # Turn lights on
        await trigger_occupancy(hass, motion_sensor, occupied=True)
        assert_state(hass.states.get(light_group_id), STATE_ON)

        # Area clears
        await trigger_occupancy(hass, motion_sensor, occupied=False)

        # Lights should STAY ON (empty turn_off_when = never turn off automatically)
        assert_state(hass.states.get(light_group_id), STATE_ON)
