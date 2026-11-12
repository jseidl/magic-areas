"""Tests for switching an area's light sensor once the Exterior meta-area loads."""

from collections.abc import Callable
import threading
from typing import Any
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.sun.const import STATE_BELOW_HORIZON
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    DOMAIN,
    AreaStates,
    AreaType,
    CommonAttributes,
    MagicAreasEvents,
    MetaAreaType,
)

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    assert_in_attribute,
    get_basic_config_entry_data,
    init_integration,
    shutdown_integration,
)

EXTERIOR_LIGHT_SENSOR = "binary_sensor.exterior_light"
AREA_STATE_ID = (
    f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state"
)


def _recording(threads: list[int], func: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap func to record the thread each call runs on."""

    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        threads.append(threading.get_ident())
        return func(*args, **kwargs)

    return _wrapper


async def test_light_sensor_switches_on_event_loop(hass: HomeAssistant) -> None:
    """An area on the sun.sun fallback switches sensor on the event loop when Exterior loads."""

    hass.states.async_set("sun.sun", STATE_BELOW_HORIZON)
    hass.states.async_set(EXTERIOR_LIGHT_SENSOR, STATE_ON)

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    )
    await init_integration(hass, [config_entry])
    try:
        area = config_entry.runtime_data
        assert isinstance(area, MagicArea)
        assert area.area_light_sensor == "sun.sun"

        loop_thread = threading.get_ident()
        resolve_threads: list[int] = []
        track_threads: list[int] = []

        with (
            patch.object(
                area,
                "resolve_light_entity",
                _recording(resolve_threads, lambda: EXTERIOR_LIGHT_SENSOR),
            ),
            patch(
                "custom_components.magic_areas.binary_sensor.presence."
                "async_track_state_change_event",
                _recording(track_threads, async_track_state_change_event),
            ),
        ):
            # The Exterior meta-area announces it has loaded.
            async_dispatcher_send(
                hass,
                MagicAreasEvents.AREA_LOADED,
                AreaType.META,
                None,
                MetaAreaType.EXTERIOR.value,
            )
            await hass.async_block_till_done()

        # Both handlers ran, on the event loop.
        assert resolve_threads == [loop_thread]
        assert track_threads == [loop_thread]
        assert area.area_light_sensor == EXTERIOR_LIGHT_SENSOR

        # The area follows the new light sensor straight away.
        hass.states.async_set(EXTERIOR_LIGHT_SENSOR, STATE_OFF)
        await hass.async_block_till_done()
        assert_in_attribute(
            hass.states.get(AREA_STATE_ID),
            CommonAttributes.STATES.value,
            AreaStates.DARK.value,
        )
    finally:
        await shutdown_integration(hass, [config_entry])
