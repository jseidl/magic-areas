"""Constants for Magic Areas tests."""

from enum import StrEnum, auto

from homeassistant.const import ATTR_FLOOR_ID

from custom_components.magic_areas.const import AreaConfigOptions, AreaType


class MockAreaIds(StrEnum):
    """StrEnum with ids of Mock Areas."""

    KITCHEN = auto()
    LIVING_ROOM = auto()
    DINING_ROOM = auto()
    MASTER_BEDROOM = auto()
    GUEST_BEDROOM = auto()
    GARAGE = auto()
    BACKYARD = auto()
    FRONT_YARD = auto()
    INTERIOR = auto()
    EXTERIOR = auto()
    GLOBAL = auto()
    GROUND_LEVEL = auto()
    FIRST_FLOOR = auto()
    SECOND_FLOOR = auto()


class MockFloorIds(StrEnum):
    """StrEnum with ids of Mock Floors."""

    GROUND_LEVEL = auto()
    FIRST_FLOOR = auto()
    SECOND_FLOOR = auto()


FLOOR_LEVEL_MAP: dict[MockFloorIds, int] = {
    MockFloorIds.GROUND_LEVEL: 0,
    MockFloorIds.FIRST_FLOOR: 1,
    MockFloorIds.SECOND_FLOOR: 2,
}

MOCK_AREAS: dict[MockAreaIds, dict[str, str | None]] = {
    MockAreaIds.KITCHEN: {
        AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
        ATTR_FLOOR_ID: MockFloorIds.FIRST_FLOOR,
    },
    MockAreaIds.LIVING_ROOM: {
        AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
        ATTR_FLOOR_ID: MockFloorIds.FIRST_FLOOR,
    },
    MockAreaIds.DINING_ROOM: {
        AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
        ATTR_FLOOR_ID: MockFloorIds.FIRST_FLOOR,
    },
    MockAreaIds.MASTER_BEDROOM: {
        AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
        ATTR_FLOOR_ID: MockFloorIds.SECOND_FLOOR,
    },
    MockAreaIds.GUEST_BEDROOM: {
        AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
        ATTR_FLOOR_ID: MockFloorIds.SECOND_FLOOR,
    },
    MockAreaIds.GARAGE: {
        AreaConfigOptions.TYPE.key: AreaType.INTERIOR,
        ATTR_FLOOR_ID: MockFloorIds.GROUND_LEVEL,
    },
    MockAreaIds.BACKYARD: {
        AreaConfigOptions.TYPE.key: AreaType.EXTERIOR,
        ATTR_FLOOR_ID: MockFloorIds.GROUND_LEVEL,
    },
    MockAreaIds.FRONT_YARD: {
        AreaConfigOptions.TYPE.key: AreaType.EXTERIOR,
        ATTR_FLOOR_ID: MockFloorIds.GROUND_LEVEL,
    },
    MockAreaIds.INTERIOR: {
        AreaConfigOptions.TYPE.key: AreaType.META,
        ATTR_FLOOR_ID: None,
    },
    MockAreaIds.EXTERIOR: {
        AreaConfigOptions.TYPE.key: AreaType.META,
        ATTR_FLOOR_ID: None,
    },
    MockAreaIds.GLOBAL: {
        AreaConfigOptions.TYPE.key: AreaType.META,
        ATTR_FLOOR_ID: None,
    },
    MockAreaIds.GROUND_LEVEL: {
        AreaConfigOptions.TYPE.key: AreaType.META,
        ATTR_FLOOR_ID: MockFloorIds.GROUND_LEVEL,
    },
    MockAreaIds.FIRST_FLOOR: {
        AreaConfigOptions.TYPE.key: AreaType.META,
        ATTR_FLOOR_ID: MockFloorIds.FIRST_FLOOR,
    },
    MockAreaIds.SECOND_FLOOR: {
        AreaConfigOptions.TYPE.key: AreaType.META,
        ATTR_FLOOR_ID: MockFloorIds.SECOND_FLOOR,
    },
}

DEFAULT_MOCK_AREA: MockAreaIds = MockAreaIds.KITCHEN
