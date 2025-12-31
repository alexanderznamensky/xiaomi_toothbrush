# Xiaomi Smart Electric Toothbrush T501 Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Custom Home Assistant integration for **Xiaomi/Soocas Smart Electric Toothbrush T501** (model: `soocare.toothbrush.1501`).

## Features

- **Brushing Detection** — Real-time detection when brushing starts/stops
- **Brushing Duration** — Live counter during brushing, preserves last session time
- **Total Time Today** — Cumulative brushing time for the day
- **Battery Level** — Read via GATT connection after brushing
- **Signal Strength** — Bluetooth RSSI (disabled by default)

## Supported Devices

| Model | Product ID | Status |
|-------|------------|--------|
| Xiaomi Smart Electric Toothbrush T501 | 0x1FF3 | ✅ Supported |
| Soocas T501 | 0x1FF3 | ✅ Supported |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu → "Custom repositories"
4. Add repository URL and select "Integration" category
5. Search for "Xiaomi Toothbrush" and install
6. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Extract `custom_components/xiaomi_toothbrush` to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "Xiaomi Toothbrush"
3. The integration will auto-discover your toothbrush, or you can enter the MAC address manually

## Entities

### Binary Sensor

| Entity | Description |
|--------|-------------|
| `binary_sensor.xiaomi_toothbrush_brushing` | ON when brushing, OFF when idle |

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.xiaomi_toothbrush_battery` | Battery level (0-100%) |
| `sensor.xiaomi_toothbrush_brushing_duration` | Current/last session duration (seconds) |
| `sensor.xiaomi_toothbrush_total_brushing_time_today` | Total brushing time today (seconds) |
| `sensor.xiaomi_toothbrush_signal_strength` | Bluetooth RSSI (dBm) |

## How It Works

The integration uses two methods to collect data:

### 1. BLE Advertisements (Passive)
- Listens to Bluetooth broadcasts from the toothbrush
- Detects brushing state by packet type (encrypted packets = brushing)
- No battery drain on the toothbrush
- Works continuously in the background

### 2. GATT Connection (Active)
- Connects directly to the toothbrush after brushing ends
- Reads battery level from standard BLE Battery Service
- Connection only possible for ~30 seconds after turning off the toothbrush

## Automation Examples

### Morning Reminder

```yaml
automation:
  - alias: "Toothbrush Morning Reminder"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.xiaomi_toothbrush_brushing
        state: "off"
        for:
          hours: 10
    action:
      - service: notify.mobile_app
        data:
          message: "Don't forget to brush your teeth! 🦷"
```

### Brushing Complete Notification

```yaml
automation:
  - alias: "Brushing Complete"
    trigger:
      - platform: state
        entity_id: binary_sensor.xiaomi_toothbrush_brushing
        from: "on"
        to: "off"
    action:
      - service: notify.mobile_app
        data:
          message: >
            Brushing complete! 
            Duration: {{ states('sensor.xiaomi_toothbrush_brushing_duration') }} seconds
```

### Track Brushing Habits

```yaml
automation:
  - alias: "Log Brushing Session"
    trigger:
      - platform: state
        entity_id: binary_sensor.xiaomi_toothbrush_brushing
        from: "on"
        to: "off"
    action:
      - service: logbook.log
        data:
          name: "Toothbrush"
          message: "Brushed for {{ states('sensor.xiaomi_toothbrush_brushing_duration') }} seconds"
```

## Troubleshooting

### Device Not Found

- Make sure Bluetooth is enabled on your Home Assistant host
- Check that the toothbrush is within Bluetooth range (~10 meters)
- Turn the toothbrush on briefly to wake it up

### Battery Not Updating

- Battery is read via GATT connection which only works right after brushing
- Turn the toothbrush on for 2-3 seconds, then off — battery should update within 10 seconds

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.xiaomi_toothbrush: debug
```

## Technical Details

- **BLE Service UUID**: `0000fe95-0000-1000-8000-00805f9b34fb` (Xiaomi MiBeacon)
- **Product ID**: `0x1FF3`
- **Manufacturer**: SOOCAS Tech.Co.,Ltd.
- **Chipset**: Realtek

### Known Limitations

- **Score and Mode** are encrypted in BLE advertisements and cannot be decrypted without reverse-engineering Xiaomi's proprietary authentication
- **GATT connection** only works for ~30 seconds after the toothbrush is turned off
- **Historical data** requires authentication via Xiaomi's `libblecipher.so` library

## Contributing

Contributions are welcome! Please open an issue or pull request.

## License

MIT License

## Credits

- [ble-in-xiaomi](https://github.com/freenetwork/ble-in-xiaomi) — Xiaomi BLE protocol documentation
- [xiaomi-ble](https://github.com/Bluetooth-Devices/xiaomi-ble) — Reference implementation for MiBeacon parsing
