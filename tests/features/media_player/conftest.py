"""Fixtures for the media player feature tests."""

import pytest

from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import setup_mock_entities
from tests.mocks import MockMediaPlayer


@pytest.fixture(name="player")
async def fixture_player(hass: HomeAssistant) -> MockMediaPlayer:
    """Register one media player in the default area."""
    mock_player = MockMediaPlayer(name="setup_player", unique_id="setup_player")
    await setup_mock_entities(
        hass, MEDIA_PLAYER_DOMAIN, {DEFAULT_MOCK_AREA: [mock_player]}
    )
    return mock_player
