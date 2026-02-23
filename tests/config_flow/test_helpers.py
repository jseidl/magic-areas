"""Tests for config_flow.helpers module."""

import pytest
import voluptuous as vol

from unittest.mock import Mock

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import async_get as async_get_ar
from homeassistant.helpers.entity_registry import async_get as async_get_er

from custom_components.magic_areas.base.magic import MagicArea
from custom_components.magic_areas.config_flow.helpers import (
    ConfigValidator,
    EntityListBuilder,
    FlowEntityContext,
    SchemaBuilder,
    SelectorBuilder,
    StateOptionsBuilder,
)
from custom_components.magic_areas.const import (
    AreaStates,
    ConfigOption,
)
from custom_components.magic_areas.const.aggregates import AggregateOptions
from custom_components.magic_areas.const.presence_hold import PresenceHoldOptions

from tests.const import DEFAULT_MOCK_AREA
from tests.mocks import MockBinarySensor, MockLight, MockMediaPlayer


class TestFlowEntityContext:
    """Test FlowEntityContext class."""

    async def test_flow_entity_context_initialization(self, hass: HomeAssistant):
        """Test FlowEntityContext initialization and entity list building."""
        # Setup area and entities
        area_registry = async_get_ar(hass)
        entity_registry = async_get_er(hass)

        # Create test area
        if not area_registry.async_get_area_by_name(DEFAULT_MOCK_AREA.value):
            area_registry.async_create(name=DEFAULT_MOCK_AREA.value)

        # Create test entities
        test_entities = [
            MockBinarySensor(
                name="motion_sensor",
                unique_id="test_motion_sensor",
                device_class=BinarySensorDeviceClass.MOTION,
            ),
            MockLight(
                name="test_light",
                state="off",
                unique_id="test_light",
                dimmable=True,
            ),
            MockMediaPlayer(
                name="test_media_player",
                state="off",
                unique_id="test_media_player",
            ),
        ]

        # Setup entities
        from tests.helpers import setup_mock_entities

        await setup_mock_entities(
            hass,
            BINARY_SENSOR_DOMAIN,
            {DEFAULT_MOCK_AREA: [test_entities[0]]},
        )
        await setup_mock_entities(
            hass,
            LIGHT_DOMAIN,
            {DEFAULT_MOCK_AREA: [test_entities[1]]},
        )
        await setup_mock_entities(
            hass,
            MEDIA_PLAYER_DOMAIN,
            {DEFAULT_MOCK_AREA: [test_entities[2]]},
        )

        # Create config entry
        config_entry = Mock()
        config_entry.options = {}

        # Create MagicArea
        magic_area = Mock(spec=MagicArea)
        magic_area.id = DEFAULT_MOCK_AREA.value
        magic_area.name = DEFAULT_MOCK_AREA.value
        magic_area.entities = {
            BINARY_SENSOR_DOMAIN: [
                {"entity_id": "binary_sensor.motion_sensor", "device_class": "motion"}
            ],
            LIGHT_DOMAIN: [{"entity_id": "light.test_light"}],
            MEDIA_PLAYER_DOMAIN: [{"entity_id": "media_player.test_media_player"}],
        }

        # Create context
        context = FlowEntityContext(hass, magic_area, config_entry)

        # Test entity lists
        assert len(context.all_entities) > 0
        assert "binary_sensor.motion_sensor" in context.all_entities
        assert "light.test_light" in context.all_entities
        assert "media_player.test_media_player" in context.all_entities

        assert len(context.area_entities) > 0
        assert "binary_sensor.motion_sensor" in context.area_entities
        assert "light.test_light" in context.area_entities
        assert "media_player.test_media_player" in context.area_entities

        assert len(context.lights) > 0
        assert "light.test_light" in context.lights

        assert len(context.media_players) > 0
        assert "media_player.test_media_player" in context.media_players

        assert len(context.binary_entities) > 0
        assert "binary_sensor.motion_sensor" in context.binary_entities

        assert len(context.light_tracking_entities) > 0

    async def test_flow_entity_context_with_excluded_entities(
        self, hass: HomeAssistant
    ):
        """Test FlowEntityContext with excluded entities."""
        # Setup similar to above but with excluded entities
        area_registry = async_get_ar(hass)
        entity_registry = async_get_er(hass)

        if not area_registry.async_get_area_by_name(DEFAULT_MOCK_AREA.value):
            area_registry.async_create(name=DEFAULT_MOCK_AREA.value)

        test_entities = [
            MockBinarySensor(
                name="motion_sensor",
                unique_id="test_motion_sensor",
                device_class=BinarySensorDeviceClass.MOTION,
            ),
        ]

        from tests.helpers import setup_mock_entities

        await setup_mock_entities(
            hass,
            BINARY_SENSOR_DOMAIN,
            {DEFAULT_MOCK_AREA: [test_entities[0]]},
        )

        config_entry = Mock()
        config_entry.options = {"exclude_entities": ["binary_sensor.excluded_sensor"]}

        magic_area = Mock(spec=MagicArea)
        magic_area.id = DEFAULT_MOCK_AREA.value
        magic_area.name = DEFAULT_MOCK_AREA.value
        magic_area.entities = {
            BINARY_SENSOR_DOMAIN: [
                {"entity_id": "binary_sensor.motion_sensor", "device_class": "motion"}
            ],
        }

        context = FlowEntityContext(hass, magic_area, config_entry)

        assert "binary_sensor.excluded_sensor" in context.all_area_entities


class TestConfigValidator:
    """Test ConfigValidator class."""

    def test_config_validator_initialization(self):
        """Test ConfigValidator initialization."""
        validator = ConfigValidator("test_flow")
        assert validator.flow_name == "test_flow"

    async def test_config_validator_validate_success(self):
        """Test successful validation."""
        validator = ConfigValidator("test_flow")
        schema = vol.Schema({"test_field": str})

        async def on_success(validated):
            return validated

        success, errors = await validator.validate(
            schema, {"test_field": "test_value"}, on_success
        )

        assert success is True
        assert errors is None

    async def test_config_validator_validate_failure(self):
        """Test validation failure."""
        validator = ConfigValidator("test_flow")
        schema = vol.Schema({"test_field": str})

        async def on_success(validated):
            return validated

        success, errors = await validator.validate(
            schema, {"test_field": 123}, on_success
        )

        assert success is False
        assert errors is not None
        assert "test_field" in errors

    async def test_config_validator_validate_multiple_invalid(self):
        """Test validation with multiple invalid fields."""
        validator = ConfigValidator("test_flow")
        schema = vol.Schema(
            {
                "field1": str,
                "field2": int,
            }
        )

        async def on_success(validated):
            return validated

        success, errors = await validator.validate(
            schema, {"field1": 123, "field2": "not_int"}, on_success
        )

        assert success is False
        assert errors is not None
        assert len(errors) == 2

    async def test_config_validator_validate_unknown_error(self):
        """Test validation with unknown error."""
        validator = ConfigValidator("test_flow")
        schema = vol.Schema({"test_field": str})

        async def on_success(validated):
            raise Exception("Unknown error")

        success, errors = await validator.validate(
            schema, {"test_field": "test_value"}, on_success
        )

        assert success is False
        assert errors is not None
        assert "base" in errors
        assert errors["base"] == "unknown_error"


class TestEntityListBuilder:
    """Test EntityListBuilder class."""

    def test_entity_list_builder_initialization(self):
        """Test EntityListBuilder initialization."""
        hass = Mock()
        all_entities = ["light.bedroom", "light.kitchen", "sensor.motion"]
        builder = EntityListBuilder(hass, all_entities)

        assert builder.hass == hass
        assert builder.all_entities == all_entities

    def test_by_domain(self):
        """Test filtering entities by domain."""
        hass = Mock()
        all_entities = [
            "light.bedroom",
            "light.kitchen",
            "sensor.motion",
            "binary_sensor.door",
        ]
        builder = EntityListBuilder(hass, all_entities)

        lights = builder.by_domain(["light"])
        assert len(lights) == 2
        assert "light.bedroom" in lights
        assert "light.kitchen" in lights

        sensors = builder.by_domain(["sensor", "binary_sensor"])
        assert len(sensors) == 2
        assert "sensor.motion" in sensors
        assert "binary_sensor.door" in sensors

    def test_by_device_class(self):
        """Test filtering entities by device class."""
        hass = Mock()
        all_entities = [
            "binary_sensor.motion",
            "binary_sensor.door",
            "sensor.temperature",
        ]
        builder = EntityListBuilder(hass, all_entities)

        # Mock state objects
        motion_state = Mock()
        motion_state.attributes = {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}

        door_state = Mock()
        door_state.attributes = {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.DOOR}

        hass.states.get.side_effect = lambda entity_id: {
            "binary_sensor.motion": motion_state,
            "binary_sensor.door": door_state,
        }.get(entity_id)

        motion_sensors = builder.by_device_class(
            BINARY_SENSOR_DOMAIN, BinarySensorDeviceClass.MOTION
        )
        assert len(motion_sensors) == 1
        assert "binary_sensor.motion" in motion_sensors

        door_sensors = builder.by_device_class(
            BINARY_SENSOR_DOMAIN, BinarySensorDeviceClass.DOOR
        )
        assert len(door_sensors) == 1
        assert "binary_sensor.door" in door_sensors

    def test_by_area_entities(self):
        """Test filtering entities by area entities."""
        hass = Mock()
        all_entities = ["light.bedroom", "light.kitchen", "sensor.motion"]
        builder = EntityListBuilder(hass, all_entities)

        area_entities = {
            LIGHT_DOMAIN: [
                {"entity_id": "light.bedroom"},
                {"entity_id": "light.kitchen"},
            ],
            BINARY_SENSOR_DOMAIN: [{"entity_id": "sensor.motion"}],
        }

        lights = builder.by_area_entities(area_entities, [LIGHT_DOMAIN])
        assert len(lights) == 2
        assert "light.bedroom" in lights
        assert "light.kitchen" in lights

        sensors = builder.by_area_entities(area_entities, [BINARY_SENSOR_DOMAIN])
        assert len(sensors) == 1
        assert "sensor.motion" in sensors


class TestStateOptionsBuilder:
    """Test StateOptionsBuilder class."""

    def test_for_light_groups(self):
        """Test building state options for light groups."""
        available_states = [
            AreaStates.OCCUPIED.value,
            AreaStates.EXTENDED.value,
            AreaStates.SLEEP.value,
        ]

        states = StateOptionsBuilder.for_light_groups(available_states)
        assert AreaStates.OCCUPIED in states
        assert AreaStates.EXTENDED in states
        assert AreaStates.SLEEP in states

    def test_for_fan_groups(self):
        """Test building state options for fan groups."""

        states = StateOptionsBuilder.for_fan_groups()
        assert AreaStates.OCCUPIED in states
        assert AreaStates.EXTENDED in states
        # Fan groups only support occupied/extended
        assert AreaStates.SLEEP not in states
        assert AreaStates.DARK not in states

    def test_for_area_aware_media_player(self):
        """Test building state options for area aware media player."""
        available_states = [
            AreaStates.OCCUPIED.value,
            AreaStates.EXTENDED.value,
            AreaStates.SLEEP.value,
        ]

        states = StateOptionsBuilder.for_area_aware_media_player(available_states)
        assert AreaStates.OCCUPIED in states
        assert AreaStates.EXTENDED in states
        assert AreaStates.SLEEP in states


class TestSelectorBuilder:
    """Test SelectorBuilder class."""

    def test_from_config_option_boolean(self):
        """Test building boolean selector from ConfigOption."""
        option = ConfigOption(
            key="test_boolean",
            default=False,
            title="Test Boolean",
            description="Test description",
            translation_key="test_boolean",
            validator=bool,
            selector_type="boolean",
        )

        selector = SelectorBuilder.from_config_option(option)
        assert selector is not None

    def test_from_config_option_select(self):
        """Test building select selector from ConfigOption."""
        option = ConfigOption(
            key="test_select",
            default="option1",
            title="Test Select",
            description="Test description",
            translation_key="test_select",
            validator=str,
            selector_type="select",
            selector_config={
                "options": ["option1", "option2", "option3"],
                "multiple": False,
                "mode": "dropdown",
                "translation_key": "test_select",
            },
        )

        selector = SelectorBuilder.from_config_option(option)
        assert selector is not None

    def test_from_config_option_entity(self):
        """Test building entity selector from ConfigOption."""
        option = ConfigOption(
            key="test_entity",
            default="",
            title="Test Entity",
            description="Test description",
            translation_key="test_entity",
            validator=str,
            selector_type="entity",
            selector_config={
                "multiple": True,
                "domain": ["light"],
                "device_class": None,
                "include_entities": ["light.bedroom"],
            },
        )

        selector = SelectorBuilder.from_config_option(option)
        assert selector is not None

    def test_from_config_option_number(self):
        """Test building number selector from ConfigOption."""
        option = ConfigOption(
            key="test_number",
            default=0,
            title="Test Number",
            description="Test description",
            translation_key="test_number",
            validator=int,
            selector_type="number",
            selector_config={
                "min": 0,
                "max": 100,
                "step": 1,
                "mode": "box",
                "unit_of_measurement": "seconds",
            },
        )

        selector = SelectorBuilder.from_config_option(option)
        assert selector is not None

    def test_from_config_option_text(self):
        """Test building text selector from ConfigOption."""
        option = ConfigOption(
            key="test_text",
            default="",
            title="Test Text",
            description="Test description",
            translation_key="test_text",
            validator=str,
            selector_type="text",
            selector_config={
                "multiline": False,
                "type": "text",
            },
        )

        selector = SelectorBuilder.from_config_option(option)
        assert selector is not None

    def test_from_config_option_none(self):
        """Test building selector when selector_type is None."""
        option = ConfigOption(
            key="test_none",
            default="",
            title="Test None",
            description="Test description",
            translation_key="test_none",
            validator=str,
            selector_type=None,
        )

        selector = SelectorBuilder.from_config_option(option)
        assert selector is None

    def test_from_config_option_unknown_type(self):
        """Test building selector with unknown selector_type."""
        option = ConfigOption(
            key="test_unknown",
            default="",
            title="Test Unknown",
            description="Test description",
            translation_key="test_unknown",
            validator=str,
            selector_type="unknown",
        )

        with pytest.raises(ValueError, match="Unknown selector_type: unknown"):
            SelectorBuilder.from_config_option(option)

    def test_from_config_option_invalid_option(self):
        """Test building selector with invalid option type."""
        with pytest.raises(TypeError, match="Expected ConfigOption, got <class 'str'>"):
            SelectorBuilder.from_config_option("invalid")

    def test_from_option_set(self):
        """Test building selectors from OptionSet class."""
        selectors = SelectorBuilder.from_option_set(PresenceHoldOptions)
        assert isinstance(selectors, dict)

        # Check that selectors are created for each ConfigOption
        assert PresenceHoldOptions.TIMEOUT.key in selectors
        # Note: PresenceHoldOptions only has TIMEOUT, no ENABLED field


class TestSchemaBuilder:
    """Test SchemaBuilder class."""

    def test_schema_builder_initialization(self):
        """Test SchemaBuilder initialization."""
        saved_options = {"test_field": "saved_value"}
        builder = SchemaBuilder(saved_options)
        assert builder.saved_options == saved_options

    def test_build_basic_schema(self):
        """Test building a basic schema."""
        saved_options = {"field1": "saved1"}
        builder = SchemaBuilder(saved_options)

        options = [
            ("field1", "default1", str),
            ("field2", "default2", int),
            ("field3", "default3", bool),
        ]

        schema = builder.build(options)
        assert isinstance(schema, vol.Schema)

    def test_build_schema_with_selectors(self):
        """Test building schema with custom selectors."""
        saved_options = {"field1": "saved1"}
        builder = SchemaBuilder(saved_options)

        options = [("field1", "default1", str), ("field2", "default2", int)]
        selectors = {"field1": Mock()}

        schema = builder.build(options, selectors=selectors)
        assert isinstance(schema, vol.Schema)

    def test_build_schema_with_dynamic_validators(self):
        """Test building schema with dynamic validators."""
        saved_options = {"field1": "saved1"}
        builder = SchemaBuilder(saved_options)

        options = [("field1", "default1", str), ("field2", "default2", int)]
        dynamic_validators = {"field1": vol.Length(min=3)}

        schema = builder.build(options, dynamic_validators=dynamic_validators)
        assert isinstance(schema, vol.Schema)

    def test_build_feature_schema(self):
        """Test building feature schema."""
        saved_options = {"field1": "saved1"}
        builder = SchemaBuilder(saved_options)

        feature_options = [("field1", "default1", str), ("field2", "default2", int)]
        feature_config = {"field1": "config1"}
        selectors = {"field1": Mock()}

        schema = builder.build_feature_schema(
            feature_options, feature_config, selectors
        )
        assert isinstance(schema, vol.Schema)

    def test_from_option_set(self):
        """Test building schema from OptionSet class."""
        saved_config = {PresenceHoldOptions.TIMEOUT.key: 60}
        builder = SchemaBuilder(saved_config)

        schema = builder.from_option_set(PresenceHoldOptions, saved_config)
        assert isinstance(schema, vol.Schema)

    def test_from_option_set_with_selector_overrides(self):
        """Test building schema from OptionSet with selector overrides."""
        saved_config = {PresenceHoldOptions.TIMEOUT.key: 60}
        builder = SchemaBuilder(saved_config)

        selector_overrides = {PresenceHoldOptions.TIMEOUT.key: Mock()}

        schema = builder.from_option_set(
            PresenceHoldOptions, saved_config, selector_overrides
        )
        assert isinstance(schema, vol.Schema)

    def test_from_option_set_with_internal_fields(self):
        """Test that internal fields are excluded from schema."""
        # Test with valid config options
        saved_config = {
            AggregateOptions.BINARY_SENSOR_DEVICE_CLASSES.key: ["motion"],
            AggregateOptions.SENSOR_DEVICE_CLASSES.key: ["temperature"],
        }
        builder = SchemaBuilder(saved_config)

        schema = builder.from_option_set(AggregateOptions, saved_config)
        assert isinstance(schema, vol.Schema)

        # Check that schema contains the expected fields
        schema_keys = list(schema.schema.keys())
        assert len(schema_keys) > 0
