# ⚙️ Configuration

Magic Areas configuration is divided into four main sections, plus additional configuration options for enabled features.

Each section allows you to fine-tune how areas behave, how presence is detected, and how states are managed.

## 🏠 Basic Area Options

These options control the general behavior of the area.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| **Area type** | `string` | `interior` | Defines the area type. Options: `interior`, `exterior`. Used for meta-area calculations. |
| **Include entities** | `list<entity>` | `[]` | Force-add entities to the area, even if not assigned to it in Home Assistant. |
| **Exclude entities** | `list<entity>` | `[]` | Force-remove entities from the area. Useful if you want them in Home Assistant but excluded from Magic Areas calculations. |
| **Windowless Area** | `bool` | `false` | Enable for areas with no natural light (bathrooms, closets, basements). Prevents fallback to exterior sensors/sun.sun for dark detection. |
| **Automatic reload on registry updates** | `bool` | `true` | Automatically reloads the area if a new device or entity is added/removed. |
| **Ignore diagnostic/config entities** | `bool` | `true` | Prevents Magic Areas from using diagnostic/config sensors (e.g., CPU temperature) that could skew aggregates. |

## 🚶 Presence Tracking Options

These options define how presence is detected and maintained within an area.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| **Platforms** | `list<string>` | `media_player`, `binary_sensor` | Platforms used for presence sensing. Options: `media_player`, `binary_sensor`, `device_tracker`, `remote`. |
| **Presence sensor device classes** | `list<string>` | `motion`, `occupancy`, `presence` | Device classes of binary sensors considered as presence sensors. Supports all binary sensor classes. |
| **Keep-only entities** | `list<entity>` | `[]` | Entities that will only be considered if the area is already occupied (triggered by another sensor). |
| **Clear timeout** | `int (minutes)` | `1` | Time to wait before clearing the area after no presence is detected. |

## 🧠 Secondary States Configuration

Area states go beyond basic presence (`occupied`/`clear`) and allow secondary states such as `dark`, `sleep`, `extended`, and user-defined states.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| **Sleep state entity** | `entity` | – | Binary sensor, switch, or input_boolean indicating sleep mode |
| **Sleep timeout** | `int (minutes)` | `1` | Time before clearing sleep state after entity goes off |
| **Extended state time** | `int (minutes)` | `5` | Continuous presence time before entering extended state |
| **Extended timeout** | `int (minutes)` | `10` | Time before clearing extended state after presence ends |
| **Calculation mode** | `select` | `majority` | How meta-areas aggregate child states: `any`, `all`, `majority` |

### 🌙 Dark/Bright States

**Fully automatic!** Magic Areas intelligently determines which sensor to use for darkness detection:

1. Area Light (Calculated) from [Aggregates](../features/aggregation.md) illuminance threshold
2. Light aggregate from [Aggregates](../features/aggregation.md) binary sensors
3. Windowless area setting (always dark)
4. Exterior meta-area sensors
5. sun.sun position

No configuration needed. See [Area States - Dark Detection](../concepts/area-states.md#dark-bright-states) for details.

!!! note "☀️ Sun Integration Required"
    The [Sun integration](https://www.home-assistant.io/integrations/sun/) must be enabled for fallback when no other light sources are available.

### 🏠 Windowless Areas

For rooms with no natural light (bathrooms, closets, interior rooms), enable **"Windowless Area"** in Basic Area Options.

**Effect**: Prevents fallback to exterior sensors or sun.sun, ensuring the area is always considered dark unless local sensors indicate otherwise.

**Note**: If you have light sensors or configured an illuminance threshold for a windowless area, those local sensors are still used.

### 🎭 User-Defined States

Create custom states beyond the built-in options:

1. Navigate to **Secondary States** → **User-Defined States**
2. Click **"Add User-Defined State"**
3. Enter **State Name** (e.g., "Movie", "Gaming", "Work")
4. Select **Entity** (binary_sensor, switch, input_boolean)
5. Save

These states become available in:
- Light Groups (active states)
- Area-Aware Media Player (notification states)
- Climate Control (via automations)

Multiple states can be configured per area, giving you complete control over automation context.

!!! tip "💡 Good State Examples"
    Use states that represent **modes or activities**: `movie`, `gaming`, `work`, `reading`, `cooking`, `party`.
    Avoid location-based names—the area already defines the location.

## ✨ Feature Selection

This section provides checkboxes in the UI for enabling or disabling specific Magic Areas features.

!!! info
    📖 See the [Features](../features/index.md) page for the full list of available features.

## 🔧 Feature-Specific Configuration

Once features are enabled, each comes with its own configuration options.

!!! info
    📘 Refer to the corresponding feature documentation under [Features](../features/index.md) for detailed setup instructions.

✅ That’s it! You now have a flexible configuration system where you can start simple and layer in advanced states and features as needed.
