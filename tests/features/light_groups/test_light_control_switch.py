"""Tests for the light control switch."""

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN, Features

from tests.const import DEFAULT_MOCK_AREA, MockAreaIds
from tests.helpers import (
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    shutdown_integration,
)

AREA_STATE_ID = (
    f"binary_sensor.magic_areas_presence_tracking_{DEFAULT_MOCK_AREA.value}_area_state"
)


class TestLightControlSwitch:
    """Test the switch that enables or disables automatic light control."""

    async def test_switch_toggles(
        self, hass: HomeAssistant, setup_basic_light_group: dict
    ):
        """Test the light control switch turns off and on again."""
        light_control_id = setup_basic_light_group["light_control_id"]
        assert_state(hass.states.get(light_control_id), STATE_ON)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: light_control_id},
            blocking=True,
        )
        assert_state(hass.states.get(light_control_id), STATE_OFF)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: light_control_id},
            blocking=True,
        )
        assert_state(hass.states.get(light_control_id), STATE_ON)

    async def test_meta_areas_get_no_light_control_switch(self, hass: HomeAssistant):
        """Test the light control switch is never created for a meta area."""
        data = get_basic_config_entry_data(MockAreaIds.INTERIOR)
        data["features"][Features.LIGHT_GROUPS] = {}
        config_entry = MockConfigEntry(domain=DOMAIN, data=data)
        await init_integration(hass, [config_entry], areas=[MockAreaIds.INTERIOR])

        meta_switch_id = (
            f"{SWITCH_DOMAIN}.magic_areas_light_groups_interior_light_control"
        )
        assert hass.states.get(meta_switch_id) is None

        await shutdown_integration(hass, [config_entry])

    async def test_creation_error_is_contained(self, hass: HomeAssistant, caplog):
        """Test a failing light control switch is logged and the area still loads."""
        data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
        data["features"][Features.LIGHT_GROUPS] = {}
        config_entry = MockConfigEntry(domain=DOMAIN, data=data)
        with patch(
            "custom_components.magic_areas.switch.LightControlSwitch",
            side_effect=RuntimeError("boom"),
        ):
            await init_integration(hass, [config_entry])

        assert "Error loading light control switch: boom" in caplog.text
        assert hass.states.get(AREA_STATE_ID) is not None

        await shutdown_integration(hass, [config_entry])
