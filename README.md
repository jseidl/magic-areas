![Build Status][ci-status] [![GitHub Release][releases-shield]][releases] [![License][license-shield]](LICENSE) [![GitHub Last Commit][last-commit-shield]][commits]
![Project Maintenance][maintenance-shield] [![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![HACS][hacs-shield]][hacs] ![integration-usage-shield] [![Discord][discord-shield]][discord]

# Magic Areas for Home Assistant: Your areas so smart it's almost magic! 🪄

![ma-logo]

Magic Areas is a Home Assistant custom integration that makes your smart home think for itself through rock-solid presence tracking — the foundation for a truly smart home.

Magic Areas knows when a room is occupied (and when it’s not) and reacts automatically. It turns Home Assistant’s Areas into dependable, presence-aware zones so your home feels alive without you lifting a finger. Instead of building dozens of manual automations, let Magic Areas control your lights, climate, and other devices so that they do just right thing, at the right time.

### What this means for you:

- 🏠 Areas that know when they’re occupied (and when they’re clear)
- 💡 Lights that only turn on when (and where) they’re needed
- 🌡 Climate that adapts to your presence and routines
- 🌀 Fans that respond automatically to heat, humidity, or CO₂
- 🎶 Media and alerts routed only to occupied spaces

Smart areas that just works, everytime, out of the box. Fully customizable if you want it.

#### Download and install through [HACS (Home Assistant Community Store)](https://hacs.xyz/):

[![Open your Home Assistant instance and open the Adaptive Lighting integration inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jseidl&repository=magic-areas&category=integration)

## ✨ What Magic Areas Does

* Detects presence in each area using multiple sources (motion sensors, media players, device trackers, BLE beacons, and more).
* Creates smart groups (lights, fans, climate, media players) that respond to an area’s state automatically.
* Supports secondary states like dark, sleep, and extended for context-aware automation.
* Provides meta-areas (e.g., Interior, Exterior, Global, Floors) to coordinate multiple areas at once.
* Includes built-in, automation-like features: light control, fan groups, climate preset switching, and more

> [!NOTE]
> Check out our [magic concepts on our documentation](https://magicareas.io/concepts/).

## Features

### Presence
* **🕰️ Smart Presence Timeouts:** Each area has a configurable timeout for clearing presence after the last motion. If motion is detected again within the timeout, it resets — no abrupt shutoffs.
* **✋ Presence Hold:** Creates a switch to manually override presence in an area. Useful if sensors aren’t fully reliable yet or for guests.
* **🕯️ Secondary States:** Define subtle room states for more nuanced automations:
    * `dark` / `bright`: Based on light sensors or sun
    * `sleep`: Tracked by any entity
    * `extended`: When a room has been occupied beyond a set time
    * `accented`: Track presence based on entertainment like media players
* **🏠 Meta-Areas and Hierarchies:** Set areas as **interior**, **exterior** and assign them to **floors**. Magic Areas will create meta-areas to track grouped presence (e.g., upstairs occupied). Presence logic and secondary states are inherited and calculated automatically.

### Smart Control
* **💡 Smart Light Groups**: Automatically groups your lights by purpose — overhead, task, accent, and sleep — and controls them based on presence state. Lights can be set to trigger only in the dark or after extended occupancy.
* **🌡️ Climate Control:** Map area states to climate device presets. For example: set your HVAC to `eco` when empty, and back to `comfort` when occupied or in sleep mode.
* **🧠 Wasp in a Box:** Reliable presence sensing that accounts for people entering/leaving rooms with doors. Combines motion and door/garage sensors to prevent lights from turning off while you’re still inside.
* **🔥 Fan Groups:** Auto-creates a `fan` group entity for each area and lets you control it using an aggregated value like temperature, humidity, or CO₂. Great for exhaust fans, ceiling fans, or air quality fans.
* **📶 Area-Aware Media Player:** Play media (like TTS alerts) only in rooms that are currently occupied. Forward notifications to the right areas — not empty ones.
* **🧮 Sensor Aggregates:** Aggregates all `sensor` and `binary_sensor` entities in the area by `device_class` and `unit_of_measurement`. Great for dashboards, alerts, and logic.
* **🚨 Health Sensor:** Auto-aggregated binary sensors for safety-related device classes:
    * `gas`, `smoke`, `moisture` (leaks), `problem`, `safety`
* **📡 BLE Tracker Integration:** Track text-based BLE sensors (like ESPresense, Bermuda, or Room Assistant) directly. Magic Areas will convert their values into usable presence sensors automatically.

> [!TIP]
> Learn more about all features on [our documentation](https://magicareas.io/features/).

## 🧙 Demo / How can Magic Areas help me?

Check out the [Implementation Ideas](https://magicareas.io/how-to/implementation-ideas/) documentation to see how you can apply Magic Areas to make every room in your house, magic!

## 🚀 Getting Started

Go to the documentation [Quick Start](https://magicareas.io/how-to/getting-started/) for installation instruction.

📖 Visit the [documentation](https://magicareas.io/how-to/implementation-ideas/) for complete guides, examples, and tips.

Enjoy smarter automations — and areas that finally understand you're still in the room ✨

## 🛠️ Problems/bugs, questions, feature requests?

Visit the [Troubleshooting](https://magicareas.io/how-to/troubleshooting/) documentation for instructions on getting help.

## 🌐 Magic Areas in your language!

Magic Areas has full translation support, meaning even your entities will be translated and is available in the following languages:

<a href="https://hosted.weblate.org/engage/magic-areas/">
<img src="https://hosted.weblate.org/widget/magic-areas/multi-auto.svg" alt="Translation status" />
</a>

Help to translate Magic Areas into your language from your web browser! We use [Hosted Weblate](https://hosted.weblate.org/engage/magic-areas/) so you don't need to fool around with pull requests nor JSON files!

## ❤️ Love Magic Areas?

Magic Areas is a passion project built and maintained with countless hours of development, testing, documentation, and supporting our amazing community.
If you’ve found it useful and want to show some love, consider buying me a beer! 🍻

Your support helps keep the project alive and is **hugely appreciated**.  ❤️

[![BuyMeCoffee][buymecoffeebadgebig]][buymecoffee]


***

[magic_areas]: https://github.com/jseidl/hass-magic_areas
[buymecoffee]: https://www.buymeacoffee.com/janseidl
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[buymecoffeebadgebig]: https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png
[commits-shield]: https://img.shields.io/github/commit-activity/y/jseidl/hass-magic_areas.svg?style=for-the-badge
[commits]: https://github.com/jseidl/hass-magic_areas/commits/main
[discord]: https://discord.gg/3yu2F7bSaT
[hacs]: https://github.com/hacs/integration
[discord-shield]: https://img.shields.io/discord/928386239789400065?style=for-the-badge&label=Discord
[license-shield]: https://img.shields.io/github/license/jseidl/hass-magic_areas.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Jan%20Seidl%20%40jseidl-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/jseidl/hass-magic_areas.svg?style=for-the-badge
[releases]: https://github.com/jseidl/hass-magic_areas/releases
[ci-status]: https://img.shields.io/github/actions/workflow/status/jseidl/hass-magic_areas/validation.yaml?style=for-the-badge
[last-commit-shield]: https://img.shields.io/github/last-commit/jseidl/hass-magic_areas?style=for-the-badge
[ma-logo]: https://raw.githubusercontent.com/home-assistant/brands/master/custom_integrations/magic_areas/logo.png
[contributors-badge]: https://flat.badgen.net/github/contributors/jseidl/hass-magic_areas
[integration-usage-shield]: https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.magic_areas.total&style=for-the-badge
[hacs-shield]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
