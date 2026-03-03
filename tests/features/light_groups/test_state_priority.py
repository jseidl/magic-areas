"""Tests for state priority filtering system."""

import asyncio

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.helpers import assert_state, trigger_occupancy, trigger_secondary_state


class TestStatePriority:
    """Test state priority filtering in light groups.

    Priority order (highest to lowest):
    1. Sleep state
    2. User-defined states
    3. Built-in states (occupied, extended, dark, bright, clear)
    """

    async def test_sleep_state_blocks_occupied_groups(
        self, hass: HomeAssistant, setup_multi_group_occupied_and_sleep: dict
    ):
        """Test that sleep state blocks groups configured for occupied.

        When sleep is active, _apply_state_priority() returns only {sleep},
        so groups configured for OCCUPIED don't match and won't turn on.
        """
        occupied_group_id = setup_multi_group_occupied_and_sleep["occupied_group_id"]
        sleep_group_id = setup_multi_group_occupied_and_sleep["sleep_group_id"]
        motion_sensor = setup_multi_group_occupied_and_sleep["motion_sensor"]
        sleep_sensor = setup_multi_group_occupied_and_sleep["secondary_sensors"][
            "sleep"
        ]

        # Activate sleep first
        await trigger_secondary_state(hass, sleep_sensor, active=True)

        # Make area occupied (with sleep active)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Sleep group should turn on (sleep state matches)
        sleep_group = hass.states.get(sleep_group_id)
        assert_state(sleep_group, STATE_ON)

        # Occupied group should NOT turn on (sleep filters out occupied state)
        occupied_group = hass.states.get(occupied_group_id)
        assert_state(occupied_group, STATE_OFF)

    async def test_sleep_state_activates_sleep_groups(
        self, hass: HomeAssistant, setup_sleep_light_group: dict
    ):
        """Test that sleep state activates groups configured for sleep."""
        light_group_id = setup_sleep_light_group["light_group_id"]
        sleep_sensor = setup_sleep_light_group["secondary_sensors"]["sleep"]

        # Activate sleep state
        await trigger_secondary_state(hass, sleep_sensor, active=True)

        # Sleep group should turn on
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_ON)

        # Deactivate sleep
        await trigger_secondary_state(hass, sleep_sensor, active=False)

        # Sleep group should turn off
        await asyncio.sleep(0.5)
        light_state = hass.states.get(light_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_user_defined_state_blocks_built_in_states(
        self, hass: HomeAssistant, setup_user_defined_state_light_group: dict
    ):
        """Test that user-defined states block built-in states.

        When movie_time is active, _apply_state_priority() filters out
        built-in states like OCCUPIED, so OCCUPIED groups don't turn on.
        """
        occupied_group_id = setup_user_defined_state_light_group["occupied_group_id"]
        movie_group_id = setup_user_defined_state_light_group["movie_group_id"]
        motion_sensor = setup_user_defined_state_light_group["motion_sensor"]
        movie_mode = setup_user_defined_state_light_group["movie_mode"]

        # Activate movie mode first
        await trigger_secondary_state(hass, movie_mode, active=True)

        # Make area occupied (with movie mode active)
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Movie group should turn on (movie_time state matches)
        movie_group = hass.states.get(movie_group_id)
        assert_state(movie_group, STATE_ON)

        # Occupied group should NOT turn on (movie_time filters out occupied)
        occupied_group = hass.states.get(occupied_group_id)
        assert_state(occupied_group, STATE_OFF)

    async def test_user_defined_state_activates_matching_groups(
        self, hass: HomeAssistant, setup_user_defined_state_light_group: dict
    ):
        """Test that user-defined states activate groups configured for them."""
        movie_group_id = setup_user_defined_state_light_group["movie_group_id"]
        movie_mode = setup_user_defined_state_light_group["movie_mode"]
        motion_sensor = setup_user_defined_state_light_group["motion_sensor"]

        # Make area occupied
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Activate movie mode
        await trigger_secondary_state(hass, movie_mode, active=True)

        # Movie group should turn on
        light_state = hass.states.get(movie_group_id)
        assert_state(light_state, STATE_ON)

        # Deactivate movie mode
        await trigger_secondary_state(hass, movie_mode, active=False)

        # Movie group should turn off
        await asyncio.sleep(0.5)
        light_state = hass.states.get(movie_group_id)
        assert_state(light_state, STATE_OFF)

    async def test_multiple_user_defined_states_all_considered(
        self, hass: HomeAssistant, setup_multi_user_defined_states: dict
    ):
        """Test that all user-defined states are considered together.

        When multiple user-defined states are active, _apply_state_priority()
        returns all of them (doesn't filter between user-defined states).
        """
        movie_group_id = setup_multi_user_defined_states["movie_group_id"]
        gaming_group_id = setup_multi_user_defined_states["gaming_group_id"]
        movie_mode = setup_multi_user_defined_states["movie_mode"]
        gaming_mode = setup_multi_user_defined_states["gaming_mode"]
        motion_sensor = setup_multi_user_defined_states["motion_sensor"]

        # Make area occupied
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Activate both modes
        await trigger_secondary_state(hass, movie_mode, active=True)
        await trigger_secondary_state(hass, gaming_mode, active=True)

        # Both groups should be on
        movie_group = hass.states.get(movie_group_id)
        assert_state(movie_group, STATE_ON)

        gaming_group = hass.states.get(gaming_group_id)
        assert_state(gaming_group, STATE_ON)

        # Turn off movie mode (gaming still active)
        await trigger_secondary_state(hass, movie_mode, active=False)
        await asyncio.sleep(0.5)

        # Movie group turns off, gaming stays on
        movie_group = hass.states.get(movie_group_id)
        assert_state(movie_group, STATE_OFF)

        gaming_group = hass.states.get(gaming_group_id)
        assert_state(gaming_group, STATE_ON)

    async def test_sleep_priority_over_user_defined(
        self, hass: HomeAssistant, setup_sleep_and_user_defined: dict
    ):
        """Test that sleep has priority over user-defined states.

        When both sleep and movie_time are active, _apply_state_priority()
        returns only {sleep}, filtering out the user-defined state.
        """
        sleep_group_id = setup_sleep_and_user_defined["sleep_group_id"]
        movie_group_id = setup_sleep_and_user_defined["movie_group_id"]
        sleep_sensor = setup_sleep_and_user_defined["secondary_sensors"]["sleep"]
        movie_mode = setup_sleep_and_user_defined["movie_mode"]
        motion_sensor = setup_sleep_and_user_defined["motion_sensor"]

        # Make area occupied
        await trigger_occupancy(hass, motion_sensor, occupied=True)

        # Activate both states
        await trigger_secondary_state(hass, movie_mode, active=True)
        await trigger_secondary_state(hass, sleep_sensor, active=True)

        # Sleep group should turn on (sleep has highest priority)
        sleep_group = hass.states.get(sleep_group_id)
        assert_state(sleep_group, STATE_ON)

        # Movie group should NOT turn on (sleep filters out user-defined states)
        movie_group = hass.states.get(movie_group_id)
        assert_state(movie_group, STATE_OFF)

        # Deactivate sleep (movie still active)
        await trigger_secondary_state(hass, sleep_sensor, active=False)
        await asyncio.sleep(0.5)

        # Sleep group turns off
        sleep_group = hass.states.get(sleep_group_id)
        assert_state(sleep_group, STATE_OFF)

        # Movie group NOW turns on (no longer filtered)
        movie_group = hass.states.get(movie_group_id)
        assert_state(movie_group, STATE_ON)
