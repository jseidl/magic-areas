"""Tests for the Reusable Timer helper."""

from datetime import datetime
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.magic_areas.helpers.timer import ReusableTimer


async def test_timer_fires(hass: HomeAssistant, patch_async_call_later):
    """Test that the timer fires after the scheduled delay."""
    fired = {}

    async def callback(now: datetime):
        fired["at"] = now

    timer = ReusableTimer(hass, 0.01, callback)
    timer.start()
    await hass.async_block_till_done()

    assert "at" in fired


async def test_timer_cancel(hass: HomeAssistant, patch_async_call_later):
    """Test that cancel prevents the timer from firing."""
    fired = {}

    async def callback(now: datetime):
        fired["at"] = now

    timer = ReusableTimer(hass, 0.01, callback)

    timer.start()
    timer.cancel()
    await hass.async_block_till_done()

    assert "at" not in fired


async def test_timer_restart_replaces_old(hass: HomeAssistant, patch_async_call_later):
    """Test that starting a timer again cancels the previous one."""
    calls = []

    async def callback(now: datetime):
        calls.append(now)

    timer = ReusableTimer(hass, 0.01, callback)

    timer.start()  # first timer
    assert timer._token == 1  # pylint: disable=protected-access
    timer.start()  # second timer replaces first
    assert timer._token == 2  # pylint: disable=protected-access
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert timer._token == 2  # pylint: disable=protected-access


async def test_async_remove_cancels(hass: HomeAssistant, patch_async_call_later):
    """Test that async_remove prevents a pending timer from firing."""
    fired = {}

    async def callback(now: datetime):
        fired["at"] = now

    timer = ReusableTimer(hass, 0.01, callback)
    timer.start()
    await timer.async_remove()
    await hass.async_block_till_done()

    assert "at" not in fired


async def test_superseded_timer_does_not_fire(hass: HomeAssistant):
    """Test a scheduled callback is skipped once the timer was started again."""
    calls = []
    scheduled = []

    async def callback(now: datetime):
        calls.append(now)

    def capture(_hass, _delay, action):
        scheduled.append(action)
        return lambda: None

    timer = ReusableTimer(hass, 60, callback)
    with patch(
        "custom_components.magic_areas.helpers.timer.async_call_later",
        side_effect=capture,
    ):
        timer.start()
        timer.start()

    # Both callbacks were queued; only the one from the latest start() may run.
    await scheduled[0](datetime.now())
    assert not calls

    await scheduled[1](datetime.now())
    assert len(calls) == 1
