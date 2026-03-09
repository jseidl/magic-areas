# 🎶 Area-Aware Media Player

The **Area-Aware Media Player** is a virtual `media_player` entity that **automatically routes `play_media` actions** to real `media_player` devices in **occupied areas only**.

This ensures messages and notifications are **only played where someone is present**, instead of broadcasting audio throughout the whole house.

✨ Perfect for:

- 📢 **TTS notifications** ([Text-to-Speech](https://www.home-assistant.io/integrations/notify.tts/))
- 🔔 **Context-aware alerts**
- 🧘 Preventing disruptions in quiet or empty rooms

!!! tip
    Works great with [Home Assistant Alerts](https://www.home-assistant.io/integrations/alert/) and other notification automations.

## ⚙️ Configuration Options

!!! warning
    This feature must be **enabled per area**. If an area has it disabled, it will not participate in media routing—even if it’s occupied.

| Option | Description | Default |
|--------|-------------|---------|
| **Notification Devices** | `media_player` entities in this area that can be used for playback. Leave blank to include all devices in the area. | All media players in the area |
| **Notify States** | Area states where playback is allowed. Supports built-in states (`occupied`, `extended`, `sleep`) and any [user-defined states](../concepts/area-states.md#user-defined-states) you've created. | `extended` (avoids triggering on transient occupancy like someone walking by) |

💡 *Use `occupied` for immediate feedback, or stick to `extended` for less noisy results in places like bedrooms.*

## 🚀 How It Works

When you send a `play_media` command to `media_player.magic_areas_area_aware_media_player_global`, Magic Areas will:

1. **Check each area** to see if it's eligible (feature enabled, state allowed, devices available)
2. **Send the media** to all appropriate devices in those areas

### ✅ Playback Rules

- Only **occupied areas** matching the configured states will receive audio
- Media is **duplicated** across multiple areas if more than one qualifies
- **No playback** occurs in sleeping, empty, or excluded areas

## 📣 Example: TTS Notification

```yaml
service: media_player.play_media
target:
  entity_id: media_player.magic_areas_area_aware_media_player_global
data:
  media_content_type: "music"
  media_content_id: "media-source://tts/google_translate?message=The+garage+door+was+left+open"
```

This will play the message **only in occupied areas** using configured media players.


## 🗣️ Example: Notify TTS Integration

You can use this feature as a **TTS notification target** by configuring a `notify` service in your `configuration.yaml`:

```yaml
notify:
  - platform: tts
    name: area_aware_notify
    entity_id: tts.piper
    media_player: media_player.magic_areas_area_aware_media_player_global
```

Then you can use it in your automations like this:

```yaml
service: notify.area_aware_notify
data:
  message: "There's a problem in the laundry room."
```

This will speak the message **only where people are present**.


## 🔗 Related

- See [Area Health](health-sensor.md) for how you can combine this with intelligent alerting.
- Learn more about [TTS notifications](https://www.home-assistant.io/integrations/notify.tts/).
