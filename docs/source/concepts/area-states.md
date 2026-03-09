# 🏠 Area States

Magic Areas' primary goal is to understand and track an **area's presence state** — that is, whether someone is currently there. But it doesn't stop there: Magic Areas also monitors a set of **secondary states** that enrich how automations behave in each area.

## 🟢 Presence State

For each area you make magic, Magic Areas does the following:

1. Scans the area for all associated entities.
2. Identifies which entities are valid **presence sensors** (see: [Presence Sensing](presence-sensing.md)).
3. Automatically creates a binary sensor entity:
   `binary_sensor.magic_areas_presence_tracking_{area_id}_area_state`

This sensor reflects the **presence state** of the area:

- When any presence entity enters a **presence state** (`on`, `home`, `playing`), the area is considered **occupied** (`on`).
- Once all presence entities leave those states, Magic Areas waits for a short delay (configured via `Clear Timeout`) before marking the area as **clear** (`off`).

!!! note
    Magic Areas automatically listen for area changes on entities.
    Changing an entity's area will cause Magic Areas to reload.

## 🌙 Dark & Bright States

Magic Areas automatically tracks whether each area is dark or bright for intelligent light automation.

### 🔦 Automatic Light Detection

The system intelligently determines darkness using cascading sources:

#### Resolution Priority

**1. Area Light (Calculated)** ⭐ Most Accurate
- **Created by**: [Aggregates feature](../features/aggregation.md) with illuminance threshold
- **Entity**: `binary_sensor.magic_areas_threshold_{area}_threshold_light`
- **How**: Monitors average illuminance from sensors in the area
- **Example**: 3 lux sensors averaging 45 lux with 50 lux threshold → dark

**2. Area Light Aggregate**
- **Created by**: [Aggregates feature](../features/aggregation.md) with binary light sensors
- **Entity**: `binary_sensor.magic_areas_aggregates_{area}_aggregate_light`
- **How**: Combines multiple binary light sensors (any `on` = bright)

**3. Windowless Areas** 🚪
- **Configured via**: "Windowless Area" toggle in area settings
- **Behavior**: Area is **always dark**
- **Use for**: Bathrooms, closets, basements with no natural light
- **Important**: If the area has illuminance sensors or light aggregates, those are used first. Windowless only prevents fallback to exterior sensors/sun.

**4. Exterior Meta-Area Sensors**
- **Fallback for**: Interior areas without own sensors
- **Uses**: Exterior's Area Light (Calculated) or aggregate
- **Logic**: Indoor areas can reference outdoor brightness

**5. sun.sun** ☀️ Always Available
- **Final fallback**: Never fails
- **States**: `below_horizon` = dark, `above_horizon` = bright
- **Requires**: [Sun integration](https://www.home-assistant.io/integrations/sun/) to be enabled

!!! tip "🏠 Windowless Area Behavior"
    The Windowless toggle prevents fallback to exterior sensors and sun.sun. If your windowless bathroom has binary light sensors or you've configured an illuminance threshold via [Aggregates](../features/aggregation.md), Magic Areas will still use those sensors. Windowless only affects the fallback chain.

### Safe Defaults

If any sensor becomes unavailable, the area defaults to **dark** to ensure lights activate when needed.

### Example Scenarios

**Living Room with Illuminance Sensors:**
- Has `sensor.living_room_lux_1`, `sensor.living_room_lux_2`
- [Aggregates](../features/aggregation.md) enabled with 50 lux threshold
- **Result**: Uses Area Light (Calculated) for most accurate detection

**Bedroom with Binary Light Sensors:**
- Has `binary_sensor.bedroom_window_light`
- [Aggregates](../features/aggregation.md) enabled (no threshold)
- **Result**: Uses Area Light Aggregate

**Bathroom (Windowless):**
- Windowless flag enabled
- No light sensors
- **Result**: Always dark (lights activate immediately when occupied)

**Bathroom (Windowless with Sensor):**
- Windowless flag enabled
- Has `binary_sensor.bathroom_light`
- **Result**: Uses the bathroom light sensor, not always dark

**Office (No Sensors):**
- No light sensors in area
- Exterior meta-area has sensors
- **Result**: Uses exterior brightness for detection

**Utility Room (Ultimate Fallback):**
- No sensors, no aggregates
- **Result**: Uses `sun.sun` position

## 🎭 User-Defined States

Beyond built-in states, create unlimited custom states matching your lifestyle:

**Examples of Good Area States:**
- **`movie`** - Tied to movie mode scene/input_boolean
- **`gaming`** - Gaming mode active
- **`work`** - Work hours sensor
- **`party`** - Party mode automation
- **`reading`** - Reading mode (e.g., triggered by vibration sensor in reading chair)
- **`cooking`** - Active cooking mode
- **`meditation`** - Zen/meditation mode

**Configuration:**
1. Navigate to Secondary States → User-Defined States
2. Click "Add User-Defined State"
3. Enter name (e.g., "Reading")
4. Select entity (binary_sensor, switch, input_boolean)

**Use in Features:**
- **[Light Groups](../features/light-groups.md)** - Create "Reading Lights" active only in reading mode
- **[Area-Aware Media Player](../features/area-aware-media-player.md)** - Route notifications only to non-movie areas
- **Climate Control** - Different presets based on custom states

!!! tip "💡 State vs. Location"
    User-defined states should represent **modes or activities** (reading, gaming, working), not **physical locations** (reading nook, gaming corner). The area itself represents the location.

## 📊 Secondary States Reference

| State | Triggered By | Description |
|-------|--------------|-------------|
| `dark` | Area Light (Calculated), light aggregate, windowless flag, or fallbacks | Area has insufficient light |
| `bright` | Inverse of dark | Area has sufficient light |
| `sleep` | Sleep Entity (binary_sensor/switch/input_boolean) | Sleep mode active |
| `extended` | Automatic after Extended Time seconds of continuous presence | Long-term occupancy |
| **User-defined** | Custom entities you configure | Any custom states (movie, gaming, work, etc.) |

## 💡 How Secondary States Are Used

Several Magic Areas features take advantage of these secondary states to fine-tune their behavior:

- **[Light Groups](../features/light-groups.md)**
  Use both presence and secondary states to determine which lights to turn on (e.g. only movie lighting when in movie mode and dark).

- **[Climate Control](../features/climate-control.md)**
  Can trigger presets based on state (e.g. only change temperature after an area has been `occupied` for a while → `extended`).

- **[Area-Aware Media Player](../features/area-aware-media-player.md)**
  Filters notification playback based on secondary states, such as avoiding alerts in sleeping areas or playing TTS messages only in extended occupancy.

- **[Fan Groups](../features/fan-groups.md)**
  Can require specific states (like `extended`) before activating ventilation based on sensor thresholds.

---

By layering **presence** with **secondary states**, Magic Areas gives you fine-grained, context-aware control over your automations — making each room react more intelligently to how it's being used.
