# Area-Aware Media Player: Assist Satellite Integration

## Overview

Magic Areas' Area-Aware Media Player (AAMP) now supports intelligent routing to assist satellites, enabling smart separation between notifications and media content across your home.

## Key Features

### 🎯 **Intelligent Content Routing**
- **Notifications** (TTS, announcements, alerts) → Assist satellites
- **Media** (music, podcasts) → Traditional media players
- **Auto-detection** of content type based on media patterns

### 🔍 **Auto-Discovery**
- Automatically finds assist satellites assigned to each area
- Zero manual configuration - just assign satellites to areas in Home Assistant
- Dynamic updates when satellites are added/removed/reassigned

### 📱 **Per-Area Configuration**
- Simple checkbox per area: "Route notifications through area satellites"
- Disabled by default - preserves existing behavior
- Enable per area as needed for intelligent routing

### 🛡️ **Robust Fallback**
- Graceful degradation if satellites unavailable
- If multiple satellites in area, continues with others if one fails
- Falls back to media players if all satellites fail or are offline

## Configuration

### 1. Setup Assist Satellites
Assign your assist satellites to areas in Home Assistant:
- Go to **Settings → Devices & Services**
- Find your assist satellite device
- Edit device → **Assign to area**

### 2. Enable AAMP Feature
In Magic Areas integration:
- **Options → Area Configuration**
- Select **"Area-aware media player"** feature
- Configure per area as needed

### 3. Configure Satellite Routing
For each area where you want satellite routing:
- ☑ **"Route notifications through area satellites"**

## Usage Examples

### Kitchen Setup
```yaml
# Kitchen configuration
route_notifications_to_satellites: true
```

**Result:**
- *"Dinner is ready!"* → Kitchen assist satellite 🔊
- *Spotify cooking playlist* → Kitchen smart speakers 🎵

### Living Room Setup
```yaml
# Living room configuration
route_notifications_to_satellites: false
```

**Result:**
- *Everything* → Living room media players (traditional behavior)

### Office Setup
```yaml
# Office configuration
route_notifications_to_satellites: true
```

**Result:**
- *"Meeting in 5 minutes"* → Office assist satellite 🔊
- *Background music* → Computer speakers 🎵
- *If satellite offline* → Falls back to computer speakers

## Service Calls

Standard Home Assistant service calls work automatically:

### TTS Announcements
```yaml
service: media_player.play_media
target:
  entity_id: media_player.magic_areas_area_aware_media_player_global
data:
  media_content_type: tts
  media_content_id: "Package delivered to front door"
```

### Music Playback
```yaml
service: media_player.play_media
target:
  entity_id: media_player.magic_areas_area_aware_media_player_global
data:
  media_content_type: music
  media_content_id: "spotify:playlist:37i9dQZF1DX0XUsuxWHRQd"
```

## Content Detection

The system automatically detects notification content:

**Notification Patterns:**
- Media types: `tts`, `announcement`, `alert`
- Content keywords: `announce`, `notification`, `alert`, `reminder`, `warning`, `emergency`

**Everything else** is treated as media content.

## Benefits

### 🏠 **Better Home Audio Experience**
- Voice announcements through dedicated voice assistants
- Music continues uninterrupted on quality speakers
- Clear separation of notification vs. entertainment audio

### ⚙️ **Simple Configuration**
- Single checkbox per area
- Auto-discovery eliminates manual setup
- Backward compatible - disabled by default

### 🔧 **Reliable Operation**
- Robust error handling and fallback mechanisms
- Individual device failure doesn't stop other announcements
- Comprehensive logging for troubleshooting

### 🚀 **Future-Ready**
- Foundation for advanced features (volume ducking, response-required notifications)
- Extensible architecture for additional device types
- Follows Magic Areas' design principles

## Troubleshooting

### Satellites Not Discovered
**Check:**
- Satellites assigned to correct areas in HA
- Satellites have `area_id` attribute
- Magic Areas restarted after satellite area assignment

**Debug:**
```yaml
# Enable debug logging
logger:
  logs:
    custom_components.magic_areas.media_player: debug
```

### Notifications Still Going to Media Players
**Check:**
- "Route notifications through area satellites" enabled for area
- Content matches notification patterns
- Satellites are available and responsive

### Fallback Behavior
The system automatically falls back to media players when:
- No satellites found in area
- Satellites are offline/unavailable
- Satellite service calls fail

This ensures announcements always reach users through available devices.

## Technical Implementation

See [AAMP_ASSIST_SATELLITE_EXTENSION.md](AAMP_ASSIST_SATELLITE_EXTENSION.md) for technical implementation details.

---

**Transform your smart home's audio experience with intelligent, area-aware routing that just works!** 🎉
