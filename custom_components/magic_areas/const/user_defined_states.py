"""User-defined states configuration constants."""

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from custom_components.magic_areas.const import (
    AreaStates,
    ConfigDomains,
    ConfigOption,
    OptionSet,
)

# Reserved state names that cannot be used for user-defined states
RESERVED_STATE_NAMES = [
    AreaStates.OCCUPIED.value,
    AreaStates.CLEAR.value,
    AreaStates.DARK.value,
    AreaStates.BRIGHT.value,
    AreaStates.SLEEP.value,
    AreaStates.EXTENDED.value,
]


class UserDefinedStateOptions(OptionSet):
    """User-defined states configuration options."""

    CONFIG_DOMAIN = ConfigDomains.USER_DEFINED_STATES

    STATES = ConfigOption(
        key="states",
        default=[],
        validator=cv.ensure_list,
    )


class UserDefinedStateEntryOptions(OptionSet):
    """Configuration schema for a single user-defined state entry."""

    CONFIG_DOMAIN = ConfigDomains.USER_DEFINED_STATES

    NAME = ConfigOption(
        key="name",
        default="",
        required=True,
        validator=cv.string,
        selector_type="text",
        selector_config={},
        title="State Name",
        description="Name for this custom state (e.g., 'Gaming', 'Movie Time')",
    )

    ENTITY = ConfigOption(
        key="entity",
        default="",
        required=True,
        validator=cv.entity_id,
        selector_type="entity",
        selector_config={},
        title="Entity",
        description="Binary sensor, switch, or input_boolean that tracks this state",
    )

    @classmethod
    def from_user_input(cls, user_input: dict) -> dict:
        """Create state entry dict from user input.

        Args:
            user_input: User input from config flow form

        Returns:
            State entry dict with name and entity

        """
        return {
            cls.NAME.key: user_input.get(cls.NAME.key, "").strip(),
            cls.ENTITY.key: user_input.get(cls.ENTITY.key, ""),
        }


# Helper functions


def slugify_state_name(name: str) -> str:
    """Generate slug from state name for use as state value."""
    return slugify(name)


def validate_state_name(name: str) -> bool:
    """Validate that state name doesn't conflict with reserved names.

    Args:
        name: User-provided state name

    Returns:
        True if name is valid, False if it conflicts with reserved names

    """
    return slugify_state_name(name) not in RESERVED_STATE_NAMES


def validate_state_name_unique(
    name: str, existing_states: list[dict], exclude_index: int | None = None
) -> bool:
    """Check if state name is unique.

    Args:
        name: State name to validate
        existing_states: List of existing states
        exclude_index: Index to exclude from check (for editing)

    Returns:
        True if name is unique, False otherwise

    """
    slugified = slugify_state_name(name)
    for idx, state in enumerate(existing_states):
        if exclude_index is not None and idx == exclude_index:
            continue
        existing_slugified = slugify_state_name(state.get("name", ""))
        if existing_slugified == slugified:
            return False
    return True
