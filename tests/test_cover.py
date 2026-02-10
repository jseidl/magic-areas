"""Test for cover groups."""

from collections import defaultdict
from collections.abc import AsyncGenerator
import logging
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.cover.const import DOMAIN as COVER_DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ENTITY_ID, STATE_OPEN
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import DOMAIN, Features

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockCover

_LOGGER = logging.getLogger(__name__)


# Fixtures


@pytest.fixture(name="cover_groups_config_entry")
def mock_config_entry_cover_groups() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data.update({"features": {Features.COVER_GROUPS: {}}})
    return MockConfigEntry(domain=DOMAIN, data=data)


@pytest.fixture(name="_setup_integration_cover_group")
async def setup_integration_cover_group(
    hass: HomeAssistant,
    cover_groups_config_entry: MockConfigEntry,
) -> AsyncGenerator[Any]:
    """Set up integration with secondary states config."""

    await init_integration(hass, [cover_groups_config_entry])
    yield
    await shutdown_integration(hass, [cover_groups_config_entry])


# Entities


@pytest.fixture(name="entities_sensor_cover_all_classes_multiple")
async def setup_entities_sensor_cover_all_classes_multiple(
    hass: HomeAssistant,
) -> list[MockCover]:
    """Create multiple mock sensor and setup the system with it."""

    nr_entities = 3
    mock_cover_entities = []

    for dc in CoverDeviceClass:
        for i in range(nr_entities):
            mock_cover_entities.append(
                MockCover(
                    name=f"cover_{dc.value}_{i}",
                    unique_id=f"cover_{dc.value}_{i}",
                    device_class=dc.value,
                )
            )
    await setup_mock_entities(
        hass, COVER_DOMAIN, {DEFAULT_MOCK_AREA: mock_cover_entities}
    )
    return mock_cover_entities


# Tests


async def test_cover_group_basic(
    hass: HomeAssistant,
    entities_sensor_cover_all_classes_multiple: list[MockCover],
    _setup_integration_cover_group,
) -> None:
    """Test cover group."""

    cover_group_entity_id_base = (
        f"{COVER_DOMAIN}.magic_areas_cover_groups_kitchen_cover_group_"
    )
    entity_map = defaultdict(list)

    # Ensure all mock entities exist and map
    for cover in entities_sensor_cover_all_classes_multiple:
        cover_state = hass.states.get(cover.entity_id)
        assert cover_state is not None
        assert cover_state.state == STATE_OPEN
        assert hasattr(cover_state, "attributes")
        assert ATTR_DEVICE_CLASS in cover_state.attributes
        entity_map[cover_state.attributes[ATTR_DEVICE_CLASS]].append(cover)

    for dc in CoverDeviceClass:
        group_entity_id = f"{cover_group_entity_id_base}{dc.value}"

        # Ensure cover group exists and has its children
        group_entity_state = hass.states.get(group_entity_id)
        assert group_entity_state is not None
        assert group_entity_state.state == STATE_OPEN
        assert hasattr(group_entity_state, "attributes")
        assert ATTR_ENTITY_ID in group_entity_state.attributes
        for child_cover in entity_map[dc.value]:
            assert (
                child_cover.entity_id in group_entity_state.attributes[ATTR_ENTITY_ID]
            )
