# Software and Mobile Handoff - 2026-10-01

This note records the wireless capture path completed on 2026-10-01: replacement ESP32-S3, BLE-only control firmware, the iPhone companion app, and the first verified light-to-telemetry alignment.

## Firmware

The current wrist-node firmware is:

```text
firmware/imu_flash_logger_v4/imu_flash_logger_v4.ino
```

Key behavior:

- ESP32-S3 DevKitC-1 N16R8, ICM-20948 at I2C address `0x68`
- 10-second capture window
- approximately 227 Hz effective sample rate
- LittleFS CSV and telemetry output
- BOOT button remains available as a local backup trigger
- no BLE HID, keyboard, or media-key advertising
- custom BLE control service only

BLE identity and protocol:

```text
Name: KineShoot-Cam
Service: 6b1d0001-9a3f-4d2a-8f6f-6b1d00000001
Characteristic: 6b1d0002-9a3f-4d2a-8f6f-6b1d00000002
Command 0x01: start IMU capture
```

Expected startup serial:

```text
BLE_CONTROL_READY,name=KineShoot-Cam,...
BLE_CONNECTED
BLE_COMMAND,capture
CAPTURE_START,file=/capture_001.csv,seconds=10
CAPTURE_DONE,...
```

RGB status:

```text
Blue: ready and advertising
Red: active IMU capture
Green: CSV and telemetry write completed
```

Green is a write-complete marker, not the motion end instant. The CSV capture window ends before green while the board writes data to LittleFS.

## iPhone App

The app is under:

```text
mobile/ios/KineShootRemote
```

Current tested version:

```text
KineShootRemote 1.5.1 (8)
```

Features:

- CoreBluetooth connection to `KineShoot-Cam`
- AVFoundation video recording
- live rear or front camera preview
- front/rear camera switch while idle
- zoom slider
- 1080p60 recording using `AVCaptureSession.Preset.inputPriority`
- 1-second blue-light pre-roll before the BLE capture command
- 14-second recording window
- automatic save to Photos
- privacy descriptions for Bluetooth, camera, microphone, and Photos

The iOS build runs in GitHub Actions and publishes an unsigned IPA for free Apple ID signing with AltStore or Sideloadly. The first install through a free Apple ID normally expires after 7 days and must be re-signed.

## Verified Alignment

Latest verified session:

```text
session_20261001_034814/capture_001.csv
```

IMU:

```text
Rows: 2268
Duration: 9.9904 s
Rate: 226.92 Hz
```

Video:

```text
1080 x 1920
59.955 fps
936 frames
15.6117 s
Green light first appears: frame 751, 12.5260 s
```

Telemetry:

```text
Capture elapsed to write completion: 11535 ms
```

Estimated mapping:

```text
Video 0.991 s ~= IMU 0.000 s
Video end before green ~= IMU 9.990 s
```

The estimated pre-roll offset is within about 9 ms of the configured 1-second delay. This validates the light and telemetry alignment method.

## Remaining Notes

- Keep the device visible and focused before pressing Start so the blue-to-red transition is recorded.
- Do not switch cameras during recording.
- Green can be detected even when the device is relatively small, but a larger focused LED target improves automatic detection.
- Do not power the ESP32 from USB and the battery boost output at the same time.

