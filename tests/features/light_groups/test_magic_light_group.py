"""Tests for MagicLightGroup smart call forwarding.

MagicLightGroup has a critical feature: when you call turn_on with attributes
(brightness, color, etc.), it should ONLY affect lights that are already on,
not turn on additional lights.
"""

import asyncio

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR
from homeassistant.const import STATE_OFF, STATE_ON

from tests.helpers import assert_state


class TestMagicLightGroupCallForwarding:
    """Test MagicLightGroup smart call forwarding to active lights only."""

    async def test_turn_on_with_brightness_only_affects_on_lights(
        self, hass, setup_basic_light_group
    ):
        """Test that brightness changes only affect lights that are already on."""
        light_group_id = setup_basic_light_group["light_group_id"]

        # Step 1: Manually turn on light_1 and light_2 (not via automation)
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": ["light.light_1", "light.light_2"]},
            blocking=True,
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # Verify they're on
        assert_state(hass.states.get("light.light_1"), STATE_ON)
        assert_state(hass.states.get("light.light_2"), STATE_ON)
        assert_state(hass.states.get("light.light_3"), STATE_OFF)

        # Step 2: Call turn_on with brightness on the GROUP
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": light_group_id, ATTR_BRIGHTNESS: 128},
            blocking=True,
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # Step 3: Verify only light_1 and light_2 have brightness changed
        # light_3 should remain OFF (not turned on)
        light1_state = hass.states.get("light.light_1")
        light2_state = hass.states.get("light.light_2")
        light3_state = hass.states.get("light.light_3")

        assert_state(light1_state, STATE_ON)
        assert light1_state.attributes.get(ATTR_BRIGHTNESS) == 128

        assert_state(light2_state, STATE_ON)
        assert light2_state.attributes.get(ATTR_BRIGHTNESS) == 128

        # Light 3 should STILL be OFF - not turned on by brightness call
        assert_state(light3_state, STATE_OFF)

    async def test_turn_on_with_color_only_affects_on_lights(
        self, hass, setup_basic_light_group
    ):
        """Test that color changes only affect lights that are already on."""
        light_group_id = setup_basic_light_group["light_group_id"]

        # Turn on only the first light
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": "light.light_1"}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # Call turn_on with color on the group
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": light_group_id, ATTR_RGB_COLOR: (255, 0, 0)},
            blocking=True,
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # Verify only light_1 has color changed
        light1_state = hass.states.get("light.light_1")
        assert_state(light1_state, STATE_ON)
        assert light1_state.attributes.get(ATTR_RGB_COLOR) == (255, 0, 0)

        # Light 2 and 3 should remain OFF
        assert_state(hass.states.get("light.light_2"), STATE_OFF)
        assert_state(hass.states.get("light.light_3"), STATE_OFF)

    async def test_turn_on_without_attributes_uses_all_lights(
        self, hass, setup_basic_light_group
    ):
        """Test that turn_on without attributes turns on all lights."""
        light_group_id = setup_basic_light_group["light_group_id"]

        # Call turn_on without any attributes (should turn on all)
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # All lights should be on
        assert_state(hass.states.get("light.light_1"), STATE_ON)
        assert_state(hass.states.get("light.light_2"), STATE_ON)
        assert_state(hass.states.get("light.light_3"), STATE_ON)

    async def test_empty_active_lights_fallback(self, hass, setup_basic_light_group):
        """Test that when no lights are on, brightness call uses all lights."""
        light_group_id = setup_basic_light_group["light_group_id"]

        # All lights are off initially
        assert_state(hass.states.get("light.light_1"), STATE_OFF)
        assert_state(hass.states.get("light.light_2"), STATE_OFF)
        assert_state(hass.states.get("light.light_3"), STATE_OFF)

        # Call with brightness when all are off (should fallback to all)
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": light_group_id, ATTR_BRIGHTNESS: 200},
            blocking=True,
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # All lights should be turned on with brightness
        for light_id in ["light.light_1", "light.light_2", "light.light_3"]:
            light_state = hass.states.get(light_id)
            assert_state(light_state, STATE_ON)
            assert light_state.attributes.get(ATTR_BRIGHTNESS) == 200

    async def test_multiple_attributes_only_affect_on_lights(
        self, hass, setup_basic_light_group
    ):
        """Test that multiple attributes in one call only affect on lights."""
        light_group_id = setup_basic_light_group["light_group_id"]

        # Turn on all lights first
        for light_id in ["light.light_1", "light.light_2", "light.light_3"]:
            await hass.services.async_call(
                "light", "turn_on", {"entity_id": light_id}, blocking=True
            )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # Turn off light_3
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": "light.light_3"}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # Call with multiple attributes
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": light_group_id,
                ATTR_BRIGHTNESS: 150,
                ATTR_RGB_COLOR: (0, 255, 0),
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # Verify light_1 and light_2 have both attributes
        for light_id in ["light.light_1", "light.light_2"]:
            light_state = hass.states.get(light_id)
            assert_state(light_state, STATE_ON)
            assert light_state.attributes.get(ATTR_BRIGHTNESS) == 150
            assert light_state.attributes.get(ATTR_RGB_COLOR) == (0, 255, 0)

        # Light 3 should still be OFF (not turned on)
        assert_state(hass.states.get("light.light_3"), STATE_OFF)

    async def test_turn_off_affects_all_lights(self, hass, setup_basic_light_group):
        """Test that turn_off always affects all lights (not just active ones)."""
        light_group_id = setup_basic_light_group["light_group_id"]

        # Turn on only light_1 and light_2
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": ["light.light_1", "light.light_2"]},
            blocking=True,
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # Call turn_off on the group
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": light_group_id}, blocking=True
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.3)

        # All lights should be off (even though light_3 was already off)
        assert_state(hass.states.get("light.light_1"), STATE_OFF)
        assert_state(hass.states.get("light.light_2"), STATE_OFF)
        assert_state(hass.states.get("light.light_3"), STATE_OFF)
