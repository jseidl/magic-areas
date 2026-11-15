"""Repairs for Magic Areas."""

from typing import cast

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant

from custom_components.magic_areas.const import MagicAreasIssue
from custom_components.magic_areas.helpers.issues import ISSUE_DATA_ENTRY_ID


class AreaNotFoundRepairFlow(RepairsFlow):
    """Fix flow which removes a config entry whose area no longer exists."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the flow."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of the fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Ask for confirmation, then remove the config entry."""
        if user_input is not None:
            # The entry may already be gone: removing is then a no-op.
            if self.hass.config_entries.async_get_entry(self._entry_id) is not None:
                await self.hass.config_entries.async_remove(self._entry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm")


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the fix flow for a fixable Magic Areas issue."""
    if issue_id.startswith(MagicAreasIssue.AREA_NOT_FOUND.value) and data:
        return AreaNotFoundRepairFlow(cast(str, data[ISSUE_DATA_ENTRY_ID]))

    return ConfirmRepairFlow()
