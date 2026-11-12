# 🌍 Meta-Areas

**Meta-Areas** are smart, virtual areas that group multiple regular areas together based on their type or location. Meta-areas are created and configured like any other Magic Area through the UI.

They are perfect for creating higher-level automations that span entire sections of your home — like controlling all lights on a floor, or monitoring the overall air quality inside your house.

## 🏗️ Types of Meta-Areas

Magic Areas supports the following types of meta-areas:

| Meta-Area       | Description |
|-----------------|-------------|
| `Interior`      | Groups all interior areas in your home |
| `Exterior`      | Groups all exterior areas (e.g. garden, patio, garage) |
| `Global`        | A top-level meta-area that includes *all* other areas |
| `$FloorName`    | Groups all areas in a given floor |

!!! note
    Meta-areas are not created automatically: add each one you want with **Add Integration → Magic Areas**, where they're listed as `(Meta) …`.

    A floor meta-area always contains the areas currently on that floor. Moving an area to another floor reloads it, and both floors' meta-areas pick up the change.

    A floor can't have a meta-area if its ID is `global`, `interior` or `exterior`, because those IDs belong to the built-in meta-areas. Home Assistant creates a floor's ID from the name the floor was first created with (a floor first created as "Exterior" keeps the ID `exterior` after you rename it). Magic Areas raises a repair issue for such floors. To fix one, create a new floor with a different name, move the areas onto it, and delete the old floor.

## ⚙️ Features Compatible with Meta-Areas

Many Magic Areas features are fully compatible with meta-areas, allowing you to apply automations across broader zones of your home:

* **[Light Groups](../features/light-groups.md)**
  Control lighting for an entire floor or your whole house.

* **[Cover Groups](../features/cover-groups.md)**
  Manage all blinds or shades in grouped areas together.

* **[Climate Control](../features/climate-control.md)**
  Control your HVAC based on state of entire floor or house.

* **[Media Player Groups](../features/media-player-groups.md)**
  Control speakers or TVs across entire sections of your home.

* **[Aggregation](../features/aggregation.md)**
  Collect sensor data (temperature, humidity, CO₂, etc.) across multiple areas and view them in a single, useful aggregate.

* **[Health Sensors](../features/health-sensor.md)**
  Monitor gas, smoke, leak, and other safety-related issues across an entire floor, interior/exterior, or globally.

---

Meta-Areas are powerful when used as part of a layered automation approach — where individual areas handle local actions, and meta-areas coordinate behaviors across your entire smart home.
