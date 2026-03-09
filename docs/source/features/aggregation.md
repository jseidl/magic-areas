# 🧮 Aggregation

The **Aggregation** feature is a **foundational component** of Magic Areas that creates aggregate sensors for `sensor` and `binary_sensor` entities in each area, grouped by `device_class` and `unit_of_measurement`.

!!! tip "🌟 Why Aggregates Matter"
    Aggregates power many other Magic Areas features:

    - **Dark/Bright Detection** - Area Light (Calculated) sensor determines when areas need lighting
    - **Wasp in a Box** - Uses aggregated motion and door sensors
    - **Fan Groups** - Monitors aggregated temperature, humidity, or air quality
    - **Health Sensors** - Aggregates safety-critical sensors

    Even if you don't directly use aggregate sensors in your automations, enabling this feature unlocks intelligent behavior throughout Magic Areas.

## 📊 What Gets Aggregated

Entities are aggregated by their `device_class`:

- **Binary Sensors**: Motion, occupancy, door, window, light, moisture, etc.
- **Sensors**: Temperature, humidity, illuminance, power, energy, etc.

!!! note "Entity Naming"
    Aggregates use the template:
    ```
    (binary_)?sensor.magic_areas_aggregates_{area}_aggregate_{device_class}
    ```
    When multiple units exist for the same device class, an `_{unit}` suffix is added.

This is especially useful for simplifying automations and dashboards, since you can reference a single "aggregate" instead of many individual sensors.

## 🔦 Area Light (Calculated)

When you configure an **illuminance threshold**, the Aggregates feature creates a special binary sensor:

`binary_sensor.magic_areas_threshold_{area}_threshold_light`

This "Area Light (Calculated)" sensor:
- Monitors aggregated illuminance sensors in the area
- Turns `on` when light levels drop below your threshold
- Turns `off` when levels rise above threshold (with optional hysteresis)
- **Automatically used for dark/bright state detection** (see [Area States](../concepts/area-states.md))

!!! example "How It Works"
    With 3 illuminance sensors averaging 45 lux and threshold set to 50:

    - Area Light (Calculated) → `on` (dark)
    - Area state includes `dark`
    - Light groups with `require_dark=True` can activate

!!! tip "💡 Recommended Threshold"
    For residential areas, start with 30-50 lux as your illuminance threshold. Adjust based on your preference for when lights should activate.

## ⚙️ Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| **Minimum number of entities** | Integer | `1` | Minimum entities required to create an aggregate. Set to `1` to always create aggregates (even single sensors). |
| **Binary sensor device classes** | Device class list | door, light, motion, occupancy, window | Binary sensor device classes to aggregate |
| **Sensor device classes** | Device class list | humidity, illuminance, temperature | Sensor device classes to aggregate |
| **Illuminance threshold** | Integer (lux) | `0` (disabled) | Creates Area Light (Calculated) sensor when illuminance drops below this value |
| **Threshold hysteresis** | Integer (%) | `0` | [Hysteresis](https://www.home-assistant.io/integrations/threshold/#hysteresis) prevents flapping by requiring illuminance to change by this percentage before toggling |

## 📊 Aggregation Methods

- **Binary Sensor** → Aggregate is `on` if **any** entity is `on` (except connectivity/plug device classes which use `all`).
- **Sensor** → Values are **averaged**, except for `power`, `current`, and `energy`, which are **summed** (total consumption).

## 💡 Example Use Cases

### 🌙 Automatic Dark Detection
Enable aggregates with illuminance sensors + threshold. Magic Areas automatically uses the Area Light (Calculated) sensor for darkness detection—no additional configuration needed.

Perfect for light automation that responds to actual room brightness instead of just time of day.

### 🔥 Temperature Management
Use `sensor.magic_areas_aggregates_{area}_aggregate_temperature` to get the average temperature of a room or floor:
- Automate HVAC systems based on area average temperature
- Compare temperatures across multiple areas
- Drive Fan Groups based on actual conditions

### 💨 Air Quality & Ventilation
Aggregate `co2`, `humidity`, or `voc` into a single sensor like `sensor.magic_areas_aggregates_{area}_aggregate_humidity`:
- Trigger fans or dehumidifiers when humidity rises
- Monitor long-term air quality trends
- Use with Fan Groups for automated ventilation

### ⚡ Power Monitoring
Use `sensor.magic_areas_aggregates_{area}_aggregate_power` to track total power consumption for an area:
- Shut off non-essential devices when usage spikes
- Display dashboards comparing power usage per area
- Track energy consumption on the [Energy Dashboard](../how-to/library/energy-aggregates.md)

### 🧠 Simplified Automations
Aggregates make automation logic cleaner:

```yaml
- alias: Turn off humidifier when area unoccupied
  trigger:
    - platform: state
      entity_id: binary_sensor.magic_areas_presence_tracking_bedroom_area_state
      to: "off"
      for: "5m"
  action:
    - service: humidifier.turn_off
      target:
        entity_id: humidifier.bedroom_humidifier
```

Instead of checking multiple sensors individually, you just check the aggregate.
