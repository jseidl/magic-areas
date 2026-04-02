"""Tests for async_migrate_entry and its helpers."""

import logging

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.magic_areas import (
    _migrate_light_groups,
    _migrate_v2_1_to_v2_2,
    async_migrate_entry,
)
from custom_components.magic_areas.const import (
    CONF_AREA_ID,
    DOMAIN,
    AreaConfigOptions,
    ConfigDomains,
    MagicConfigEntryVersion,
    PresenceTrackingOptions,
)
from custom_components.magic_areas.const.light_groups import (
    LightGroupEntryOptions,
    LightGroupOptions,
    LightGroupTurnOffWhen,
    LightGroupTurnOnWhen,
)
from custom_components.magic_areas.const.secondary_states import SecondaryStateOptions
from custom_components.magic_areas.const.user_defined_states import (
    UserDefinedStateEntryOptions,
    UserDefinedStateOptions,
)

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

AREA_ID = "guest_bedroom"


def _make_old_entry(data: dict, options: dict) -> MockConfigEntry:
    """Return a MockConfigEntry mimicking a v2.1 (flat) entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Guest Bedroom",
        unique_id=AREA_ID,
        data=data,
        options=options,
        version=2,
        minor_version=1,
    )


# Real-world old flat options dict (condensed from CONFIG_MIGRATION.md examples)
OLD_OPTIONS_REGULAR: dict = {
    "clear_timeout": 1,
    "exclude_entities": [
        "sensor.guest_bedroom_motion_sensor_device_temperature",
        "binary_sensor.apollo_msr_1_gamma_a55538_radar_target",
    ],
    "features": {
        "aggregates": {
            "aggregates_binary_sensor_device_classes": ["light", "motion", "occupancy"],
            "aggregates_illuminance_threshold": 0,
            "aggregates_illuminance_threshold_hysteresis": 0,
            "aggregates_min_entities": 1,
            "aggregates_sensor_device_classes": ["temperature", "humidity"],
        },
        "area_aware_media_player": {
            "notification_devices": [],
            "notification_states": ["extended"],
        },
        "ble_trackers": {
            "ble_tracker_entities": [
                "sensor.f20e3d1363ac4ba18554e8554e167ea1_100_40004_area"
            ]
        },
        "health": {"health_binary_sensor_device_classes": ["problem", "smoke"]},
        "light_groups": {
            "accent_lights": [],
            "accent_lights_act_on": ["occupancy", "state"],
            "accent_lights_states": [],
            "overhead_lights": [],
            "overhead_lights_act_on": ["occupancy", "state"],
            "overhead_lights_states": ["occupied"],
            "sleep_lights": ["light.third_reality_night_light_guest_bedroom"],
            "sleep_lights_act_on": ["occupancy"],
            "sleep_lights_states": ["sleep"],
            "task_lights": ["light.guest_bedroom_workstation_lamp"],
            "task_lights_act_on": ["occupancy", "state"],
            "task_lights_states": ["occupied", "extended"],
        },
        "presence_hold": {"presence_hold_timeout": 0},
        "wasp_in_a_box": {
            "delay": 90,
            "wasp_device_classes": ["motion"],
            "wasp_timeout": 0,
        },
    },
    "ignore_diagnostic_entities": True,
    "include_entities": [],
    "keep_only_entities": [
        "binary_sensor.apollo_msr_1_gamma_a55538_radar_zone_1_occupancy"
    ],
    "presence_device_platforms": ["binary_sensor"],
    "presence_sensor_device_class": ["motion", "occupancy", "presence", "moving"],
    "reload_on_registry_change": True,
    "secondary_states": {
        "accent_entity": "switch.accent_mode",
        "dark_entity": "binary_sensor.magic_areas_threshold_backyard_threshold_light",
        "extended_time": 5,
        "extended_timeout": 15,
        "sleep_entity": "switch.adaptive_lighting_sleep_mode_guest_bedroom",
        "sleep_timeout": 30,
    },
    "type": "interior",
}

OLD_OPTIONS_META: dict = {
    "clear_timeout": 0,
    "exclude_entities": [],
    "features": {
        "aggregates": {
            "aggregates_binary_sensor_device_classes": ["motion", "occupancy"],
            "aggregates_illuminance_threshold": 0,
            "aggregates_illuminance_threshold_hysteresis": 0,
            "aggregates_min_entities": 1,
            "aggregates_sensor_device_classes": ["temperature"],
        },
        "light_groups": {},
        "climate_control": {
            "entity_id": "climate.upstairs",
            "preset_clear": "Away",
            "preset_extended": "Home",
            "preset_occupied": "",
            "preset_sleep": "Sleep",
        },
    },
    "reload_on_registry_change": True,
    "secondary_states": {
        "calculation_mode": "any",
        "extended_time": 10,
        "extended_timeout": 5,
        "sleep_timeout": 0,
    },
    "type": "meta",
}


# ---------------------------------------------------------------------------
# TestMigrateLightGroups
# ---------------------------------------------------------------------------


class TestMigrateLightGroups:
    """Unit tests for _migrate_light_groups helper."""

    def test_empty_config_returns_empty_groups(self):
        """Empty config produces a groups list with no entries."""
        result = _migrate_light_groups({})
        assert result == {LightGroupOptions.GROUPS.key: []}

    def test_skips_categories_with_no_lights(self):
        """Categories with empty lights list are not included in groups."""
        config = {
            "overhead_lights": [],
            "overhead_lights_act_on": ["occupancy"],
            "overhead_lights_states": ["occupied"],
            "task_lights": [],
            "task_lights_act_on": ["occupancy"],
            "task_lights_states": [],
        }
        result = _migrate_light_groups(config)
        assert result[LightGroupOptions.GROUPS.key] == []

    def test_occupancy_act_on_produces_correct_triggers(self):
        """act_on=['occupancy'] maps to area_occupied/area_clear triggers."""
        config = {
            "overhead_lights": ["light.overhead"],
            "overhead_lights_act_on": ["occupancy"],
            "overhead_lights_states": ["occupied"],
        }
        groups = _migrate_light_groups(config)[LightGroupOptions.GROUPS.key]
        assert len(groups) == 1
        g = groups[0]
        assert (
            LightGroupTurnOnWhen.AREA_OCCUPIED.value
            in g[LightGroupEntryOptions.TURN_ON_WHEN.key]
        )
        assert (
            LightGroupTurnOffWhen.AREA_CLEAR.value
            in g[LightGroupEntryOptions.TURN_OFF_WHEN.key]
        )
        assert (
            LightGroupTurnOnWhen.STATE_GAIN.value
            not in g[LightGroupEntryOptions.TURN_ON_WHEN.key]
        )

    def test_state_act_on_produces_correct_triggers(self):
        """act_on=['state'] maps to state_gain+area_dark/state_loss triggers."""
        config = {
            "task_lights": ["light.task"],
            "task_lights_act_on": ["state"],
            "task_lights_states": ["extended"],
        }
        groups = _migrate_light_groups(config)[LightGroupOptions.GROUPS.key]
        assert len(groups) == 1
        g = groups[0]
        assert (
            LightGroupTurnOnWhen.STATE_GAIN.value
            in g[LightGroupEntryOptions.TURN_ON_WHEN.key]
        )
        assert (
            LightGroupTurnOnWhen.AREA_DARK.value
            in g[LightGroupEntryOptions.TURN_ON_WHEN.key]
        )
        assert (
            LightGroupTurnOffWhen.STATE_LOSS.value
            in g[LightGroupEntryOptions.TURN_OFF_WHEN.key]
        )
        assert (
            LightGroupTurnOnWhen.AREA_OCCUPIED.value
            not in g[LightGroupEntryOptions.TURN_ON_WHEN.key]
        )

    def test_both_act_on_combines_triggers(self):
        """act_on=['occupancy','state'] produces all four triggers."""
        config = {
            "overhead_lights": ["light.main"],
            "overhead_lights_act_on": ["occupancy", "state"],
            "overhead_lights_states": ["occupied", "extended"],
        }
        groups = _migrate_light_groups(config)[LightGroupOptions.GROUPS.key]
        g = groups[0]
        turn_on = g[LightGroupEntryOptions.TURN_ON_WHEN.key]
        turn_off = g[LightGroupEntryOptions.TURN_OFF_WHEN.key]
        assert LightGroupTurnOnWhen.AREA_OCCUPIED.value in turn_on
        assert LightGroupTurnOnWhen.STATE_GAIN.value in turn_on
        assert LightGroupTurnOnWhen.AREA_DARK.value in turn_on
        assert LightGroupTurnOffWhen.AREA_CLEAR.value in turn_off
        assert LightGroupTurnOffWhen.STATE_LOSS.value in turn_off

    def test_require_dark_always_true(self):
        """All migrated groups have require_dark=True."""
        config = {
            "sleep_lights": ["light.night_light"],
            "sleep_lights_act_on": ["occupancy"],
            "sleep_lights_states": ["sleep"],
        }
        groups = _migrate_light_groups(config)[LightGroupOptions.GROUPS.key]
        assert groups[0][LightGroupEntryOptions.REQUIRE_DARK.key] is True

    def test_states_copied_verbatim(self):
        """States list is copied as-is into the group entry."""
        config = {
            "task_lights": ["light.task"],
            "task_lights_act_on": ["state"],
            "task_lights_states": ["occupied", "extended"],
        }
        groups = _migrate_light_groups(config)[LightGroupOptions.GROUPS.key]
        assert groups[0][LightGroupEntryOptions.STATES.key] == ["occupied", "extended"]

    def test_name_derived_from_category(self):
        """Group names are the human-readable category titles."""
        config = {
            "overhead_lights": ["light.main"],
            "overhead_lights_act_on": ["occupancy"],
            "overhead_lights_states": [],
            "task_lights": ["light.task"],
            "task_lights_act_on": ["occupancy"],
            "task_lights_states": [],
            "sleep_lights": ["light.sleep"],
            "sleep_lights_act_on": ["occupancy"],
            "sleep_lights_states": [],
        }
        groups = _migrate_light_groups(config)[LightGroupOptions.GROUPS.key]
        names = [g[LightGroupEntryOptions.NAME.key] for g in groups]
        assert "Overhead Lights" in names
        assert "Task Lights" in names
        assert "Sleep Lights" in names

    def test_real_world_guest_bedroom(self):
        """Guest Bedroom: sleep + task lights set, overhead + accent empty → 2 groups."""
        lg = OLD_OPTIONS_REGULAR["features"]["light_groups"]
        groups = _migrate_light_groups(lg)[LightGroupOptions.GROUPS.key]
        # Overhead and accent are empty, so only sleep + task
        assert len(groups) == 2
        names = [g[LightGroupEntryOptions.NAME.key] for g in groups]
        assert "Sleep Lights" in names
        assert "Task Lights" in names


# ---------------------------------------------------------------------------
# TestMigrateV2_1ToV2_2
# ---------------------------------------------------------------------------


class TestMigrateV2_1ToV2_2:  # pylint: disable=invalid-name
    """Unit tests for _migrate_v2_1_to_v2_2 helper."""

    def _entry(self, options: dict, data: dict | None = None) -> MockConfigEntry:
        if data is None:
            data = {CONF_AREA_ID: AREA_ID, "type": "interior"}
        return _make_old_entry(data, options)

    def test_area_domain_fields_present(self):
        """Area domain contains all expected keys."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        area = result[ConfigDomains.AREA]
        assert AreaConfigOptions.TYPE.key in area
        assert AreaConfigOptions.INCLUDE_ENTITIES.key in area
        assert AreaConfigOptions.EXCLUDE_ENTITIES.key in area
        assert AreaConfigOptions.RELOAD_ON_REGISTRY_CHANGE.key in area
        assert AreaConfigOptions.IGNORE_DIAGNOSTIC_ENTITIES.key in area
        assert AreaConfigOptions.WINDOWLESS.key in area

    def test_windowless_defaults_false(self):
        """Windowless field is always False after migration (no old equivalent)."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        assert result[ConfigDomains.AREA][AreaConfigOptions.WINDOWLESS.key] is False

    def test_area_type_copied(self):
        """Type value is preserved from old config."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        assert result[ConfigDomains.AREA][AreaConfigOptions.TYPE.key] == "interior"

    def test_presence_tracking_domain_present(self):
        """presence_tracking domain contains all expected keys."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        pt = result[ConfigDomains.PRESENCE]
        assert PresenceTrackingOptions.CLEAR_TIMEOUT.key in pt
        assert PresenceTrackingOptions.KEEP_ONLY_ENTITIES.key in pt
        assert PresenceTrackingOptions.DEVICE_PLATFORMS.key in pt
        assert PresenceTrackingOptions.SENSOR_DEVICE_CLASS.key in pt

    def test_clear_timeout_copied(self):
        """clear_timeout value is preserved."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        assert (
            result[ConfigDomains.PRESENCE][PresenceTrackingOptions.CLEAR_TIMEOUT.key]
            == 1
        )

    def test_secondary_states_dark_entity_dropped(self):
        """dark_entity is NOT present in new secondary_states (auto-discovered now)."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        ss = result[ConfigDomains.SECONDARY_STATES]
        assert "dark_entity" not in ss

    def test_secondary_states_accent_entity_dropped(self):
        """accent_entity is NOT present in new secondary_states."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        ss = result[ConfigDomains.SECONDARY_STATES]
        assert "accent_entity" not in ss

    def test_secondary_states_sleep_values_preserved(self):
        """sleep_entity and sleep_timeout are copied across."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        ss = result[ConfigDomains.SECONDARY_STATES]
        assert (
            ss[SecondaryStateOptions.SLEEP_ENTITY.key]
            == "switch.adaptive_lighting_sleep_mode_guest_bedroom"
        )
        assert ss[SecondaryStateOptions.SLEEP_TIMEOUT.key] == 30

    def test_secondary_states_extended_values_preserved(self):
        """extended_time and extended_timeout are copied across."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        ss = result[ConfigDomains.SECONDARY_STATES]
        assert ss[SecondaryStateOptions.EXTENDED_TIME.key] == 5
        assert ss[SecondaryStateOptions.EXTENDED_TIMEOUT.key] == 15

    def test_accent_entity_creates_user_defined_state(self):
        """Non-empty accent_entity becomes a user-defined state named 'Accent'."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        uds = result[ConfigDomains.USER_DEFINED_STATES]
        states = uds[UserDefinedStateOptions.STATES.key]
        assert len(states) == 1
        assert states[0][UserDefinedStateEntryOptions.NAME.key] == "Accented"
        assert (
            states[0][UserDefinedStateEntryOptions.ENTITY.key] == "switch.accent_mode"
        )

    def test_empty_accent_entity_no_user_defined_states(self):
        """Empty accent_entity produces empty user-defined states list."""
        opts = {**OLD_OPTIONS_REGULAR}
        opts["secondary_states"] = {**opts["secondary_states"], "accent_entity": ""}
        result = _migrate_v2_1_to_v2_2(self._entry(opts))
        states = result[ConfigDomains.USER_DEFINED_STATES][
            UserDefinedStateOptions.STATES.key
        ]
        assert states == []

    def test_features_aggregates_copied_verbatim(self):
        """Aggregates feature config is copied without modification."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        agg = result[ConfigDomains.FEATURES]["aggregates"]
        assert agg["aggregates_min_entities"] == 1
        assert "temperature" in agg["aggregates_sensor_device_classes"]

    def test_features_wasp_in_a_box_copied_verbatim(self):
        """Wasp-in-a-box feature config is copied without modification."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        wiab = result[ConfigDomains.FEATURES]["wasp_in_a_box"]
        assert wiab["delay"] == 90
        assert wiab["wasp_timeout"] == 0

    def test_light_groups_migrated_to_groups_list(self):
        """light_groups feature is converted to new groups list format."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        lg = result[ConfigDomains.FEATURES]["light_groups"]
        assert LightGroupOptions.GROUPS.key in lg
        assert isinstance(lg[LightGroupOptions.GROUPS.key], list)

    def test_meta_area_calculation_mode_preserved(self):
        """Meta area secondary_states retains calculation_mode."""
        entry = _make_old_entry(
            data={CONF_AREA_ID: "upstairs", "type": "meta"},
            options=OLD_OPTIONS_META,
        )
        result = _migrate_v2_1_to_v2_2(entry)
        ss = result[ConfigDomains.SECONDARY_STATES]
        assert ss[SecondaryStateOptions.CALCULATION_MODE.key] == "any"

    def test_options_override_data(self):
        """Options values win over matching keys in data."""
        data = {
            CONF_AREA_ID: AREA_ID,
            "type": "exterior",  # data says exterior
            "clear_timeout": 999,
        }
        # options override
        opts = {**OLD_OPTIONS_REGULAR, "type": "interior"}
        result = _migrate_v2_1_to_v2_2(_make_old_entry(data, opts))
        assert result[ConfigDomains.AREA][AreaConfigOptions.TYPE.key] == "interior"

    def test_full_regular_area_all_domains_present(self):
        """Full migration of a regular area produces all expected top-level domains."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        assert ConfigDomains.AREA in result
        assert ConfigDomains.PRESENCE in result
        assert ConfigDomains.SECONDARY_STATES in result
        assert ConfigDomains.USER_DEFINED_STATES in result
        assert ConfigDomains.FEATURES in result

    def test_windowless_true_when_dark_entity_empty(self):
        """Empty dark_entity indicates windowless room."""
        opts = {**OLD_OPTIONS_REGULAR}
        opts["secondary_states"] = {**opts["secondary_states"], "dark_entity": ""}
        result = _migrate_v2_1_to_v2_2(self._entry(opts))
        assert result[ConfigDomains.AREA][AreaConfigOptions.WINDOWLESS.key] is True

    def test_windowless_false_when_dark_entity_set(self):
        """Non-empty dark_entity indicates room has windows/natural light."""
        result = _migrate_v2_1_to_v2_2(self._entry(OLD_OPTIONS_REGULAR))
        # OLD_OPTIONS_REGULAR has dark_entity set to a sensor
        assert result[ConfigDomains.AREA][AreaConfigOptions.WINDOWLESS.key] is False


# ---------------------------------------------------------------------------
# TestAsyncMigrateEntry
# ---------------------------------------------------------------------------


# pylint: disable-next=invalid-name
class TestAsyncMigrateEntry:
    """Integration tests for async_migrate_entry (requires hass)."""

    def _old_entry(self) -> MockConfigEntry:
        return _make_old_entry(
            data={"id": AREA_ID, "type": "interior", "name": "Guest Bedroom"},
            options=OLD_OPTIONS_REGULAR,
        )

    async def test_migrates_v2_1_returns_true(self, hass: HomeAssistant):
        """async_migrate_entry returns True for a v2.1 entry."""
        entry = self._old_entry()
        entry.add_to_hass(hass)
        result = await async_migrate_entry(hass, entry)
        assert result is True

    async def test_migrates_v2_1_bumps_minor_version(self, hass: HomeAssistant):
        """After migration minor_version is updated to MagicConfigEntryVersion.MINOR."""

        entry = self._old_entry()
        entry.add_to_hass(hass)
        await async_migrate_entry(hass, entry)
        assert entry.minor_version == MagicConfigEntryVersion.MINOR

    async def test_migrates_v2_1_data_stripped_to_id_only(self, hass: HomeAssistant):
        """After migration data contains only the CONF_AREA_ID key."""
        entry = self._old_entry()
        entry.add_to_hass(hass)
        await async_migrate_entry(hass, entry)
        assert set(entry.data.keys()) == {CONF_AREA_ID}

    async def test_migrates_v2_1_options_have_domain_structure(
        self, hass: HomeAssistant
    ):
        """After migration options has all expected domain keys."""
        entry = self._old_entry()
        entry.add_to_hass(hass)
        await async_migrate_entry(hass, entry)
        opts = entry.options
        assert ConfigDomains.AREA in opts
        assert ConfigDomains.PRESENCE in opts
        assert ConfigDomains.SECONDARY_STATES in opts
        assert ConfigDomains.USER_DEFINED_STATES in opts
        assert ConfigDomains.FEATURES in opts

    async def test_migrates_v2_1_light_groups_use_groups_list(
        self, hass: HomeAssistant
    ):
        """After migration light_groups feature uses the new 'groups' list format."""
        entry = self._old_entry()
        entry.add_to_hass(hass)
        await async_migrate_entry(hass, entry)
        lg = entry.options[ConfigDomains.FEATURES]["light_groups"]
        assert LightGroupOptions.GROUPS.key in lg
        groups = lg[LightGroupOptions.GROUPS.key]
        # sleep + task lights were non-empty, accent + overhead were empty
        assert len(groups) == 2

    async def test_migrates_v2_1_accent_entity_to_user_defined_state(
        self, hass: HomeAssistant
    ):
        """accent_entity from old secondary_states migrates to user_defined_states."""
        entry = self._old_entry()
        entry.add_to_hass(hass)
        await async_migrate_entry(hass, entry)
        uds_states = entry.options[ConfigDomains.USER_DEFINED_STATES][
            UserDefinedStateOptions.STATES.key
        ]
        assert len(uds_states) == 1
        assert uds_states[0][UserDefinedStateEntryOptions.NAME.key] == "Accented"

    async def test_downgrade_returns_false(self, hass: HomeAssistant):
        """Entry with version > MAJOR returns False (downgrade from future)."""

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Future Area",
            unique_id="future_area",
            data={CONF_AREA_ID: "future_area"},
            options={},
            version=MagicConfigEntryVersion.MAJOR + 1,
            minor_version=1,
        )
        entry.add_to_hass(hass)
        result = await async_migrate_entry(hass, entry)
        assert result is False

    async def test_already_current_version_returns_true(self, hass: HomeAssistant):
        """Entry already at current version returns True without data loss."""

        current_options = {
            ConfigDomains.AREA: {AreaConfigOptions.TYPE.key: "interior"},
            ConfigDomains.PRESENCE: {},
            ConfigDomains.SECONDARY_STATES: {},
            ConfigDomains.USER_DEFINED_STATES: {UserDefinedStateOptions.STATES.key: []},
            ConfigDomains.FEATURES: {},
        }
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Current Area",
            unique_id="current_area",
            data={CONF_AREA_ID: "current_area"},
            options=current_options,
            version=MagicConfigEntryVersion.MAJOR,
            minor_version=MagicConfigEntryVersion.MINOR,
        )
        entry.add_to_hass(hass)
        result = await async_migrate_entry(hass, entry)
        assert result is True
        # Options should be untouched (no v2.1→v2.2 migration ran)
        assert (
            entry.options[ConfigDomains.AREA][AreaConfigOptions.TYPE.key] == "interior"
        )
