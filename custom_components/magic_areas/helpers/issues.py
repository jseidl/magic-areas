"""Magic Areas repair issue helpers.

Every issue created here carries its config entry id in the issue ``data`` so
the issues can be found and cleaned up when the entry is removed.
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
    async_get as async_get_issue_registry,
)

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.const import (
    CONF_AREA_ID,
    DOMAIN,
    Features,
    MagicAreasIssue,
)
from custom_components.magic_areas.helpers.aggregates import (
    get_wasp_in_a_box_available_device_classes,
)

_LOGGER = logging.getLogger(__name__)

ISSUE_DATA_ENTRY_ID = "entry_id"

# Features which can't work without the Aggregates feature.
FEATURES_REQUIRING_AGGREGATES: dict[str, str] = {
    Features.WASP_IN_A_BOX: "Wasp in a Box",
    Features.FAN_GROUPS: "Fan Groups",
}


def _issue_id(issue: MagicAreasIssue, entry: ConfigEntry, suffix: str = "") -> str:
    """Build the issue id for a config entry."""
    issue_id = f"{issue.value}_{entry.entry_id}"
    return f"{issue_id}_{suffix}" if suffix else issue_id


def _raise_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    issue: MagicAreasIssue,
    issue_id: str,
    placeholders: dict[str, str],
    *,
    log_message: str,
    severity: IssueSeverity = IssueSeverity.WARNING,
    is_fixable: bool = False,
) -> None:
    """Create or update an issue, logging only when it is first raised."""
    if async_get_issue_registry(hass).async_get_issue(DOMAIN, issue_id) is None:
        _LOGGER.warning(log_message)

    async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=is_fixable,
        severity=severity,
        translation_key=issue,
        translation_placeholders=placeholders,
        data={ISSUE_DATA_ENTRY_ID: entry.entry_id},
    )


def async_raise_area_not_found_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Raise the fixable issue for an entry whose area no longer exists."""
    _raise_issue(
        hass,
        entry,
        MagicAreasIssue.AREA_NOT_FOUND,
        _issue_id(MagicAreasIssue.AREA_NOT_FOUND, entry),
        {
            "area_name": entry.title,
            "area_id": str(entry.data.get(CONF_AREA_ID)),
        },
        severity=IssueSeverity.ERROR,
        is_fixable=True,
        log_message=(
            f"{entry.title}: Area '{entry.data.get(CONF_AREA_ID)}' not found "
            "on registry. Remove this entry or restore the area."
        ),
    )


def async_clear_area_not_found_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear the missing area issue for an entry."""
    async_delete_issue(hass, DOMAIN, _issue_id(MagicAreasIssue.AREA_NOT_FOUND, entry))


def async_delete_entry_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete every issue which belongs to a config entry."""
    issue_registry = async_get_issue_registry(hass)
    for domain, issue_id in list(issue_registry.issues):
        if domain != DOMAIN:
            continue
        issue = issue_registry.issues[(domain, issue_id)]
        if (issue.data or {}).get(ISSUE_DATA_ENTRY_ID) == entry.entry_id:
            async_delete_issue(hass, DOMAIN, issue_id)


def async_update_dependency_issues(
    hass: HomeAssistant, entry: ConfigEntry, area: MagicArea
) -> None:
    """Raise or clear the feature dependency issues of an area.

    Checks are made from the area's entities and configuration instead of the
    state machine, so an aggregate which doesn't exist *yet* (still starting up)
    is not reported, and an issue clears itself as soon as the area is set up
    again with the dependency in place.
    """
    for feature, feature_name in FEATURES_REQUIRING_AGGREGATES.items():
        issue_id = _issue_id(MagicAreasIssue.MISSING_AGGREGATES, entry, str(feature))
        if (
            area.is_meta()
            or not area.has_feature(feature)
            or area.has_feature(Features.AGGREGATION)
        ):
            async_delete_issue(hass, DOMAIN, issue_id)
            continue

        _raise_issue(
            hass,
            entry,
            MagicAreasIssue.MISSING_AGGREGATES,
            issue_id,
            {"area_name": area.name, "feature_name": feature_name},
            log_message=(
                f"{area.name}: {feature_name} feature requires Aggregates "
                "feature to be enabled. Please enable Aggregates in the area "
                "configuration."
            ),
        )

    _update_wasp_in_a_box_issues(hass, entry, area)


def _update_wasp_in_a_box_issues(
    hass: HomeAssistant, entry: ConfigEntry, area: MagicArea
) -> None:
    """Raise or clear the Wasp in a Box missing sensor issues."""
    wasp_issue_id = _issue_id(MagicAreasIssue.WASP_NO_WASP_SENSORS, entry)
    box_issue_id = _issue_id(MagicAreasIssue.WASP_NO_BOX_SENSORS, entry)

    # Without the feature (or aggregates, which has its own issue) there is
    # nothing more to report.
    if (
        area.is_meta()
        or not area.has_feature(Features.WASP_IN_A_BOX)
        or not area.has_feature(Features.AGGREGATION)
    ):
        async_delete_issue(hass, DOMAIN, wasp_issue_id)
        async_delete_issue(hass, DOMAIN, box_issue_id)
        return

    wasp_classes, box_classes = get_wasp_in_a_box_available_device_classes(area)

    if wasp_classes:
        async_delete_issue(hass, DOMAIN, wasp_issue_id)
    else:
        _raise_issue(
            hass,
            entry,
            MagicAreasIssue.WASP_NO_WASP_SENSORS,
            wasp_issue_id,
            {"area_name": area.name},
            log_message=(
                f"{area.name}: Wasp in a Box has no motion, occupancy or presence "
                "aggregate to use as the wasp, so it will never detect presence."
            ),
        )

    if box_classes:
        async_delete_issue(hass, DOMAIN, box_issue_id)
    else:
        _raise_issue(
            hass,
            entry,
            MagicAreasIssue.WASP_NO_BOX_SENSORS,
            box_issue_id,
            {"area_name": area.name},
            log_message=(
                f"{area.name}: Wasp in a Box has no door or garage door aggregate "
                "to use as the box, so it will never detect presence."
            ),
        )
