"""Tests for user-defined states functionality."""

import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON

from custom_components.magic_areas.const import (
    DOMAIN,
    AreaStates,
    CommonAttributes,
    ConfigDomains,
)
from custom_components.magic_areas.const.user_defined_states import (
    UserDefinedStateEntryOptions,
    UserDefinedStateOptions,
    slugify_state_name,
)
from tests.conftest import MockConfigEntry
from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_in_attribute,
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor

# Expected state names (slugified)
EXPECTED_STATE_MOVIE_TIME = "movie_time"
EXPECTED_STATE_GAMING = "gaming"


@pytest.fixture
async def setup_user_defined_states(hass):
    """Set up area with user-defined states."""
    # Create tracking entities
    movie_mode = MockBinarySensor(
        name="movie_mode",
        unique_id="movie_mode",
        device_class=None,
    )
    gaming_mode = MockBinarySensor(
        name="gaming_mode",
        unique_id="gaming_mode",
        device_class=None,
    )

    # Register entities FIRST (this populates entity_id)
    await setup_mock_entities(
        hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [movie_mode, gaming_mode]}
    )

    # NOW set initial states (entity_id is available)
    hass.states.async_set(movie_mode.entity_id, STATE_OFF)
    hass.states.async_set(gaming_mode.entity_id, STATE_OFF)

    # Create config entry with user-defined states
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data[ConfigDomains.USER_DEFINED_STATES.value] = {
        UserDefinedStateOptions.STATES.key: [
            {
                UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                UserDefinedStateEntryOptions.ENTITY.key: movie_mode.entity_id,
            },
            {
                UserDefinedStateEntryOptions.NAME.key: "Gaming",
                UserDefinedStateEntryOptions.ENTITY.key: gaming_mode.entity_id,
            },
        ]
    }

    config_entry = MockConfigEntry(domain=DOMAIN, data=data)
    await init_integration(hass, [config_entry])

    area_state_id = f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state"

    yield {
        "area_state_id": area_state_id,
        "movie_mode_id": movie_mode.entity_id,
        "gaming_mode_id": gaming_mode.entity_id,
        "config_entry": config_entry,
    }

    await shutdown_integration(hass, [config_entry])


class TestUserDefinedStates:
    """Test user-defined states runtime behavior."""

    async def test_user_defined_state_becomes_active(
        self, hass, setup_user_defined_states
    ):
        """Test area gains user-defined state when entity turns on."""
        area_state_id = setup_user_defined_states["area_state_id"]
        movie_mode_id = setup_user_defined_states["movie_mode_id"]

        # Turn on movie mode
        hass.states.async_set(movie_mode_id, STATE_ON)
        await hass.async_block_till_done()

        # Verify area has movie_time state
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, EXPECTED_STATE_MOVIE_TIME
        )

    async def test_user_defined_state_becomes_inactive(
        self, hass, setup_user_defined_states
    ):
        """Test area loses user-defined state when entity turns off."""
        area_state_id = setup_user_defined_states["area_state_id"]
        movie_mode_id = setup_user_defined_states["movie_mode_id"]

        # Turn on then off
        hass.states.async_set(movie_mode_id, STATE_ON)
        await hass.async_block_till_done()

        hass.states.async_set(movie_mode_id, STATE_OFF)
        await hass.async_block_till_done()

        # Verify area no longer has movie_time state
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(
            area_state,
            CommonAttributes.STATES.value,
            EXPECTED_STATE_MOVIE_TIME,
            negate=True,
        )

    async def test_multiple_user_defined_states(self, hass, setup_user_defined_states):
        """Test multiple user-defined states can be active simultaneously."""
        area_state_id = setup_user_defined_states["area_state_id"]
        movie_mode_id = setup_user_defined_states["movie_mode_id"]
        gaming_mode_id = setup_user_defined_states["gaming_mode_id"]

        # Turn on both states
        hass.states.async_set(movie_mode_id, STATE_ON)
        hass.states.async_set(gaming_mode_id, STATE_ON)
        await hass.async_block_till_done()

        # Verify area has both states
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, EXPECTED_STATE_MOVIE_TIME
        )
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, EXPECTED_STATE_GAMING
        )

    async def test_user_defined_state_with_occupied(
        self, hass, setup_user_defined_states
    ):
        """Test user-defined states work alongside occupied state."""
        area_state_id = setup_user_defined_states["area_state_id"]
        movie_mode_id = setup_user_defined_states["movie_mode_id"]

        # Turn on movie mode
        hass.states.async_set(movie_mode_id, STATE_ON)
        await hass.async_block_till_done()

        # Area should have clear and movie_time (not occupied since no presence sensors)
        area_state = hass.states.get(area_state_id)
        assert_in_attribute(area_state, CommonAttributes.STATES.value, AreaStates.CLEAR)
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, EXPECTED_STATE_MOVIE_TIME
        )

    async def test_slugification(self, hass, setup_user_defined_states):
        """Test state names are properly slugified."""
        area_state_id = setup_user_defined_states["area_state_id"]
        movie_mode_id = setup_user_defined_states["movie_mode_id"]

        # Turn on "Movie Time" - should appear as "movie_time"
        hass.states.async_set(movie_mode_id, STATE_ON)
        await hass.async_block_till_done()

        area_state = hass.states.get(area_state_id)
        # Should be slugified
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, EXPECTED_STATE_MOVIE_TIME
        )
        # Should NOT be raw name
        assert_in_attribute(
            area_state, CommonAttributes.STATES.value, "Movie Time", negate=True
        )


class TestSlugifyStateName:
    """Test state name slugification."""

    def test_basic_slugification(self):
        """Test basic slugification."""
        assert slugify_state_name("Movie Time") == "movie_time"
        assert slugify_state_name("Gaming Mode") == "gaming_mode"
        assert slugify_state_name("Party Mode") == "party_mode"

    def test_special_characters(self):
        """Test slugification removes special characters."""
        assert slugify_state_name("Movie & TV") == "movie_tv"
        assert slugify_state_name("Relax/Chill") == "relax_chill"

    def test_multiple_spaces(self):
        """Test multiple spaces are handled."""
        assert slugify_state_name("Movie  Time") == "movie_time"
        assert slugify_state_name("   Gaming   ") == "gaming"

    def test_already_slugified(self):
        """Test already slugified names."""
        assert slugify_state_name("movie_time") == "movie_time"
        assert slugify_state_name("gaming") == "gaming"
