"""Tests for config_flow.features registry."""

from unittest.mock import Mock

import pytest

from custom_components.magic_areas.config_flow.features import (
    get_available_features,
    get_feature_handler,
)
from custom_components.magic_areas.config_flow.flow import OptionsFlowHandler
from custom_components.magic_areas.const import (
    AreaConfigOptions,
    AreaType,
    ConfigDomains,
    ConfigHelper,
    Features,
)


def create_mock_flow(area_type: AreaType) -> Mock:
    """Create a mock flow with proper ConfigHelper."""
    flow = Mock(spec=OptionsFlowHandler)

    # Create area config with proper structure
    area_config_data = {
        ConfigDomains.AREA: {
            AreaConfigOptions.TYPE.key: area_type,
        }
    }

    # Create mock area with real ConfigHelper
    flow.area = Mock()
    flow.area.id = "test_area"
    flow.area.config = ConfigHelper(area_config_data)

    return flow


class TestFeaturesRegistry:
    """Test features registry functionality."""

    def test_get_feature_handler_valid(self):
        """Test getting a valid feature handler."""
        flow = create_mock_flow(AreaType.INTERIOR)

        # Test getting a valid feature handler
        handler = get_feature_handler(Features.AGGREGATION, flow)
        assert handler is not None
        assert handler.feature_id == Features.AGGREGATION
        assert handler.feature_name == "Aggregates"
        assert hasattr(handler, "is_available")
        assert hasattr(handler, "requires_configuration")

    def test_get_feature_handler_another_feature(self):
        """Test getting another valid feature handler."""
        flow = create_mock_flow(AreaType.INTERIOR)

        # Test presence hold feature
        handler = get_feature_handler(Features.PRESENCE_HOLD, flow)
        assert handler is not None
        assert handler.feature_id == Features.PRESENCE_HOLD
        assert handler.feature_name == "Presence Hold"

    def test_get_feature_handler_invalid(self):
        """Test getting an invalid feature handler raises ValueError."""
        flow = create_mock_flow(AreaType.INTERIOR)

        # Test getting an invalid feature handler
        with pytest.raises(ValueError, match="Unknown feature: invalid_feature"):
            get_feature_handler("invalid_feature", flow)

    def test_get_available_features_interior(self):
        """Test getting available features for interior area."""
        flow = create_mock_flow(AreaType.INTERIOR)

        # Test getting available features
        available_features = get_available_features(flow)
        assert isinstance(available_features, dict)
        assert len(available_features) > 0

        # Check that all handlers have required attributes and properties
        for feature_id, handler in available_features.items():
            assert hasattr(handler, "feature_id")
            assert hasattr(handler, "feature_name")
            assert hasattr(handler, "requires_configuration")
            assert handler.feature_id == feature_id

            # is_available is a property, verify it works
            assert isinstance(handler.is_available, bool)

        # Interior areas should have light groups and fan groups
        assert Features.LIGHT_GROUPS in available_features
        assert Features.FAN_GROUPS in available_features
        assert Features.AGGREGATION in available_features
        assert Features.PRESENCE_HOLD in available_features

    def test_get_available_features_exterior(self):
        """Test getting available features for exterior area."""
        flow = create_mock_flow(AreaType.EXTERIOR)

        # Test getting available features
        available_features = get_available_features(flow)
        assert isinstance(available_features, dict)
        assert len(available_features) > 0

        # Exterior areas should also have light groups and fan groups
        assert Features.LIGHT_GROUPS in available_features
        assert Features.FAN_GROUPS in available_features

    def test_get_available_features_meta_area(self):
        """Test getting available features for meta area filters unavailable features."""
        flow = create_mock_flow(AreaType.META)

        # Test getting available features for meta area
        available_features = get_available_features(flow)
        assert isinstance(available_features, dict)

        # Meta areas should NOT have features that require regular areas
        # Light groups and fan groups are not available for meta areas
        assert Features.LIGHT_GROUPS not in available_features
        assert Features.FAN_GROUPS not in available_features

        # But meta areas should have features that work with meta areas
        assert Features.AGGREGATION in available_features

    def test_feature_availability_check(self):
        """Test that is_available property works correctly."""
        # Create flows for different area types
        interior_flow = create_mock_flow(AreaType.INTERIOR)
        meta_flow = create_mock_flow(AreaType.META)

        # Get light groups handler for both
        light_groups_interior = get_feature_handler(
            Features.LIGHT_GROUPS, interior_flow
        )
        light_groups_meta = get_feature_handler(Features.LIGHT_GROUPS, meta_flow)

        # Light groups should be available for interior but not meta
        assert light_groups_interior.is_available is True
        assert light_groups_meta.is_available is False

    def test_registered_features_work_correctly(self):
        """Test that registered features work correctly.

        Note: Not all Features enum values need handlers - some features like
        cover_groups and media_player_groups are enable/disable only without
        configuration, so they don't need config flow handlers.
        """
        flow = create_mock_flow(AreaType.INTERIOR)

        # Get all features that DO have handlers
        available_features = get_available_features(flow)

        # Verify each registered handler is valid
        for feature_id in available_features:
            handler = get_feature_handler(feature_id, flow)
            assert handler is not None
            assert handler.feature_id == feature_id
            assert hasattr(handler, "feature_name")
            assert hasattr(handler, "handle_step")

        # Ensure we have at least the core features with handlers
        core_features_with_handlers = [
            Features.LIGHT_GROUPS,
            Features.FAN_GROUPS,
            Features.AGGREGATION,
            Features.PRESENCE_HOLD,
            Features.CLIMATE_CONTROL,
            Features.HEALTH,
        ]

        for feature in core_features_with_handlers:
            assert feature in available_features, f"{feature} should be registered"

    def test_available_features_returns_instances(self):
        """Test that get_available_features returns handler instances, not classes."""
        flow = create_mock_flow(AreaType.INTERIOR)

        available_features = get_available_features(flow)

        # All values should be instances, not classes
        for handler in available_features.values():
            assert not isinstance(handler, type)
            assert hasattr(handler, "handle_step")
            assert callable(handler.handle_step)
