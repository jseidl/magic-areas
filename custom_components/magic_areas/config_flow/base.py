"""Base classes for config flow."""

import logging
from typing import Any, Optional

import voluptuous as vol
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from ..const import EMPTY_STRING

_LOGGER = logging.getLogger(__name__)


class NullableEntitySelector(EntitySelector):
    """Entity selector that supports null values."""

    def __call__(self, data):
        """Validate the passed selection, if passed."""
        if data in (None, ""):
            return data
        return super().__call__(data)  # type: ignore


class ConfigBase:
    """Base class for config flow with selector builders."""

    config_entry = None

    # Selector builders
    def _build_selector_boolean(self):
        """Build a boolean toggle selector."""
        return BooleanSelector(BooleanSelectorConfig())

    def _build_selector_select(
        self, options=None, multiple=False, translation_key=EMPTY_STRING
    ):
        """Build a <select> selector."""
        if not options:
            options = []

        return SelectSelector(
            SelectSelectorConfig(
                options=options,
                multiple=multiple,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=translation_key,
            )
        )

    def _build_selector_entity_simple(
        self, options=None, multiple=False, force_include=False
    ):
        """Build a <select> selector with predefined settings."""
        if not options:
            options = []
        return NullableEntitySelector(
            EntitySelectorConfig(include_entities=options, multiple=multiple)
        )

    def _build_selector_number(
        self,
        *,
        min_value: float = 0,
        max_value: float = 9999,
        mode: NumberSelectorMode = NumberSelectorMode.BOX,
        step: float = 1,
        unit_of_measurement: str = "seconds",
    ):
        """Build a number selector."""
        return NumberSelector(
            NumberSelectorConfig(
                min=min_value,
                max=max_value,
                mode=mode,
                step=step,
                unit_of_measurement=unit_of_measurement,
            )
        )

    def _build_options_schema(
        self,
        options,
        *,
        saved_options: dict | None = None,
        dynamic_validators=None,
        selectors=None,
    ) -> vol.Schema:
        """Build schema for configuration options."""
        _LOGGER.debug(
            "ConfigFlow: Building schema from options: %s - dynamic_validators: %s",
            str(options),
            str(dynamic_validators),
        )

        if not dynamic_validators:
            dynamic_validators = {}

        if not selectors:
            selectors = {}

        if saved_options is None and self.config_entry:
            saved_options = self.config_entry.options

        _LOGGER.debug(
            "ConfigFlow: Data for pre-populating fields: %s", str(saved_options)
        )

        schema = {
            vol.Optional(
                name,
                description={
                    "suggested_value": (
                        saved_options.get(name)
                        if saved_options and saved_options.get(name) is not None
                        else default
                    )
                },
                default=default,
            ): (
                selectors[name]
                if name in selectors
                else dynamic_validators.get(name, validation)
            )
            for name, default, validation in options
        }

        _LOGGER.debug("ConfigFlow: Built schema: %s", str(schema))

        return vol.Schema(schema)
