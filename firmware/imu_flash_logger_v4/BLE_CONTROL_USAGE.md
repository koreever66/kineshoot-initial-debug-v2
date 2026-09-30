# KineShoot BLE Control

The firmware now advertises only the custom control service used by the iPhone app. It no longer advertises a BLE HID keyboard or media remote.

## Device

```text
Name: KineShoot-Cam
Service: 6b1d0001-9a3f-4d2a-8f6f-6b1d00000001
Characteristic: 6b1d0002-9a3f-4d2a-8f6f-6b1d00000002
```

## Commands

```text
0x01 = start IMU capture only
0x02 = reserved for capture plus a phone-side video action
```

The iPhone app writes `0x01` after it starts recording video.

## Expected Serial Output

```text
BLE_CONTROL_READY,name=KineShoot-Cam,...
BLE_CONNECTED
BLE_COMMAND,capture
CAPTURE_START,file=/capture_001.csv,seconds=10
CAPTURE_DONE,...
```

The BOOT button remains available as an offline capture trigger. It no longer sends a phone HID key.
