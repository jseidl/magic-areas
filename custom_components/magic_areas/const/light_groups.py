"""Light groups feature constants."""

from enum import StrEnum, auto
import logging

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

LIGHT_GROUP_CONTEXT_PREFIX = "MAGICAREAS_LG_CTX"


class LightGroupAttributes(StrEnum):
    """Attributes for Magic Light group."""

    MODE = auto()


class LightGroupOperationMode(StrEnum):
    """Operating modes for Magic light group."""

    MANUAL = auto()
    MAGIC = auto()


class LightGroupAllLightsConfig(StrEnum):
    """Attributes for the All Lights group."""

    NAME = "all_lights"
    ICON = "mdi:infinity"


# ============================================================================
# Config Enums
# ============================================================================


class LightGroupTurnOnWhen(StrEnum):
    """When light groups should turn on lights."""

    AREA_OCCUPIED = auto()  # Turn on when area transitions from clear to occupied
    STATE_GAIN = (
        auto()
    )  # Turn on when area gains a configured state while already occupied
    AREA_DARK = auto()  # Turn on when area gains dark state while occupied


class LightGroupTurnOffWhen(StrEnum):
    """When light groups should turn off lights."""

    AREA_CLEAR = auto()  # Turn off when area becomes unoccupied
    STATE_LOSS = auto()  # Turn off when area loses all configured states
    EXTERIOR_BRIGHT = (
        auto()
    )  # Turn off when exterior becomes bright (exterior area → sun.sun fallback)


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

    NAME = ConfigOption(
        key="name",
        default="",
        required=True,
        validator=cv.string,
        selector_type="text",
        selector_config={},
        title="Group Name",
        description="Name for this light group",
    )

    LIGHTS = ConfigOption(
        key="lights",
        default=[],
        required=True,
        validator=cv.entity_ids,
        selector_type="entity",
        selector_config={"options": [], "multiple": True},
        title="Lights",
        description="Light entities in this group",
    )

    STATES = ConfigOption(
        key="states",
        default=["occupied"],
        required=True,
        validator=cv.ensure_list,
        selector_type="select",
        selector_config={"options": [], "multiple": True},
        title="Active States",
        description="Area states when this group should be active",
    )

    TURN_ON_WHEN = ConfigOption(
        key="turn_on_when",
        default=[
            LightGroupTurnOnWhen.AREA_OCCUPIED.value,
            LightGroupTurnOnWhen.STATE_GAIN.value,
            LightGroupTurnOnWhen.AREA_DARK.value,
        ],
        required=True,
        validator=cv.ensure_list,
        selector_type="select",
        selector_config={
            "options": [cls.value for cls in LightGroupTurnOnWhen],
            "multiple": True,
            "translation_key": "turn_on_when",
        },
        title="Turn On When",
        description="When to turn on lights",
    )

    TURN_OFF_WHEN = ConfigOption(
        key="turn_off_when",
        default=[
            LightGroupTurnOffWhen.AREA_CLEAR.value,
            LightGroupTurnOffWhen.STATE_LOSS.value,
            LightGroupTurnOffWhen.EXTERIOR_BRIGHT.value,
        ],
        required=True,
        validator=cv.ensure_list,
        selector_type="select",
        selector_config={
            "options": [cls.value for cls in LightGroupTurnOffWhen],
            "multiple": True,
            "translation_key": "turn_off_when",
        },
        title="Turn Off When",
        description="When to turn off lights. Leave empty to never turn off automatically (lights stay on until manually turned off).",
    )

    REQUIRE_DARK = ConfigOption(
        key="require_dark",
        default=True,
        required=True,
        validator=cv.boolean,
        selector_type="boolean",
        title="Require Dark",
        description="Only turn on if area is dark. Uses area light sensor, falling back to exterior area and sun.sun. Disable for windowless areas or lights that should turn on regardless of brightness.",
    )


# ============================================================================
# Helper Functions
# ============================================================================


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
    return slugify_group_name(name) != slugify_group_name(
        LightGroupAllLightsConfig.NAME.value
    )


def validate_group_name_unique(
    name: str, existing_groups: list[dict], exclude_index: int | None = None
) -> bool:
    """Check if group name is unique.

    Args:
        name: Group name to validate
        existing_groups: List of existing groups
        exclude_index: Index to exclude from check (for editing)

    Returns:
        True if name is unique, False otherwise

    """
    for idx, group in enumerate(existing_groups):
        if exclude_index is not None and idx == exclude_index:
            continue
        if group.get("name", "").lower() == name.lower():
            return False
    return True
