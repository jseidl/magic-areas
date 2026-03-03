"""Tests for light group trigger mechanisms."""

import asyncio

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from custom_components.magic_areas.const import AreaStates, MagicAreasEvents

from tests.features.light_groups.conftest import create_magic_context
from tests.helpers import assert_state, trigger_occupancy, trigger_secondary_state


class TestTriggers:
    """Test trigger mechanisms for light groups."""

    async def test_area_occupied_trigger_fires_on_transition(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test AREA_OCCUPIED trigger fires on clear→occupied transition."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Setup: Area is clear (initial state)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

        # Event: Area transitions to occupied
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Verify trigger fired (lights turned on)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_area_occupied_trigger_doesnt_fire_when_already_occupied(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test AREA_OCCUPIED trigger doesn't fire if already occupied."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Setup: Area becomes occupied first
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Event: Still occupied, but dispatch no state change
        area_id = setup_basic_light_group["config_entry"].data["id"]
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            area_id,
            (set(), set()),  # No new or lost states
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify lights stay on (no duplicate turn-on)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_state_gain_trigger_fires_when_gaining_configured_state(
        self,
        hass: HomeAssistant,
        setup_basic_light_group_bright: dict,
    ):
        """Test AREA_DARK trigger fires when area becomes dark while occupied.

        Note: This test uses AREA_DARK trigger, not STATE_GAIN. STATE_GAIN only applies
        to secondary states (sleep, user-defined), not brightness states (dark/bright).
        """
        light_group_id = setup_basic_light_group_bright["light_group_id"]
        motion_sensor = setup_basic_light_group_bright["motion_sensor"]
        dark_sensor = setup_basic_light_group_bright["dark_sensor"]

        # Area is ALREADY bright from fixture setup (dark sensor ON)
        # Make area occupied (but bright, so lights won't turn on due to require_dark)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Lights should NOT turn on (area is bright, require_dark=True blocks turn-on)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

        # Event: Area becomes dark (AREA_DARK trigger fires)
        await trigger_secondary_state(hass, dark_sensor, active=False)

        # Verify lights turned on via AREA_DARK trigger
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_state_gain_trigger_doesnt_fire_when_unoccupied(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test STATE_GAIN trigger doesn't fire if area is unoccupied."""
        light_group_id = setup_basic_light_group["light_group_id"]
        area_id = setup_basic_light_group["config_entry"].data["id"]

        # Setup: Area is clear (no occupancy)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

        # Event: Area gains dark state but stays clear
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            area_id,
            ({AreaStates.DARK}, {AreaStates.BRIGHT}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify trigger did NOT fire
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_area_dark_trigger_fires_when_becomes_dark(
        self,
        hass: HomeAssistant,
        setup_basic_light_group_bright: dict,
    ):
        """Test AREA_DARK trigger fires when area becomes dark while occupied."""
        light_group_id = setup_basic_light_group_bright["light_group_id"]
        motion_sensor = setup_basic_light_group_bright["motion_sensor"]
        dark_sensor = setup_basic_light_group_bright["dark_sensor"]

        # Area is ALREADY bright from fixture setup (dark sensor ON)
        # Make area occupied (but bright, so lights won't turn on)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Lights should NOT turn on (area is bright)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

        # Event: Area becomes dark (AREA_DARK trigger)
        await trigger_secondary_state(hass, dark_sensor, active=False)

        # Verify lights turned on via AREA_DARK trigger
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_area_dark_trigger_doesnt_fire_when_unoccupied(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test AREA_DARK trigger doesn't fire if area is unoccupied."""
        light_group_id = setup_basic_light_group["light_group_id"]
        area_id = setup_basic_light_group["config_entry"].data["id"]

        # Setup: Area is clear and bright
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

        # Event: Area becomes dark but stays clear
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            area_id,
            ({AreaStates.DARK}, {AreaStates.BRIGHT}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify trigger did NOT fire
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_multiple_triggers_any_can_activate(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that when multiple triggers configured, any one can activate lights."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]
        area_id = setup_basic_light_group["config_entry"].data["id"]

        # Group has AREA_OCCUPIED, STATE_GAIN, and AREA_DARK (default config)

        # Test 1: AREA_OCCUPIED trigger
        await trigger_occupancy(hass, motion_sensor, occupied=True)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Reset - turn off and make area clear
        # Use magic context to avoid entering manual mode
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": light_group_id},
            blocking=True,
            context=create_magic_context(),
        )
        await hass.async_block_till_done()
        await trigger_occupancy(hass, motion_sensor, occupied=False)

        # Test 2: Make occupied but bright
        await trigger_occupancy(hass, motion_sensor, occupied=True)
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            area_id,
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # STATE_GAIN trigger (dark gained while occupied)
        dispatcher_send(
            hass,
            MagicAreasEvents.AREA_STATE_CHANGED,
            area_id,
            ({AreaStates.DARK}, {AreaStates.BRIGHT}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Should have turned on via STATE_GAIN or AREA_DARK
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)
