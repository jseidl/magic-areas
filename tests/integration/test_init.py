"""Test initializing the system."""

import logging

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN, ConfigDomains, Features

from tests.const import DEFAULT_MOCK_AREA, MockAreaIds
from tests.helpers import (
    assert_state,
    get_basic_config_entry_data,
    init_integration,
    shutdown_integration,
)

_LOGGER = logging.getLogger(__name__)


async def test_init_default_config(
    hass: HomeAssistant, basic_config_entry: MockConfigEntry, _setup_integration_basic
) -> None:
    """Test loading the integration."""

    # Validate the right enties were created.
    area_binary_sensor = hass.states.get(
        f"{BINARY_SENSOR_DOMAIN}.magic_areas_presence_tracking_kitchen_area_state"
    )

    assert_state(area_binary_sensor, STATE_OFF)


async def test_invalid_features_config_disables_every_feature(
    hass: HomeAssistant,
) -> None:
    """A features section that is not a mapping enables no feature."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data[ConfigDomains.FEATURES.value] = ["not", "a", "mapping"]
    config_entry = MockConfigEntry(domain=DOMAIN, data=data)
    await init_integration(hass, [config_entry])
    try:
        area = config_entry.runtime_data
        assert not area.has_feature(Features.LIGHT_GROUPS)
        assert not area.has_feature(Features.AGGREGATION)
    finally:
        await shutdown_integration(hass, [config_entry])


async def test_area_type_helpers(hass: HomeAssistant) -> None:
    """Areas report whether they are interior or exterior from their configured type."""
    interior = MockConfigEntry(
        domain=DOMAIN, data=get_basic_config_entry_data(MockAreaIds.KITCHEN)
    )
    exterior = MockConfigEntry(
        domain=DOMAIN, data=get_basic_config_entry_data(MockAreaIds.BACKYARD)
    )
    await init_integration(
        hass, [interior, exterior], areas=[MockAreaIds.KITCHEN, MockAreaIds.BACKYARD]
    )
    try:
        assert interior.runtime_data.is_interior()
        assert not interior.runtime_data.is_exterior()
        assert exterior.runtime_data.is_exterior()
        assert not exterior.runtime_data.is_interior()
    finally:
        await shutdown_integration(hass, [interior, exterior])
