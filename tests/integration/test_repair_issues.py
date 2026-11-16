"""Tests for the Magic Areas repair issues."""

import copy
import json
import pathlib

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.area_registry import async_get as async_get_ar
from homeassistant.setup import async_setup_component

from custom_components.magic_areas.const import DOMAIN, MagicAreasIssue
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.fan_groups import FanGroupOptions
from custom_components.magic_areas.const.wasp_in_a_box import WaspInABoxOptions
from custom_components.magic_areas.helpers.issues import ISSUE_DATA_ENTRY_ID
from custom_components.magic_areas.repairs import (
    AreaNotFoundRepairFlow,
    async_create_fix_flow,
)

from tests.const import DEFAULT_MOCK_AREA
from tests.helpers import (
    get_basic_config_entry_data,
    init_integration,
    merge_feature_config,
    setup_mock_entities,
    shutdown_integration,
)
from tests.mocks import MockBinarySensor

COMPONENT_PATH = pathlib.Path(__file__).parents[2] / "custom_components" / "magic_areas"
TRANSLATIONS_PATH = COMPONENT_PATH / "translations" / "en.json"
STRINGS_PATH = COMPONENT_PATH / "strings.json"


def _entry_issues(hass: HomeAssistant) -> dict[str, ir.IssueEntry]:
    """Return the Magic Areas issues by issue id."""
    registry = ir.async_get(hass)
    return {
        issue_id: issue
        for (domain, issue_id), issue in registry.issues.items()
        if domain == DOMAIN
    }


def _issue_id(issue: MagicAreasIssue, entry: MockConfigEntry, suffix: str = "") -> str:
    issue_id = f"{issue.value}_{entry.entry_id}"
    return f"{issue_id}_{suffix}" if suffix else issue_id


def _wasp_entry(
    *, aggregates: bool = True, min_entities: int = 1, classes: list[str] | None = None
) -> MockConfigEntry:
    """Build an entry with Wasp in a Box (and optionally Aggregates)."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    configs = [WaspInABoxOptions.to_config({WaspInABoxOptions.DELAY.key: 0})]
    if aggregates:
        options: dict = {AggregateOptions.MIN_ENTITIES.key: min_entities}
        if classes is not None:
            options[AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key] = classes
        configs.append(AggregateOptions.to_config(options))
    merge_feature_config(data, *configs)
    return MockConfigEntry(domain=DOMAIN, data=data)


async def _add_sensors(
    hass: HomeAssistant, *device_classes: BinarySensorDeviceClass
) -> None:
    sensors = [
        MockBinarySensor(
            name=f"{device_class}_sensor",
            unique_id=f"unique_{device_class}",
            device_class=device_class,
        )
        for device_class in device_classes
    ]
    await setup_mock_entities(hass, BINARY_SENSOR_DOMAIN, {DEFAULT_MOCK_AREA: sensors})


# Translations


def test_every_issue_has_translations() -> None:
    """Every issue key has text in strings.json and en.json."""
    for path in (STRINGS_PATH, TRANSLATIONS_PATH):
        issues = json.loads(path.read_text())["issues"]
        for issue in MagicAreasIssue:
            assert issue.value in issues, f"{issue.value} missing from {path.name}"
            assert issues[issue.value]["title"]
            assert issues[issue.value]["description"]


def test_translations_match_strings() -> None:
    """The issue translations are the same in strings.json and en.json."""
    assert (
        json.loads(STRINGS_PATH.read_text())["issues"]
        == json.loads(TRANSLATIONS_PATH.read_text())["issues"]
    )


# Area not found


async def _setup_missing_area_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry whose area is not in the area registry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ghost",
        data=get_basic_config_entry_data(DEFAULT_MOCK_AREA),
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return entry


async def test_missing_area_raises_fixable_issue(hass: HomeAssistant) -> None:
    """An entry for a deleted area fails cleanly and raises a fixable issue."""
    entry = await _setup_missing_area_entry(hass)

    assert entry.state is ConfigEntryState.SETUP_ERROR

    issue = _entry_issues(hass)[_issue_id(MagicAreasIssue.AREA_NOT_FOUND, entry)]
    assert issue.is_fixable
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_key == MagicAreasIssue.AREA_NOT_FOUND
    assert issue.translation_placeholders == {
        "area_name": "Ghost",
        "area_id": DEFAULT_MOCK_AREA.value,
    }
    assert issue.data == {ISSUE_DATA_ENTRY_ID: entry.entry_id}


async def test_missing_area_fix_flow_removes_entry(hass: HomeAssistant) -> None:
    """Confirming the fix flow removes the entry and its issue."""
    entry = await _setup_missing_area_entry(hass)
    issue_id = _issue_id(MagicAreasIssue.AREA_NOT_FOUND, entry)
    issue = _entry_issues(hass)[issue_id]

    flow = await async_create_fix_flow(hass, issue_id, issue.data)
    assert isinstance(flow, AreaNotFoundRepairFlow)
    flow.hass = hass
    flow.handler = DOMAIN
    flow.issue_id = issue_id

    result = await flow.async_step_init()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert issue_id not in _entry_issues(hass)


async def test_missing_area_fix_flow_entry_already_removed(
    hass: HomeAssistant,
) -> None:
    """The fix flow still completes when the entry is already gone."""
    flow = await async_create_fix_flow(
        hass, "area_not_found_gone", {ISSUE_DATA_ENTRY_ID: "does_not_exist"}
    )
    flow.hass = hass
    flow.handler = DOMAIN

    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_missing_area_issue_clears_when_area_exists(
    hass: HomeAssistant,
) -> None:
    """Restoring the area and reloading the entry clears the issue."""
    entry = await _setup_missing_area_entry(hass)
    issue_id = _issue_id(MagicAreasIssue.AREA_NOT_FOUND, entry)
    assert issue_id in _entry_issues(hass)

    # Restore the area, then reload the entry.
    async_get_ar(hass).async_create(name=DEFAULT_MOCK_AREA.value)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    try:
        assert entry.state is ConfigEntryState.LOADED
        assert issue_id not in _entry_issues(hass)
    finally:
        await shutdown_integration(hass, [entry])


async def test_removing_entry_deletes_its_issues(hass: HomeAssistant) -> None:
    """Removing an entry removes every issue belonging to it."""
    entry = _wasp_entry(aggregates=False)
    await init_integration(hass, [entry])
    assert _entry_issues(hass)

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert not _entry_issues(hass)


# Missing aggregates


async def test_wasp_without_aggregates_raises_issue(hass: HomeAssistant) -> None:
    """Wasp in a Box without Aggregates raises only the dependency issue."""
    entry = _wasp_entry(aggregates=False)
    await init_integration(hass, [entry])
    try:
        issues = _entry_issues(hass)
        issue_id = _issue_id(MagicAreasIssue.MISSING_AGGREGATES, entry, "wasp_in_a_box")
        assert list(issues) == [issue_id]

        issue = issues[issue_id]
        assert not issue.is_fixable
        assert issue.severity == ir.IssueSeverity.WARNING
        assert issue.translation_key == MagicAreasIssue.MISSING_AGGREGATES
        assert issue.translation_placeholders is not None
        assert issue.translation_placeholders["feature_name"] == "Wasp in a Box"
    finally:
        await shutdown_integration(hass, [entry])


async def test_fan_groups_without_aggregates_raises_issue(
    hass: HomeAssistant,
) -> None:
    """Fan Groups without Aggregates raises the dependency issue."""
    data = get_basic_config_entry_data(DEFAULT_MOCK_AREA)
    merge_feature_config(data, FanGroupOptions.to_config({}))
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    await init_integration(hass, [entry])
    try:
        issue_id = _issue_id(MagicAreasIssue.MISSING_AGGREGATES, entry, "fan_groups")
        issue = _entry_issues(hass)[issue_id]
        assert issue.translation_placeholders is not None
        assert issue.translation_placeholders["feature_name"] == "Fan Groups"
    finally:
        await shutdown_integration(hass, [entry])


async def test_missing_aggregates_issue_clears_when_enabled(
    hass: HomeAssistant,
) -> None:
    """Enabling Aggregates (which reloads the entry) clears the issue."""
    entry = _wasp_entry(aggregates=False)
    await init_integration(hass, [entry])
    try:
        issue_id = _issue_id(MagicAreasIssue.MISSING_AGGREGATES, entry, "wasp_in_a_box")
        assert issue_id in _entry_issues(hass)

        data = copy.deepcopy(dict(entry.data))
        merge_feature_config(
            data,
            AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
        )
        hass.config_entries.async_update_entry(entry, data=data)
        await hass.async_block_till_done()

        assert issue_id not in _entry_issues(hass)
    finally:
        await shutdown_integration(hass, [entry])


async def test_no_issues_when_wasp_is_complete(hass: HomeAssistant) -> None:
    """No issue is raised with Aggregates and both kinds of sensor present."""
    entry = _wasp_entry()
    await _add_sensors(
        hass, BinarySensorDeviceClass.MOTION, BinarySensorDeviceClass.DOOR
    )
    await init_integration(hass, [entry])
    try:
        assert not _entry_issues(hass)
    finally:
        await shutdown_integration(hass, [entry])


# Wasp in a Box sensors


async def test_wasp_no_sensors_raises_both_issues(hass: HomeAssistant) -> None:
    """An area with no wasp or box sensors raises both issues."""
    entry = _wasp_entry()
    await init_integration(hass, [entry])
    try:
        issues = _entry_issues(hass)
        for issue in (
            MagicAreasIssue.WASP_NO_WASP_SENSORS,
            MagicAreasIssue.WASP_NO_BOX_SENSORS,
        ):
            raised = issues[_issue_id(issue, entry)]
            assert not raised.is_fixable
            assert raised.severity == ir.IssueSeverity.WARNING
            assert raised.translation_key == issue
    finally:
        await shutdown_integration(hass, [entry])


async def test_wasp_missing_only_box_sensors(hass: HomeAssistant) -> None:
    """Only the box issue is raised when there is a wasp but no door."""
    entry = _wasp_entry()
    await _add_sensors(hass, BinarySensorDeviceClass.MOTION)
    await init_integration(hass, [entry])
    try:
        issues = _entry_issues(hass)
        assert _issue_id(MagicAreasIssue.WASP_NO_BOX_SENSORS, entry) in issues
        assert _issue_id(MagicAreasIssue.WASP_NO_WASP_SENSORS, entry) not in issues
    finally:
        await shutdown_integration(hass, [entry])


async def test_wasp_missing_only_wasp_sensors(hass: HomeAssistant) -> None:
    """Only the wasp issue is raised when there is a door but no motion."""
    entry = _wasp_entry()
    await _add_sensors(hass, BinarySensorDeviceClass.DOOR)
    await init_integration(hass, [entry])
    try:
        issues = _entry_issues(hass)
        assert _issue_id(MagicAreasIssue.WASP_NO_WASP_SENSORS, entry) in issues
        assert _issue_id(MagicAreasIssue.WASP_NO_BOX_SENSORS, entry) not in issues
    finally:
        await shutdown_integration(hass, [entry])


async def test_wasp_issue_when_aggregate_class_not_enabled(
    hass: HomeAssistant,
) -> None:
    """A door sensor whose device class isn't aggregated doesn't count."""
    entry = _wasp_entry(classes=[BinarySensorDeviceClass.MOTION])
    await _add_sensors(
        hass, BinarySensorDeviceClass.MOTION, BinarySensorDeviceClass.DOOR
    )
    await init_integration(hass, [entry])
    try:
        issues = _entry_issues(hass)
        assert _issue_id(MagicAreasIssue.WASP_NO_BOX_SENSORS, entry) in issues
        assert _issue_id(MagicAreasIssue.WASP_NO_WASP_SENSORS, entry) not in issues
    finally:
        await shutdown_integration(hass, [entry])


async def test_wasp_issue_when_below_min_entities(hass: HomeAssistant) -> None:
    """A device class below the aggregate minimum doesn't get an aggregate."""
    entry = _wasp_entry(min_entities=2)
    await _add_sensors(
        hass, BinarySensorDeviceClass.MOTION, BinarySensorDeviceClass.DOOR
    )
    await init_integration(hass, [entry])
    try:
        issues = _entry_issues(hass)
        assert _issue_id(MagicAreasIssue.WASP_NO_WASP_SENSORS, entry) in issues
        assert _issue_id(MagicAreasIssue.WASP_NO_BOX_SENSORS, entry) in issues
    finally:
        await shutdown_integration(hass, [entry])


async def test_wasp_issues_clear_when_aggregates_become_available(
    hass: HomeAssistant,
) -> None:
    """Fixing the aggregate configuration reloads the entry and clears the issues."""
    entry = _wasp_entry(min_entities=2)
    await _add_sensors(
        hass, BinarySensorDeviceClass.MOTION, BinarySensorDeviceClass.DOOR
    )
    await init_integration(hass, [entry])
    try:
        assert len(_entry_issues(hass)) == 2

        data = copy.deepcopy(dict(entry.data))
        merge_feature_config(
            data,
            AggregateOptions.to_config({AggregateOptions.MIN_ENTITIES.key: 1}),
        )
        hass.config_entries.async_update_entry(entry, data=data)
        await hass.async_block_till_done()

        assert not _entry_issues(hass)
    finally:
        await shutdown_integration(hass, [entry])


# Fix flow selection


@pytest.mark.parametrize(
    ("issue_id", "data"),
    [
        pytest.param("reserved_floor_id_exterior", None, id="other-issue"),
        pytest.param(
            MagicAreasIssue.AREA_NOT_FOUND.value, None, id="area-not-found-no-data"
        ),
    ],
)
async def test_other_issues_get_a_plain_confirm_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> None:
    """Issues without an entry to remove fall back to the standard confirm flow."""
    flow = await async_create_fix_flow(hass, issue_id, data)

    assert isinstance(flow, ConfirmRepairFlow)
    assert not isinstance(flow, AreaNotFoundRepairFlow)
