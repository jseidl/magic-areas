# Area Aware Media Player (AAMP) - Assist Satellite Extension

This document describes the implementation of assist satellite support for Magic Areas' Area Aware Media Player (AAMP) feature.

## Overview

The AAMP extension adds intelligent routing between traditional media players and assist satellites based on configurable per-area strategies. This allows for flexible audio routing where notifications can go to satellites while media continues to use traditional speakers, or any combination thereof.

## Key Features

### 1. Auto-Discovery
- Automatically discovers assist satellites assigned to each area via Home Assistant's area registry
- No manual entity configuration required - satellites are found by their `area_id` attribute
- Dynamically updates when satellites are added, removed, or reassigned


### 2. Per-Area Satellite Routing
Simple checkbox configuration per area:

- **Route notifications through area satellites**: When enabled, notifications (TTS, announcements, alerts) are sent to assist satellites in the area. Media playback continues to use media players. Automatically falls back to media players if no satellites are available.

### 3. Content-Type Detection
Automatically detects notification vs. media content based on:
- Media type and content ID patterns
- Common TTS/notification keywords: "tts", "announce", "notification", "alert", "reminder"

### 4. Intelligent Fallback
- If satellites unavailable, automatically falls back to media players
- If multiple satellites in area, continues with others if one fails
- Graceful degradation ensures announcements always reach some device


## Implementation Details

### Modified Files

1. **`const.py`**
   - Added assist satellite domain import
   - Added audio routing strategy constants and options
   - Extended AAMP feature schema with routing strategy
   - Updated configuration options

2. **`config_flow.py`**
   - Added audio routing strategy selector to AAMP configuration UI
   - Added translation key support for routing options

3. **`area_aware_media_player.py`**
   - Added assist satellite auto-discovery methods
   - Implemented routing logic based on strategy and content type
   - Enhanced async_play_media with intelligent device selection
   - Added satellite announcement methods with fallback

4. **`translations/en.json`**
   - Added translations for new audio routing options
   - Updated AAMP feature description to include satellites
   - Added selector options for routing strategies

### New Configuration Options

```yaml
# In area configuration
audio_routing_strategy: "satellites_for_notifications"  # Per-area setting
```

### Auto-Discovery Logic

```python
def get_assist_satellites_for_area(self, area):
    """Auto-discover satellites by area assignment."""
    all_satellites = self.hass.states.async_all(ASSIST_SATELLITE_DOMAIN)
    return [s.entity_id for s in all_satellites
            if s.attributes.get("area_id") == area.id]
```

### Routing Decision Matrix


| Configuration | Notification Content | Media Content |
|---------------|---------------------|---------------|
| Checkbox Disabled (Default) | Media Players | Media Players |
| Checkbox Enabled | Satellites → Media Players (fallback) | Media Players |

## Usage Examples

### Setup Process
1. Assign assist satellites to areas in Home Assistant
2. Enable AAMP feature in Magic Areas
3. Check "Route notifications through area satellites" for desired areas
4. AAMP automatically discovers and routes to appropriate devices

### Example Configurations

**Kitchen - Notifications to satellite, music to speakers:**
```yaml
route_notifications_to_satellites: true
```

**Living Room - Everything to media players:**
```yaml

route_notifications_to_satellites: false  # Default
```

**Office - Notifications to satellite, fallback to computer speakers:**
```yaml
route_notifications_to_satellites: true
```

### Service Calls

The AAMP handles routing automatically. Standard media player service calls work:

```yaml
# TTS announcement - routed per area strategy
service: media_player.play_media
target:
  entity_id: media_player.magic_areas_area_aware_media_player_global
data:
  media_content_type: "tts"
  media_content_id: "Meeting in 30 minutes"

# Music playback - routed per area strategy
service: media_player.play_media
target:
  entity_id: media_player.magic_areas_area_aware_media_player_global
data:
  media_content_type: "music"
  media_content_id: "spotify:playlist:xyz"
```

## Benefits

### For Users
- **Flexible Configuration**: Choose the right routing strategy per room
- **Zero Manual Setup**: Satellites discovered automatically by area assignment
- **Intelligent Routing**: Content type determines appropriate device selection
- **Graceful Fallback**: Always works even if preferred devices unavailable
- **Backward Compatible**: Existing configurations work unchanged

### For Magic Areas
- **Minimal Configuration**: Maintains Jan's philosophy of simple setup
- **Clean Architecture**: Extends existing AAMP without breaking changes
- **Consistent UI**: Uses existing configuration patterns and selectors
- **Scalable**: Handles any number of satellites across any number of areas

## Future Enhancements

Potential future improvements:
- Response-required notifications with timeout handling
- Priority-based routing (high-priority to satellites, low-priority to speakers)
- Time-based routing rules (quiet hours route to specific devices)
- Integration with voice feedback systems for effectiveness tracking

## Testing

The implementation includes:
- Content type detection validation
- Routing strategy logic verification
- Fallback mechanism testing
- Service discovery validation
- Area assignment change handling

## Pull Request Readiness

This implementation is ready for submission to Magic Areas as it:
- Follows existing code patterns and architecture
- Includes comprehensive translations
- Maintains backward compatibility
- Uses established configuration UI patterns
- Includes proper error handling and logging
- Respects Magic Areas' minimal configuration philosophy

The extension seamlessly integrates assist satellites into Magic Areas' intelligent home automation ecosystem while maintaining the simplicity and reliability users expect.
