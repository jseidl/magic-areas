# 🌬️ Fan Groups

Fan Groups work similarly to a simplified version of the [Generic Thermostat](https://www.home-assistant.io/integrations/generic_thermostat/). This feature groups all fans within an area—whether you have one or many—and allows you to monitor an [aggregate sensor](aggregation.md) of a selected `device_class` such as `temperature` 🌡️, `humidity` 💧, or `co2` 🫁.

The fans will automatically turn `on` 🔛 when the tracked sensor's value rises above a configured `setpoint`, and turn `off` 🔘 when it falls below.

!!! note "🧮 Requires Aggregates Feature"
    Fan Groups monitor aggregate sensors created by the [Aggregates feature](aggregation.md). Ensure Aggregates is enabled with the device class you want to track (temperature, humidity, CO₂, etc.).

## ⚙️ Configuration Options

| Option                 | Type    | Default   | Description                                                                 |
|------------------------|--------|-----------|-----------------------------------------------------------------------------|
| Required state         | string | `occupied` | Area must be in this state for fans to activate.                            |
| Tracked device class   | string | n/a       | Aggregate device class to monitor (e.g., `temperature`, `humidity`, `co2`). |
| Setpoint               | number | n/a       | Value threshold at which fans turn on/off.                                   |

## 🛠️ Example Use Cases

* Turning fans on when it's too hot 🔥
* Activating bathroom exhaust fans when humidity is too high 💦
* Turning on ventilation fans if CO2 levels become elevated 🏭
