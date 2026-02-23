"""Tests for manual mode override behavior."""

import asyncio

import pytest

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const.light_groups import (
    LightGroupAttributes,
    LightGroupOperationMode,
)

from tests.features.light_groups.conftest import (
    trigger_occupancy,
    trigger_secondary_state,
)
from tests.helpers import assert_attribute, assert_state


class TestManualMode:
    """Test manual mode override behavior."""

    async def test_user_turn_on_enters_manual_mode(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that user-initiated turn-on enters manual mode."""
        light_group_id = setup_basic_light_group["light_group_id"]

        # User turns on lights directly (no magic context)
        await hass.services.async_call(
            "light", "turn_on", {ATTR_ENTITY_ID: light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify manual mode was entered
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )

    async def test_user_turn_off_enters_manual_mode(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that user-initiated turn-off enters manual mode."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # First, turn lights on automatically
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MAGIC.value,
        )

        # User turns off lights directly (enters manual mode)
        await hass.services.async_call(
            "light", "turn_off", {ATTR_ENTITY_ID: light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify manual mode was entered
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )

    async def test_magic_context_doesnt_enter_manual_mode(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that Magic Areas automatic control doesn't trigger manual mode."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Magic Areas turns on lights automatically
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Verify lights are on and in magic mode
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MAGIC.value,
        )

    async def test_manual_mode_blocks_automatic_turn_on(
        self, hass: HomeAssistant, setup_sleep_light_group: dict
    ):
        """Test that manual mode blocks automatic turn-on from STATE_GAIN trigger."""
        light_group_id = setup_sleep_light_group["light_group_id"]
        motion_sensor = setup_sleep_light_group["motion_sensor"]
        sleep_sensor = setup_sleep_light_group["secondary_sensors"]["sleep"]

        # Step 1: Trigger area occupancy
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Step 2: Assert light group is in magic mode (and OFF, since SLEEP not active)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MAGIC.value,
        )

        # Step 3: Trigger secondary state (SLEEP) to make the light come on via STATE_GAIN
        await trigger_secondary_state(hass, sleep_sensor, active=True)

        # Step 4: Assert light group is ON (STATE_GAIN trigger fired)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Step 5: Call turn_off on light group to trigger manual mode
        await hass.services.async_call(
            "light", "turn_off", {ATTR_ENTITY_ID: light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Step 6: Assert light group is in manual mode
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )

        # Step 7: Turn the secondary state off
        await trigger_secondary_state(hass, sleep_sensor, active=False)

        # Step 8: Trigger secondary state (active=True) again (STATE_GAIN fires)
        await trigger_secondary_state(hass, sleep_sensor, active=True)

        # Step 9: Assert light did NOT come on (manual mode blocked it)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )

    async def test_manual_mode_blocks_automatic_turn_off_except_clear(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that manual mode blocks automatic turn-off except on AREA_CLEAR."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied, lights turn on
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # User manually turns on lights again (enters manual mode)
        await hass.services.async_call(
            "light", "turn_on", {ATTR_ENTITY_ID: light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify manual mode
        light_state = hass.states.get(light_group_id)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )

        # Area goes clear - should turn off even in manual mode
        await trigger_occupancy(hass, motion_sensor, occupied=False)

        # Lights should turn off (AREA_CLEAR overrides manual mode)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_area_clear_exits_manual_mode(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that AREA_CLEAR exits manual mode."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Enter manual mode
        await hass.services.async_call(
            "light", "turn_off", {ATTR_ENTITY_ID: light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        light_state = hass.states.get(light_group_id)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )

        # Area clears
        await trigger_occupancy(hass, motion_sensor, occupied=False)

        # Manual mode should reset to magic
        light_state = hass.states.get(light_group_id)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MAGIC.value,
        )

    async def test_manual_mode_persists_across_state_changes(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that manual mode persists across various state changes."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Make area occupied
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Enter manual mode
        await hass.services.async_call(
            "light", "turn_off", {ATTR_ENTITY_ID: light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        light_state = hass.states.get(light_group_id)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )

        # Trigger motion again (state change but not clear)
        hass.states.async_set(motion_sensor.entity_id, STATE_ON)
        await hass.async_block_till_done()
        await asyncio.sleep(0.5)

        # Manual mode should persist
        light_state = hass.states.get(light_group_id)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )

        # Various state changes (as long as area doesn't clear)
        await asyncio.sleep(0.5)

        # Manual mode should still persist
        light_state = hass.states.get(light_group_id)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )

    async def test_turn_on_without_context_enters_manual(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that turn_on without context enters manual mode."""
        light_group_id = setup_basic_light_group["light_group_id"]

        # Turn on without any context (user action)
        await hass.services.async_call(
            "light", "turn_on", {ATTR_ENTITY_ID: light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Should enter manual mode
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )

    async def test_update_attributes_called_on_manual_mode_change(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test that attributes are updated when entering manual mode."""
        light_group_id = setup_basic_light_group["light_group_id"]
        motion_sensor = setup_basic_light_group["motion_sensor"]

        # Start with automatic control
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MAGIC.value,
        )

        # Enter manual mode via user action
        await hass.services.async_call(
            "light", "turn_on", {ATTR_ENTITY_ID: light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

        # Verify attribute was updated
        light_state = hass.states.get(light_group_id)
        assert_attribute(
            light_state,
            LightGroupAttributes.MODE.value,
            LightGroupOperationMode.MANUAL.value,
        )
