# Capture Metadata Correction - 2026-10-01

The hardware review identified incorrect provenance fields in exported metadata after the ESP32-S3 replacement and BLE/App integration. The IMU CSV values were not changed.

## Problem

Exports made with the old default wrapper recorded:

```text
hardware_revision = H1
trigger_source = boot_button
```

This was correct for the original direct-connection baseline, but not for captures made with the replacement ESP32-S3 or when the iPhone App triggered capture through BLE.

## Corrections

The repository-level project state now uses:

```text
hardware_revision = H2
```

New export wrappers:

```text
tools/export_usb_ble.bat
tools/export_usb_ble_COM6.bat
```

BLE/App exports now record:

```text
hardware_revision = H2
trigger_source = ble_command
power_source = usb_computer
mount_position = bench_handheld
```

The BOOT wrapper remains:

```text
trigger_source = boot_button
```

## Corrected Existing Sessions

The following known App/BLE sessions were corrected without modifying their CSV payloads:

```text
session_20261001_032715/capture_011 through capture_013
session_20261001_034814/capture_001
```

Entries before `capture_011` in `session_20261001_032715` were left at the original `H1 / boot_button` provenance because they were not part of the three confirmed BLE static captures.

## Operational Rule

Use:

```text
export_usb_ble_COM6.bat
```

for captures started by the iPhone App or any future BLE command.

Use:

```text
export_usb_boot_COM6.bat
```

only when capture was started by the physical BOOT button.

