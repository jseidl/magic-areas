"""Light groups feature constants."""

import logging
import uuid
from enum import StrEnum

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from custom_components.magic_areas.const import (
    ConfigDomains,
    ConfigOption,
    FeatureOptionSet,
    OptionSet,
)

_LOGGER = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

LIGHT_GROUP_ALL = "all_lights"
LIGHT_GROUP_ALL_ICON = "mdi:infinity"


# ============================================================================
# Enums
# ============================================================================


class LightGroupActOn(StrEnum):
    """When light groups should act on area state changes."""

    OCCUPANCY = "occupancy"  # Only turns on if area just changed from clear to occupied
    STATE = "state"  # Turn on at state change regardless if area was already occupied


# ============================================================================
# Feature Configuration
# ============================================================================


class LightGroupOptions(FeatureOptionSet):
    """Light groups feature configuration options."""

    CONFIG_DOMAIN = ConfigDomains.FEATURES
    FEATURE_KEY = "light_groups"

    GROUPS = ConfigOption(
        key="groups",
        default=[],
        validator=cv.ensure_list,
    )


class LightGroupEntryOptions(OptionSet):
    """Configuration schema for a single light group entry."""

    CONFIG_DOMAIN = ConfigDomains.FEATURES

    UUID = ConfigOption(
        key="uuid",
        default="",
        required=True,
        validator=cv.string,
        internal=True,  # Never show to user - auto-generated
    )

    NAME = ConfigOption(
        key="name",
        default="",
        required=True,
        validator=cv.string,
        title="Group Name",
        description="Name for this light group",
    )

    LIGHTS = ConfigOption(
        key="lights",
        default=[],
        required=True,
        validator=cv.entity_ids,
        title="Lights",
        description="Light entities in this group",
    )

    STATES = ConfigOption(
        key="states",
        default=["occupied"],
        required=True,
        validator=cv.ensure_list,
        title="Active States",
        description="Area states when this group should be active",
    )

    ACT_ON = ConfigOption(
        key="act_on",
        default=["occupancy", "state"],
        required=True,
        validator=cv.ensure_list,
        title="Act On",
        description="When to act on state changes",
    )

    ICON = ConfigOption(
        key="icon",
        default="mdi:lightbulb-group",
        validator=cv.icon,
        title="Icon",
        description="Icon for this group",
    )


# ============================================================================
# Helper Functions
# ============================================================================


def generate_group_uuid() -> str:
    """Generate a new UUID for a group."""
    return str(uuid.uuid4())


def slugify_group_name(name: str) -> str:
    """Generate slug from group name for use in entity IDs."""
    return slugify(name)


def validate_group_name(name: str) -> bool:
    """Validate that group name doesn't conflict with reserved names.

    Args:
        name: User-provided group name

    Returns:
        True if name is valid, False if it conflicts with reserved names
    """
    return slugify_group_name(name) != slugify_group_name(LIGHT_GROUP_ALL)


def validate_group_name_unique(
    name: str, existing_groups: list[dict], exclude_uuid: str | None = None
) -> bool:
    """Check if group name is unique.

    Args:
        name: Group name to validate
        existing_groups: List of existing groups
        exclude_uuid: UUID to exclude from check (for editing)

    Returns:
        True if name is unique, False otherwise
    """
    for group in existing_groups:
        if exclude_uuid and group.get("uuid") == exclude_uuid:
            continue
        if group.get("name", "").lower() == name.lower():
            return False
    return True
