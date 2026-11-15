"""Tests for light group turn-off behaviors."""

import asyncio

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from custom_components.magic_areas.const import AreaStates, MagicAreasEvents
from custom_components.magic_areas.const.light_groups import (
    LightGroupAttributes,
    LightGroupTurnOnWhen,
)

from tests.helpers import assert_attribute, assert_state, trigger_occupancy


class TestTurnOff:
    """Test turn-off behaviors for light groups."""

    async def test_turn_off_on_area_clear(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test lights turn off when area clears."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Area becomes clear
        await trigger_occupancy(hass, motion_sensor, occupied=False)

        # Verify lights turned off
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_turn_off_on_state_loss(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test lights turn off when all configured states are lost."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied and dark (lights turn on)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Area loses occupied state (becomes clear)
        await trigger_occupancy(hass, motion_sensor, occupied=False)

        # Verify lights turned off (lost OCCUPIED state)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_turn_off_on_exterior_bright(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test lights turn off when exterior area becomes bright."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Exterior area becomes bright
        dispatcher_send(
            hass,
            f"{MagicAreasEvents.AREA_STATE_CHANGED}_exterior",
            "exterior",
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify lights turned off
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_area_clear_resets_manual_mode(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that AREA_CLEAR resets manual mode."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Enter manual mode by turning off
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify manual mode
        light_state = hass.states.get(light_group_id)
        assert_attribute(light_state, LightGroupAttributes.MODE.value, "manual")

        # Area goes clear
        await trigger_occupancy(hass, motion_sensor, occupied=False)

        # Verify manual mode was reset
        light_state = hass.states.get(light_group_id)
        assert_attribute(light_state, LightGroupAttributes.MODE.value, "magic")

    async def test_exterior_bright_ignored_if_not_configured(
        self, hass: HomeAssistant, setup_no_exterior_light_group: dict
    ):
        """Test exterior bright is ignored if not in TURN_OFF_WHEN."""
        light_group_id = setup_no_exterior_light_group["light_group_id"]
        motion_sensor = setup_no_exterior_light_group["motion_sensor"]

        # Make area occupied, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Exterior becomes bright
        dispatcher_send(
            hass,
            f"{MagicAreasEvents.AREA_STATE_CHANGED}_{'exterior'}",
            "exterior",
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify lights did NOT turn off (no EXTERIOR_BRIGHT in config)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

    async def test_state_loss_only_when_all_states_lost(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test STATE_LOSS only triggers when ALL configured states are lost."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Group configured for OCCUPIED state
        # Make area occupied
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Area is still occupied (no state loss)
        # Lights should stay on
        await asyncio.sleep(0.5)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Now lose the occupied state
        await trigger_occupancy(hass, motion_sensor, occupied=False)

        # Should turn off (lost all configured states)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_own_area_events_dont_trigger_exterior_bright(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that own area bright events don't trigger EXTERIOR_BRIGHT logic."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]
        area_id = setup_basic_light_group["config_entry"].data["id"]

        # Make area occupied, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Own area becomes bright (not exterior)
        dispatcher_send(
            hass,
            f"{MagicAreasEvents.AREA_STATE_CHANGED}_{area_id}",
            area_id,
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Lights should stay ON (own area bright doesn't trigger EXTERIOR_BRIGHT)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)


class TestTurnOffGuards:
    """Test the conditions that block an automatic turn-off."""

    async def test_exterior_bright_ignored_when_group_is_off(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test exterior brightness does nothing to a group that is already off."""
        light_group_id = setup_basic_light_group["light_group_id"]
        assert_state(hass.states.get(light_group_id), STATE_OFF)

        dispatcher_send(
            hass,
            f"{MagicAreasEvents.AREA_STATE_CHANGED}_exterior",
            "exterior",
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        assert_state(hass.states.get(light_group_id), STATE_OFF)

    async def test_exterior_bright_ignored_in_manual_mode(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test manual mode keeps lights on when the exterior gets bright."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        await trigger_occupancy(hass, motion_sensor, occupied=True)
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        assert_attribute(
            hass.states.get(light_group_id), LightGroupAttributes.MODE.value, "manual"
        )

        dispatcher_send(
            hass,
            f"{MagicAreasEvents.AREA_STATE_CHANGED}_exterior",
            "exterior",
            ({AreaStates.BRIGHT}, {AreaStates.DARK}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        assert_state(hass.states.get(light_group_id), STATE_ON)

    async def test_no_turn_off_triggers_means_never_turn_off(
        self, hass: HomeAssistant, setup_custom_light_group
    ):
        """Test a group without turn-off triggers stays on when the area clears."""
        setup = await setup_custom_light_group(
            states=[AreaStates.OCCUPIED],
            turn_on_when=[LightGroupTurnOnWhen.AREA_OCCUPIED],
            turn_off_when=[],
            require_dark=False,
        )

        await trigger_occupancy(hass, setup["motion_sensor"], occupied=True)
        assert_state(hass.states.get(setup["light_group_id"]), STATE_ON)

        await trigger_occupancy(hass, setup["motion_sensor"], occupied=False)
        assert_state(hass.states.get(setup["light_group_id"]), STATE_ON)

    async def test_lights_on_before_occupancy_stay_on(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test lights that are on when the area becomes occupied aren't turned off."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        await hass.services.async_call(
            "light", "turn_on", {"entity_id": light_group_id}, blocking=True
        )
        await hass.async_block_till_done()

        await trigger_occupancy(hass, motion_sensor, occupied=True)

        assert_state(hass.states.get(light_group_id), STATE_ON)

    async def test_manual_mode_blocks_state_based_turn_off(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test manual mode keeps lights on when an unrelated state change arrives."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]
        area_id = setup_basic_light_group["config_entry"].data["id"]

        await trigger_occupancy(hass, motion_sensor, occupied=True)
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": light_group_id}, blocking=True
        )
        await hass.async_block_till_done()

        dispatcher_send(
            hass,
            f"{MagicAreasEvents.AREA_STATE_CHANGED}_{area_id}",
            area_id,
            ({AreaStates.DARK}, {AreaStates.BRIGHT}),
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        assert_state(hass.states.get(light_group_id), STATE_ON)
