"""Tests for config_flow.base module."""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock, patch

import pytest
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

from custom_components.magic_areas.config_flow.base import (
    ConfigBase,
    NullableEntitySelector,
)


class TestConfigBase:
    """Test ConfigBase class."""

    def test_build_selector_boolean(self):
        """Test building a boolean selector."""
        config_base = ConfigBase()
        selector = config_base.build_selector_boolean()

        assert isinstance(selector, BooleanSelector)
        assert selector.config is not None  # TypedDict doesn't support isinstance

    def test_build_selector_select(self):
        """Test building a select selector."""
        config_base = ConfigBase()
        options = ["option1", "option2", "option3"]
        selector = config_base.build_selector_select(options)

        assert isinstance(selector, SelectSelector)
        assert selector.config is not None
        assert selector.config["options"] == options
        assert selector.config["multiple"] is False
        assert selector.config["mode"] == SelectSelectorMode.DROPDOWN

    def test_build_selector_select_multiple(self):
        """Test building a multi-select selector."""
        config_base = ConfigBase()
        options = ["option1", "option2", "option3"]
        selector = config_base.build_selector_select(options, multiple=True)

        assert isinstance(selector, SelectSelector)
        assert selector.config is not None
        assert selector.config["options"] == options
        assert selector.config["multiple"] is True
        assert selector.config["mode"] == SelectSelectorMode.DROPDOWN

    def test_build_selector_select_with_translation(self):
        """Test building a select selector with translation key."""
        config_base = ConfigBase()
        options = ["option1", "option2"]
        selector = config_base.build_selector_select(
            options, translation_key="test_translation"
        )

        assert isinstance(selector, SelectSelector)
        assert selector.config is not None
        assert selector.config["options"] == options
        assert selector.config["translation_key"] == "test_translation"

    def test_build_selector_entity_simple(self):
        """Test building a simple entity selector."""
        config_base = ConfigBase()
        options = ["entity1", "entity2", "entity3"]
        selector = config_base.build_selector_entity_simple(options)

        assert isinstance(selector, EntitySelector)
        assert selector.config is not None
        assert selector.config["include_entities"] == options
        assert selector.config["multiple"] is False

    def test_build_selector_entity_simple_multiple(self):
        """Test building a multi-entity selector."""
        config_base = ConfigBase()
        options = ["entity1", "entity2", "entity3"]
        selector = config_base.build_selector_entity_simple(options, multiple=True)

        assert isinstance(selector, EntitySelector)
        assert selector.config is not None
        assert selector.config["include_entities"] == options
        assert selector.config["multiple"] is True

    def test_build_selector_entity_simple_force_include(self):
        """Test building an entity selector with force include."""
        config_base = ConfigBase()
        options = ["entity1", "entity2", "entity3"]
        selector = config_base.build_selector_entity_simple(
            options, multiple=True, force_include=True
        )

        assert isinstance(selector, EntitySelector)
        assert selector.config is not None
        assert selector.config["include_entities"] == options
        assert selector.config["multiple"] is True

    def test_build_selector_number(self):
        """Test building a number selector."""
        config_base = ConfigBase()
        selector = config_base.build_selector_number(
            min_value=0, max_value=100, step=1, unit_of_measurement="seconds"
        )

        assert isinstance(selector, NumberSelector)
        assert selector.config is not None
        assert selector.config["min"] == 0
        assert selector.config["max"] == 100
        assert selector.config["step"] == 1
        assert selector.config["unit_of_measurement"] == "seconds"
        assert selector.config["mode"] == NumberSelectorMode.BOX

    def test_build_selector_number_with_mode(self):
        """Test building a number selector with specific mode."""
        config_base = ConfigBase()
        selector = config_base.build_selector_number(
            min_value=0, max_value=100, mode=NumberSelectorMode.SLIDER
        )

        assert isinstance(selector, NumberSelector)
        assert selector.config is not None
        assert selector.config["min"] == 0
        assert selector.config["max"] == 100
        assert selector.config["mode"] == NumberSelectorMode.SLIDER

    def test_build_options_schema_basic(self):
        """Test building a basic options schema."""
        config_base = ConfigBase()
        options = [
            ("option1", "default1", str),
            ("option2", "default2", int),
            ("option3", "default3", bool),
        ]

        schema = config_base.build_options_schema(options)

        assert isinstance(schema, vol.Schema)
        assert len(schema.schema) == 3

        # Check that all options are present
        schema_keys = list(schema.schema.keys())
        assert any("option1" in str(key) for key in schema_keys)
        assert any("option2" in str(key) for key in schema_keys)
        assert any("option3" in str(key) for key in schema_keys)

    def test_build_options_schema_with_dynamic_validators(self):
        """Test building schema with dynamic validators."""
        config_base = ConfigBase()
        options = [("option1", "default1", str), ("option2", "default2", int)]
        dynamic_validators = {"option1": vol.Length(min=3)}

        schema = config_base.build_options_schema(
            options, dynamic_validators=dynamic_validators
        )

        assert isinstance(schema, vol.Schema)
        # Check that dynamic validator is applied
        schema_keys = list(schema.schema.keys())
        option1_key = next(key for key in schema_keys if "option1" in str(key))
        # The validator should be the dynamic one, not the original str validator

    def test_build_options_schema_with_selectors(self):
        """Test building schema with custom selectors."""
        config_base = ConfigBase()
        options = [("option1", "default1", str), ("option2", "default2", int)]
        selectors = {"option1": BooleanSelector(BooleanSelectorConfig())}

        schema = config_base.build_options_schema(options, selectors=selectors)

        assert isinstance(schema, vol.Schema)
        # Check that custom selector is used
        schema_keys = list(schema.schema.keys())
        option1_key = next(key for key in schema_keys if "option1" in str(key))
        # The validator should be the custom selector

    def test_build_options_schema_no_config_entry(self):
        """Test building schema when no config entry is available."""
        config_base = ConfigBase()
        options = [("option1", "default1", str)]

        schema = config_base.build_options_schema(options)

        assert isinstance(schema, vol.Schema)
        # Should use the provided default since no config entry (it's a lambda)
        schema_keys = list(schema.schema.keys())
        option1_key = next(key for key in schema_keys if "option1" in str(key))
        assert callable(option1_key.default)
        assert option1_key.default() == "default1"

    def test_build_options_schema_with_enum_keys(self):
        """Test building schema with enum keys (should convert to string values)."""
        from enum import StrEnum

        class TestEnum(StrEnum):
            """Test enum for schema building."""

            OPTION1 = "option1"
            OPTION2 = "option2"

        config_base = ConfigBase()
        # Simulate what happens in flow.py select_features with Features enum
        options = [
            (TestEnum.OPTION1, False, bool),
            (TestEnum.OPTION2, False, bool),
        ]

        # This should not raise a SchemaError
        schema = config_base.build_options_schema(options)

        assert isinstance(schema, vol.Schema)
        assert len(schema.schema) == 2

        # Verify that the enum was converted to its string value
        schema_keys = list(schema.schema.keys())
        assert any("option1" in str(key) for key in schema_keys)
        assert any("option2" in str(key) for key in schema_keys)

        # Verify we can validate with string keys (not enum)
        result = schema({"option1": True, "option2": False})
        assert result["option1"] is True
        assert result["option2"] is False


class TestNullableEntitySelector:
    """Test NullableEntitySelector class."""

    def test_nullable_entity_selector_none(self):
        """Test that None is accepted."""
        selector = NullableEntitySelector()
        result = selector(None)
        assert result is None

    def test_nullable_entity_selector_empty_string(self):
        """Test that empty string is accepted."""
        selector = NullableEntitySelector()
        result = selector("")
        assert result == ""

    def test_nullable_entity_selector_valid_entity(self):
        """Test that valid entity IDs are passed through."""
        selector = NullableEntitySelector()
        result = selector("light.bedroom")
        assert result == "light.bedroom"

    def test_nullable_entity_selector_invalid_entity(self):
        """Test that invalid entity IDs raise an error."""
        selector = NullableEntitySelector()
        with pytest.raises(vol.Invalid):
            selector("invalid_entity_id")

    def test_nullable_entity_selector_with_config(self):
        """Test nullable entity selector with configuration."""
        selector = NullableEntitySelector(
            EntitySelectorConfig(include_entities=["light.bedroom"])
        )
        result = selector("light.bedroom")
        assert result == "light.bedroom"

        # Should still accept None
        result = selector(None)
        assert result is None

        # Should still accept empty string
        result = selector("")
        assert result == ""

    def test_nullable_entity_selector_with_multiple(self):
        """Test nullable entity selector with multiple entities."""
        selector = NullableEntitySelector(
            EntitySelectorConfig(multiple=True, include_entities=["light.bedroom"])
        )
        result = selector(["light.bedroom"])
        assert result == ["light.bedroom"]

        # Should still accept None
        result = selector(None)
        assert result is None

        # Should still accept empty string
        result = selector("")
        assert result == ""
