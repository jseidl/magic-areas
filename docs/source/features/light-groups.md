# 💡 Light Groups

Light Groups let you organize lights intelligently, with each group responding automatically to area presence and states. Create as many groups as you need with names that make sense for YOUR home.

## ✅ Unlimited Custom Groups

Unlike rigid category systems, Light Groups are completely flexible. Create groups with custom names:

- **Movie Lights** - Dim ambiance for movie night
- **Desk Lamp** - Task lighting that stays on during work hours
- **Cooking Lights** - Bright lighting over prep areas
- **Bedside Lamps** - Gentle lights for winding down
- **Accent Wall** - Decorative lighting for art display

Each group has full control over when it activates, what triggers it, and whether it requires darkness.

!!! warning
    No group will be created if there are no `light` entities in the area.

## ⚙️ Configuration Options

Each light group you create has these options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| **Group Name** | Text | (required) | Custom name for this group (e.g., "Movie Lights") |
| **Lights** | Entity selector | (required) | Light entities in this group |
| **Active States** | Multi-select | `occupied` | Area states when this group should be active (e.g., `extended`, `sleep`, or any user-defined states like `movie`, `gaming`) |
| **Turn On When** | Multi-select | `area_occupied`, `state_gain`, `area_dark` | Triggers that activate lights |
| **Turn Off When** | Multi-select | `area_clear`, `state_loss`, `exterior_bright` | Triggers that deactivate lights |
| **Require Dark** | Boolean | `True` | Only activate if area is dark |

### 🎯 Turn On Triggers

Choose when lights should turn on:

- **`area_occupied`** - When area transitions from clear to occupied
- **`state_gain`** - When area gains a configured state (while already occupied)
- **`area_dark`** - When area becomes dark (while occupied)

### 🎯 Turn Off Triggers

Choose when lights should turn off:

- **`area_clear`** - When area becomes unoccupied
- **`state_loss`** - When area loses ALL configured states
- **`exterior_bright`** - When outside becomes bright (uses Exterior meta-area or sun.sun fallback)

!!! note "☀️ Sun Integration Required"
    The `exterior_bright` trigger requires the [Sun integration](https://www.home-assistant.io/integrations/sun/) to be enabled for fallback when no Exterior meta-area exists.

!!! tip "🔄 Eliminating Feedback Loops"
    The separate on/off triggers solve the classic problem: lights turning on make the room bright, which used to trigger them to turn off again. Now you can configure lights to turn on when dark but only turn off when you leave or morning arrives—not just because they illuminated the room.

## ☀️ The `require_dark` Toggle

Control whether each group respects darkness:

**`require_dark = True`** (default)
- Group only activates if area is dark
- Uses automatic light sensor resolution (see below)
- Perfect for most lighting scenarios

**`require_dark = False`**
- Group activates based on states alone, ignoring brightness
- Essential for **windowless areas** (bathrooms, closets, basements)
- Useful for **accent lighting** that should always be on (lava lamps, desk accent lights, decorative lighting)
- Great for hallways that need light during the day

### 🔦 How Darkness is Determined

Magic Areas automatically determines if an area is dark using:

1. **Area Light (Calculated)** - If [Aggregates feature](aggregation.md) has illuminance sensors + threshold configured
2. **Area Light Aggregate** - If [Aggregates feature](aggregation.md) has binary light sensors
3. **Windowless Flag** - If enabled, area is always dark (unless local sensors override)
4. **Exterior brightness** - Falls back to Exterior meta-area sensors or sun.sun

!!! note "🔗 Complete Details"
    See [Area States - Dark Detection](../concepts/area-states.md#dark-bright-states) for the full cascading resolution logic.

## 🚀 How It Works

1. **Area state changes** (occupied, dark, sleep, or custom states)
2. **Light groups evaluate** their active states + turn on triggers
3. **If conditions match** → lights activate (respecting `require_dark`)
4. **Turn off triggers** independently control when lights deactivate

!!! warning "💡 Control Switch"
    Turn on the `Light Control ({Area})` switch created by Magic Areas to enable automation. When off, lights respond only to manual control.

## 🧠 Usage Examples

### 🚽 Bathroom Lights (Windowless)

```yaml
Group Name: Bathroom Overhead
Lights: light.bathroom_ceiling
Active States: (leave default - occupied is implied)
Turn On When: area_occupied
Turn Off When: area_clear
Require Dark: False  # ← Always turn on, regardless of time
```

**Why**: Bathrooms have no windows, so lights should always activate when someone enters.

### 🎬 Living Room Movie Lights

```yaml
Group Name: Movie Ambiance
Lights: light.tv_backlight, light.corner_lamp
Active States: movie  # ← Requires custom "movie" user-defined state
Turn On When: state_gain
Turn Off When: state_loss
Require Dark: True
```

**Why**: Only activates when movie mode is enabled, creating perfect ambiance.

### 🌙 Bedroom Overnight

```yaml
Group Name: Bedside Lamps
Lights: light.bedside_left, light.bedside_right
Active States: sleep
Turn On When: area_occupied, state_gain
Turn Off When: area_clear
Require Dark: True
```

**Why**: Gentle lighting when entering bedroom at night or when sleep mode activates.

### 🍳 Kitchen Task Lighting

```yaml
Group Name: Cooking Lights
Lights: light.counter_strips, light.stove_light
Active States: (leave default - occupied is implied)
Turn On When: area_occupied, area_dark
Turn Off When: area_clear, exterior_bright
Require Dark: True
```

**Why**: Turns on when you enter the kitchen and it's dark, turns off when you leave or morning arrives.

### 💼 Office Desk Accent

```yaml
Group Name: Desk Accent Lights
Lights: light.desk_rgb_strip, light.lava_lamp
Active States: work  # ← Custom "work" user-defined state
Turn On When: state_gain
Turn Off When: state_loss
Require Dark: False  # ← Always on during work, regardless of brightness
```

**Why**: Decorative lighting that creates ambiance during work hours, independent of room brightness.

### 🎮 Gaming Setup

```yaml
Group Name: Gaming Lights
Lights: light.desk_rgb, light.wall_panels
Active States: gaming  # ← Custom "gaming" user-defined state
Turn On When: state_gain
Turn Off When: state_loss
Require Dark: False  # ← Gaming lights should be on regardless of ambient light
```

**Why**: Creates immersive gaming atmosphere whenever gaming mode is active.

## 🎚️ Brightness and Color Temperature

Magic Areas controls **when** lights turn on/off, not **how bright** or what color.

For brightness/temperature automation, use:

- [Adaptive Lighting](https://github.com/basnijholt/adaptive-lighting/)
- [Circadian Lighting](https://github.com/claytonjn/hass-circadian_lighting)

These integrate seamlessly with Magic Areas.
