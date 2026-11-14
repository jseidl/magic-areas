"""Integration tests for the options flow, driven through Home Assistant's flow manager."""

# pylint: disable=protected-access

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.climate.const import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.magic_areas.config_flow.domain_handlers import (
    DomainStepResult,
)
from custom_components.magic_areas.config_flow.features.base import StepResult
from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler
from custom_components.magic_areas.config_flow.user_defined_states import (
    UserDefinedStatesHandler,
)
from custom_components.magic_areas.const import DOMAIN, ConfigDomains
from custom_components.magic_areas.const.climate_control import ClimateControlOptions
from custom_components.magic_areas.const.fan_groups import FanGroupOptions
from custom_components.magic_areas.const.light_groups import LightGroupEntryOptions
from custom_components.magic_areas.const.presence_hold import PresenceHoldOptions
from custom_components.magic_areas.const.user_defined_states import (
    UserDefinedStateEntryOptions,
    UserDefinedStateOptions,
)

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor, MockClimate, MockLight

CONFIGURABLE_FEATURES = [
    "aggregates",
    "area_aware_media_player",
    "ble_trackers",
    "climate_control",
    "fan_groups",
    "health",
    "light_groups",
    "presence_hold",
    "wasp_in_a_box",
]

SIMPLE_FEATURE_INPUTS: list[tuple[str, dict[str, Any]]] = [
    ("aggregates", {}),
    ("area_aware_media_player", {}),
    ("ble_trackers", {}),
    ("health", {}),
    ("presence_hold", {PresenceHoldOptions.TIMEOUT.key: 5}),
    ("wasp_in_a_box", {}),
]


@pytest.fixture(name="options_flow_entry")
async def setup_options_flow_entry(hass: HomeAssistant) -> AsyncGenerator[dict]:
    """Set up a real area with entities and every configurable feature enabled."""
    light = MockLight(
        name="flow_light", state="off", unique_id="flow_light", dimmable=True
    )
    motion = MockBinarySensor(
        name="flow_motion",
        unique_id="flow_motion",
        device_class=BinarySensorDeviceClass.MOTION,
    )
    movie_mode = MockBinarySensor(
        name="flow_movie_mode", unique_id="flow_movie_mode", device_class=None
    )
    climate = MockClimate(
        name="flow_climate",
        unique_id="flow_climate",
        preset_modes=["away", "home"],
    )

    await setup_mock_entities(hass, LIGHT_DOMAIN, {DEFAULT_MOCK_AREA: [light]})
    await setup_mock_entities(
        hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: [motion, movie_mode]}
    )
    await setup_mock_entities(hass, CLIMATE_DOMAIN, {DEFAULT_MOCK_AREA: [climate]})

    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    data[ConfigDomains.FEATURES] = {feature: {} for feature in CONFIGURABLE_FEATURES}

    config_entry = MockConfigEntry(domain=DOMAIN, data=data, options=data)
    await init_integration(hass, [config_entry])

    yield {
        "config_entry": config_entry,
        "light_id": light.entity_id,
        "movie_mode_id": movie_mode.entity_id,
        "climate_id": climate.entity_id,
    }

    await shutdown_integration(hass, [config_entry])


async def _start_flow(hass: HomeAssistant, config_entry: MockConfigEntry) -> dict:
    """Start the options flow and return the main menu."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "show_menu"
    return dict(result)


async def _goto(hass: HomeAssistant, flow_id: str, step_id: str) -> dict:
    """Navigate a menu to the given step."""
    return dict(
        await hass.config_entries.options.async_configure(
            flow_id, {"next_step_id": step_id}
        )
    )


async def _submit(
    hass: HomeAssistant, flow_id: str, user_input: dict[str, Any]
) -> dict:
    """Submit a form."""
    return dict(await hass.config_entries.options.async_configure(flow_id, user_input))


async def _direct_flow(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> OptionsFlowHandler:
    """Create an initialized options flow to exercise defensive branches."""
    flow = OptionsFlowHandler(config_entry)
    flow.hass = hass
    flow.handler = config_entry.entry_id
    await flow.async_step_init()
    return flow


class TestMainMenu:
    """Test the options flow main menu."""

    async def test_menu_lists_configured_features(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test that every enabled configurable feature gets a menu entry."""
        result = await _start_flow(hass, options_flow_entry["config_entry"])

        for feature in CONFIGURABLE_FEATURES:
            assert f"feature_{feature}" in result["menu_options"]
        assert result["menu_options"][-1] == "finish"

    @pytest.mark.parametrize(
        "step_id", ["area_config", "presence_tracking", "secondary_states"]
    )
    async def test_domain_forms_return_to_menu(
        self, hass: HomeAssistant, options_flow_entry, step_id: str
    ):
        """Test submitting the core configuration forms."""
        result = await _start_flow(hass, options_flow_entry["config_entry"])

        result = await _goto(hass, result["flow_id"], step_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == step_id

        result = await _submit(hass, result["flow_id"], {})
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "show_menu"

    async def test_finish_persists_feature_options(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test that configured feature options are saved when finishing."""
        result = await _start_flow(hass, options_flow_entry["config_entry"])
        flow_id = result["flow_id"]

        await _goto(hass, flow_id, "feature_presence_hold")
        await _submit(hass, flow_id, {PresenceHoldOptions.TIMEOUT.key: 5})
        result = await _goto(hass, flow_id, "finish")
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        saved = result["data"][ConfigDomains.FEATURES]["presence_hold"]
        assert saved[PresenceHoldOptions.TIMEOUT.key] == 5


class TestFeatureSteps:
    """Test feature configuration steps through the real flow."""

    @pytest.mark.parametrize(("feature_id", "user_input"), SIMPLE_FEATURE_INPUTS)
    async def test_simple_feature_round_trip(
        self,
        hass: HomeAssistant,
        options_flow_entry,
        feature_id: str,
        user_input: dict[str, Any],
    ):
        """Test entering and submitting a single-form feature."""
        result = await _start_flow(hass, options_flow_entry["config_entry"])

        result = await _goto(hass, result["flow_id"], f"feature_{feature_id}")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == f"feature_{feature_id}"

        result = await _submit(hass, result["flow_id"], user_input)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "show_menu"

    async def test_fan_groups_form_is_shown(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test the fan groups form renders through the real flow."""
        result = await _start_flow(hass, options_flow_entry["config_entry"])

        result = await _goto(hass, result["flow_id"], "feature_fan_groups")

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "feature_fan_groups"

    async def test_fan_groups_submit_saves_and_returns_to_menu(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test submitting the fan groups form through the real flow."""
        result = await _start_flow(hass, options_flow_entry["config_entry"])
        flow_id = result["flow_id"]

        await _goto(hass, flow_id, "feature_fan_groups")
        result = await _submit(
            hass,
            flow_id,
            {
                FanGroupOptions.REQUIRED_STATE.key: "occupied",
                FanGroupOptions.TRACKED_DEVICE_CLASS.key: "humidity",
                FanGroupOptions.SETPOINT.key: 25.0,
            },
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "show_menu"

        result = await _goto(hass, flow_id, "finish")
        await hass.async_block_till_done()

        saved = result["data"][ConfigDomains.FEATURES]["fan_groups"]
        assert saved[FanGroupOptions.TRACKED_DEVICE_CLASS.key] == "humidity"
        assert saved[FanGroupOptions.SETPOINT.key] == 25.0

    async def test_fan_groups_rejects_unsupported_device_class(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test a device class that fan groups cannot track is rejected."""
        result = await _start_flow(hass, options_flow_entry["config_entry"])
        flow_id = result["flow_id"]

        await _goto(hass, flow_id, "feature_fan_groups")
        with pytest.raises(InvalidData):
            await _submit(
                hass,
                flow_id,
                {FanGroupOptions.TRACKED_DEVICE_CLASS.key: "illuminance"},
            )

    async def test_fan_groups_requires_tracked_class_to_be_aggregated(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test the tracked device class must be aggregated by the Aggregates feature."""
        result = await _start_flow(hass, options_flow_entry["config_entry"])
        flow_id = result["flow_id"]

        await _goto(hass, flow_id, "feature_fan_groups")
        result = await _submit(
            hass,
            flow_id,
            {FanGroupOptions.TRACKED_DEVICE_CLASS.key: "carbon_dioxide"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "feature_fan_groups"
        assert result["errors"] == {
            FanGroupOptions.TRACKED_DEVICE_CLASS.key: "tracked_device_class_not_aggregated"
        }

    async def test_fan_groups_requires_aggregates_feature(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test fan groups cannot be configured while Aggregates is disabled."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])
        flow.area_options[ConfigDomains.FEATURES].pop("aggregates")

        await flow.async_step_feature_fan_groups(None)
        result = await flow.async_step_feature_fan_groups({})

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {
            FanGroupOptions.TRACKED_DEVICE_CLASS.key: "aggregates_required"
        }
        assert "setpoint" not in flow.area_options[ConfigDomains.FEATURES]["fan_groups"]

    async def test_light_groups_add_edit_delete(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test the complete light group lifecycle."""
        light_id = options_flow_entry["light_id"]
        result = await _start_flow(hass, options_flow_entry["config_entry"])
        flow_id = result["flow_id"]

        result = await _goto(hass, flow_id, "feature_light_groups")
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "feature_light_groups"
        assert "feature_light_groups_select_group" not in result["menu_options"]

        # Add: first with invalid data, then valid
        result = await _goto(hass, flow_id, "feature_light_groups_add_group")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "feature_light_groups_add_group"

        result = await _submit(
            hass,
            flow_id,
            {
                LightGroupEntryOptions.NAME.key: "",
                LightGroupEntryOptions.LIGHTS.key: [],
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {
            "name": "malformed_input",
            "lights": "no_lights_selected",
        }

        result = await _submit(
            hass,
            flow_id,
            {
                LightGroupEntryOptions.NAME.key: "Reading",
                LightGroupEntryOptions.LIGHTS.key: [light_id],
            },
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "feature_light_groups"
        assert "feature_light_groups_select_group" in result["menu_options"]
        assert "feature_light_groups_delete_group" in result["menu_options"]

        # Edit
        result = await _goto(hass, flow_id, "feature_light_groups_select_group")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "feature_light_groups_select_group"

        result = await _submit(hass, flow_id, {"group_index": 0})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "feature_light_groups_edit_group"

        result = await _submit(
            hass,
            flow_id,
            {
                LightGroupEntryOptions.NAME.key: "Reading Nook",
                LightGroupEntryOptions.LIGHTS.key: [light_id],
            },
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "feature_light_groups"

        # Delete
        result = await _goto(hass, flow_id, "feature_light_groups_delete_group")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "feature_light_groups_delete_group"

        result = await _submit(hass, flow_id, {"group_index": 0, "confirm": True})
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "feature_light_groups"
        assert "feature_light_groups_select_group" not in result["menu_options"]

    async def test_climate_control_two_step_flow(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test the climate control entity then presets steps."""
        result = await _start_flow(hass, options_flow_entry["config_entry"])
        flow_id = result["flow_id"]

        result = await _goto(hass, flow_id, "feature_climate_control")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "feature_climate_control"

        result = await _submit(
            hass,
            flow_id,
            {ClimateControlOptions.ENTITY_ID.key: options_flow_entry["climate_id"]},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "feature_climate_control_select_presets"

        result = await _submit(
            hass, flow_id, {ClimateControlOptions.PRESET_CLEAR.key: "away"}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "show_menu"

    async def test_climate_control_presets_step_without_entity_restarts(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test entering the presets step directly goes back to entity selection."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])

        result = await flow.async_step_feature_climate_control_select_presets(None)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "feature_climate_control"


class TestFeatureDispatch:
    """Test the defensive branches of the feature dispatcher."""

    async def test_no_current_feature_returns_menu(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test dispatching without a current feature goes back to the menu."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])
        flow._current_feature = None

        result = await flow.async_step_feature(None)

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "show_menu"

    async def test_unknown_feature_returns_menu(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test dispatching an unregistered feature goes back to the menu."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])
        flow._current_feature = "does_not_exist"

        result = await flow.async_step_feature(None)

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "show_menu"

    async def test_unsupported_result_type_returns_menu(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test a handler result that is not form/menu/create_entry returns the menu."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])
        handler = flow._feature_handlers["presence_hold"]
        flow._current_feature = "presence_hold"

        with patch.object(
            handler,
            "handle_step",
            AsyncMock(return_value=StepResult(type="abort")),
        ):
            result = await flow.async_step_feature(None)

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "show_menu"

    async def test_non_initial_menu_step_uses_feature_specific_step_id(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test a menu from a non-initial step gets a feature-specific step id."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])
        handler = flow._feature_handlers["light_groups"]
        flow._current_feature = "light_groups"
        flow._current_feature_step = "sub_menu"

        with patch.object(
            handler,
            "handle_step",
            AsyncMock(
                return_value=StepResult(
                    type="menu", step_id="sub_menu", menu_options=["show_menu"]
                )
            ),
        ):
            result = await flow.async_step_feature(None)

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "feature_light_groups_sub_menu"

    async def test_light_groups_wrappers_route_input_and_entry(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test the light group wrappers for both entry and submitted input."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])

        entered = await flow.async_step_feature_light_groups(None)
        assert entered["type"] is FlowResultType.MENU
        assert entered["step_id"] == "feature_light_groups"

        submitted = await flow.async_step_feature_light_groups({})
        assert submitted["type"] is FlowResultType.MENU
        assert submitted["step_id"] == "feature_light_groups"

        edit = await flow.async_step_feature_light_groups_edit_group(None)
        assert edit["type"] is FlowResultType.FORM
        assert edit["step_id"] == "feature_light_groups_edit_group"


class TestUserDefinedStatesSteps:
    """Test the user-defined states steps of the options flow."""

    async def test_add_edit_delete_lifecycle(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test adding, editing and deleting a state through the real flow."""
        entity_id = options_flow_entry["movie_mode_id"]
        result = await _start_flow(hass, options_flow_entry["config_entry"])
        flow_id = result["flow_id"]

        # Main menu of the domain: only "add" is offered while empty
        result = await _goto(hass, flow_id, "user_defined_states")
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user_defined_states"
        assert "user_defined_states_select_state" not in result["menu_options"]

        # Add
        result = await _goto(hass, flow_id, "user_defined_states_add_state")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user_defined_states_add_state"

        result = await _submit(
            hass,
            flow_id,
            {
                UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                UserDefinedStateEntryOptions.ENTITY.key: entity_id,
            },
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user_defined_states"
        assert "user_defined_states_select_state" in result["menu_options"]

        # Select, which transitions into the edit form
        result = await _goto(hass, flow_id, "user_defined_states_select_state")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user_defined_states_select_state"

        result = await _submit(hass, flow_id, {"state_index": 0})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user_defined_states_edit_state"

        result = await _submit(
            hass,
            flow_id,
            {
                UserDefinedStateEntryOptions.NAME.key: "Cinema Mode",
                UserDefinedStateEntryOptions.ENTITY.key: entity_id,
            },
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user_defined_states"

        # Delete
        result = await _goto(hass, flow_id, "user_defined_states_delete_state")
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user_defined_states_delete_state"

        result = await _submit(hass, flow_id, {"state_index": 0, "confirm": True})
        assert result["type"] is FlowResultType.MENU
        assert "user_defined_states_select_state" not in result["menu_options"]

    async def test_add_state_validation_error_keeps_form(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test an invalid state shows the form again with errors."""
        result = await _start_flow(hass, options_flow_entry["config_entry"])
        flow_id = result["flow_id"]

        await _goto(hass, flow_id, "user_defined_states")
        await _goto(hass, flow_id, "user_defined_states_add_state")
        result = await _submit(
            hass,
            flow_id,
            {
                UserDefinedStateEntryOptions.NAME.key: "",
                UserDefinedStateEntryOptions.ENTITY.key: "",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user_defined_states_add_state"
        assert result["errors"]

    async def test_select_state_invalid_index_returns_domain_menu(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test selecting a state that does not exist returns to the state menu."""
        entity_id = options_flow_entry["movie_mode_id"]
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])
        flow.area_options[ConfigDomains.USER_DEFINED_STATES.value] = {
            UserDefinedStateOptions.STATES.key: [
                {
                    UserDefinedStateEntryOptions.NAME.key: "Movie Time",
                    UserDefinedStateEntryOptions.ENTITY.key: entity_id,
                }
            ]
        }

        result = await flow.async_step_user_defined_states_select_state(
            {"state_index": 5}
        )

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user_defined_states"

    @pytest.mark.parametrize(
        "step_method",
        [
            "async_step_user_defined_states_add_state",
            "async_step_user_defined_states_select_state",
            "async_step_user_defined_states_edit_state",
            "async_step_user_defined_states_delete_state",
        ],
    )
    async def test_unexpected_result_returns_domain_menu(
        self, hass: HomeAssistant, options_flow_entry, step_method: str
    ):
        """Test a handler result of an unknown type returns to the state menu."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])
        real_handle_step = UserDefinedStatesHandler.handle_step

        async def fake_handle_step(self, step_id, user_input):
            if step_id == "main":
                return await real_handle_step(self, step_id, user_input)
            return DomainStepResult(type="abort")

        with patch.object(UserDefinedStatesHandler, "handle_step", fake_handle_step):
            result = await getattr(flow, step_method)(None)

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user_defined_states"

    async def test_main_step_unexpected_result_returns_main_menu(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test the domain main step falls back to the options main menu."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])

        with patch.object(
            UserDefinedStatesHandler,
            "handle_step",
            AsyncMock(return_value=DomainStepResult(type="abort")),
        ):
            result = await flow.async_step_user_defined_states(None)

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "show_menu"

    @pytest.mark.parametrize(
        "step_method",
        [
            "async_step_user_defined_states",
            "async_step_user_defined_states_add_state",
            "async_step_user_defined_states_select_state",
            "async_step_user_defined_states_edit_state",
            "async_step_user_defined_states_delete_state",
        ],
    )
    async def test_create_entry_result_returns_main_menu(
        self, hass: HomeAssistant, options_flow_entry, step_method: str
    ):
        """Test a create_entry result from the handler returns to the main menu."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])

        with patch.object(
            UserDefinedStatesHandler,
            "handle_step",
            AsyncMock(return_value=DomainStepResult(type="create_entry")),
        ):
            result = await getattr(flow, step_method)(None)

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "show_menu"

    async def test_main_step_form_result_is_shown(
        self, hass: HomeAssistant, options_flow_entry
    ):
        """Test a form result from the domain main step is rendered."""
        flow = await _direct_flow(hass, options_flow_entry["config_entry"])

        with patch.object(
            UserDefinedStatesHandler,
            "handle_step",
            AsyncMock(
                return_value=DomainStepResult(
                    type="form", step_id="custom", data_schema=vol.Schema({})
                )
            ),
        ):
            result = await flow.async_step_user_defined_states(None)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user_defined_states_custom"
