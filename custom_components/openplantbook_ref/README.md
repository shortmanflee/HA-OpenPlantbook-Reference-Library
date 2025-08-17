# Plant Sensor Integration

A Home Assistant custom integration that provides plant care sensors based on data from the OpenPlantBook API.

## Features

- Connects to OpenPlantBook API to fetch plant care requirements
- Creates sensors for optimal plant care parameters:
  - Light levels (minimum/maximum lux)
  - Temperature ranges (minimum/maximum °C)
  - Humidity ranges (minimum/maximum %)
  - Soil moisture ranges (minimum/maximum %)
  - Soil conductivity ranges (minimum/maximum μS/cm)
- Supports plant images as entity pictures
- Full UI configuration - no YAML required
- Device registry integration for proper organization
- Diagnostic support for troubleshooting

## Setup

1. Install the custom component in your `custom_components` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Plant Sensor" and select it
5. Enter your OpenPlantBook API credentials (client_id and secret)
6. Add plant locations using the integration's configuration options

## Requirements

- OpenPlantBook API credentials (register at https://open.plantbook.io/)
- Home Assistant 2024.1+ (for subentry support)

## Configuration

All configuration is done through the Home Assistant UI:

1. **Main Integration**: Enter API credentials
2. **Plant Locations**: Add individual plants via subentries
   - Search OpenPlantBook database by name
   - Select from matching results
   - Customize care parameters as needed

## Integration Quality

This integration follows Home Assistant's Integration Quality Scale and implements:

- ✅ **Bronze**: Config flows, unique entity IDs
- ✅ **Silver**: Entity unavailability handling, parallel updates
- ✅ **Gold**: Device management, diagnostics support
- 🔄 **Platinum**: In progress - strict typing, async dependencies
