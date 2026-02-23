"""Tests for darkness requirement checks."""

import asyncio

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from custom_components.magic_areas.const import AreaStates, MagicAreasEvents

from tests.features.light_groups.conftest import (
    trigger_occupancy,
    trigger_secondary_state,
)
from tests.helpers import assert_state


class TestDarknessRequirement:
    """Test darkness requirement logic."""

    async def test_require_dark_true_checks_for_dark_state(
        self,
        hass: HomeAssistant,
        setup_basic_light_group_bright: dict,
    ):
        """Test that REQUIRE_DARK=True blocks turn-on when bright, AREA_DARK trigger turns on when dark.

        This test demonstrates:
        1. require_dark=True is a CONDITION that blocks turn-on when area is bright
        2. AREA_DARK is a TRIGGER that fires when area becomes dark
        3. Both work together: trigger fires + condition passes = lights turn on
        """
        light_group_id = setup_basic_light_group_bright["light_group_id"]
        motion_sensor = setup_basic_light_group_bright["motion_sensor"]
        dark_sensor = setup_basic_light_group_bright["dark_sensor"]

        # Area is ALREADY bright from fixture setup (dark sensor ON)
        # Event: Area becomes occupied while bright (AREA_OCCUPIED trigger fires)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Verify lights DON'T turn on (require_dark=True condition blocks it)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

        # Now make area dark (turn dark sensor OFF = dark)
        # This fires the AREA_DARK trigger
        await trigger_secondary_state(hass, dark_sensor, active=False)

        # Verify lights NOW turn on (AREA_DARK trigger fired + require_dark condition passes)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_require_dark_false_bypasses_check(
        self, hass: HomeAssistant, setup_dark_optional_light_group: dict
    ):
        """Test that REQUIRE_DARK=False bypasses darkness check."""
        light_group_id = setup_dark_optional_light_group["light_group_id"]
        motion_sensor = setup_dark_optional_light_group["motion_sensor"]
        area_id = setup_dark_optional_light_group["config_entry"].data["id"]

        # Group has REQUIRE_DARK=False
        # Setup: Make area bright
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            area_id,
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Event: Area becomes occupied while bright
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Should turn on despite being bright
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_darkness_check_is_one_shot_at_turn_on(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that darkness is only checked once at turn-on time."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]
        area_id = setup_basic_light_group["config_entry"].data["id"]

        # Setup: Area becomes occupied and dark (lights turn on)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Lights should have turned on (area is dark by default)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Event: Area becomes bright (while still occupied)
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            area_id,
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Lights should stay ON (darkness is only checked at turn-on)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_no_feedback_loop_with_interior_lights(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that there's no feedback loop when interior lights affect brightness."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]
        area_id = setup_basic_light_group["config_entry"].data["id"]

        # This test verifies the one-shot darkness check prevents feedback
        # Setup: Turn lights on when dark
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Simulate interior lights making room bright
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            area_id,
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Lights should stay ON (no feedback loop)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_darkness_from_area_sensor(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test darkness check uses area states (area sensor)."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Area state system provides dark/bright
        # Setup: Area is occupied and dark (default state)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Should turn on (dark is in states)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_brightness_changes_after_turn_on_dont_affect_lights(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that brightness changes after lights are on don't trigger turn-off."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]
        area_id = setup_basic_light_group["config_entry"].data["id"]

        # Setup: Turn lights on when dark
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Multiple brightness oscillations
        for _ in range(3):
            # Becomes bright
            dispatcher_send(
                hass,
                MagicAreasEvents.AREA_STATE_CHANGED,
                area_id,
                ({AreaStates.BRIGHT}, {AreaStates.DARK}),
            )
            await hass.async_block_till_done()
            await asyncio.sleep(0.1)

            # Becomes dark again
            dispatcher_send(
                hass,
                MagicAreasEvents.AREA_STATE_CHANGED,
                area_id,
                ({AreaStates.DARK}, {AreaStates.BRIGHT}),
            )
            await hass.async_block_till_done()
            await asyncio.sleep(0.1)

        # Lights should stay ON through all oscillations
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)
