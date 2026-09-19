# Hardware Sync - Battery and Boost Validation

Date: 2026-09-19

Branch: `codex/hardware-bringup`

Software baseline: F4

## Result

The battery and boost supply path completed five consecutive captures:

```text
3 static captures
2 small arm-raise captures
```

All five files passed:

```text
approximately 2269-2270 rows
approximately 226.9 Hz
maximum interval below 10 ms
no gaps of 20 ms or more
no empty or partial file
no saturation
```

This confirms that the battery, TP4057 path, SS-12E07G4 switch, and TPS61088
can power the ESP32 and ICM during both static and light-motion captures.

## Current Power Chain

```text
protected 3.7 V battery
-> TP4057 BAT+ / BAT-
-> SS-12E07G4 3 A switch on battery positive
-> TPS61088 fixed 5 V boost
-> ESP32 5V and GND
```

## Remaining Hardware Work

The electrical path is now functional, but the wearable assembly is not yet
complete:

- secure battery, TP4057, switch, and boost module in the forearm pouch
- add strain relief for all battery, power, USB, and sensor cables
- prevent the battery pouch from pulling on the ESP32 or ICM harness
- keep USB-C, BOOT, and RGB LED accessible
- confirm TP4057 charge behavior with the ESP32 load switched off
- repeat five captures after final mechanical fixation

## Safety Rules

- Do not connect USB 5 V and battery-boost 5 V at the same time.
- Keep the ESP32 load off while charging through TP4057.
- Do not use the boost EN pin as the main power switch.
- Keep `SS12D07VG4` out of the main boost input current path.
