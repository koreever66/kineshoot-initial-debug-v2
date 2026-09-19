# Hardware Sync - 2026-09-19

## Baseline

```text
hardware_revision: H1
software_revision: F4
interface_revision: I1
ICM-20948 I2C address: 0x68
I2C clock: 50 kHz
WHO_AM_I: 0xEA
```

Current wiring:

```text
ESP32 3V3    -> ICM VCC
ESP32 GND    -> ICM GND
ESP32 GPIO8  -> ICM SDI/SDA
ESP32 GPIO9  -> ICM SCLK/SCL
ICM NCS      -> 3V3
ICM AD0      -> GND
```

## Test Timeline

### USB START and BOOT

Session: `session_20260919_004010`

Both static captures passed. The trigger mapping was confirmed by the operator:

```text
capture_001: START, computer USB
capture_002: BOOT, computer USB
```

| Metric | START | BOOT |
|---|---:|---:|
| Rows | 2270 | 2269 |
| Duration | 9.997 s | 9.998 s |
| Sample rate | 226.967 Hz | 226.856 Hz |
| Maximum interval | 6.315 ms | 5.844 ms |
| Gaps >= 20 ms | 0 | 0 |
| Gravity mean | 1000.278 mg | 1000.121 mg |
| Gravity standard deviation | 3.600 mg | 3.075 mg |
| Gyro mean | 0.953 dps | 0.932 dps |
| Gyro maximum | 4.109 dps | 2.231 dps |
| Temperature drift | 0.910 C | 1.010 C |
| Saturation samples | 0 | 0 |

### Power Bank Empty Captures

Session: `session_20260919_004628`

Three BOOT-triggered captures were exported after power-bank operation. Every
file was exactly 64 bytes and contained only the CSV header. There were no
sample rows, so body motion could not be evaluated.

```text
capture_001.csv: 64 B, 0 data rows, intended static
capture_002.csv: 64 B, 0 data rows, intended arm raise x2
capture_003.csv: 64 B, 0 data rows, intended squat x3
```

The export path was verified. Remote size, downloaded size, and `END_FILE`
checks all succeeded. This was an IMU sampling-path failure, not a truncated
download.

### Recovery Check

The fixed-address I2C diagnostic repeatedly returned:

```text
tx=0 rx=1 who=0xEA
```

This confirms that the ICM-20948 was present at `0x68` and that `WHO_AM_I`
was correct during the recovery check.

### Power Bank Recovery Captures

Session: `session_20260919_010015`

Two static captures on the table passed after F4 was re-uploaded:

| Metric | Round 1 | Round 2 |
|---|---:|---:|
| Rows | 2270 | 2270 |
| Duration | 9.997 s | 9.998 s |
| Sample rate | 226.977 Hz | 226.945 Hz |
| Maximum interval | 5.844 ms | 5.844 ms |
| Gaps >= 20 ms | 0 | 0 |
| Gravity mean | 998.986 mg | 996.792 mg |
| Gravity standard deviation | 6.505 mg | 6.273 mg |
| Gyro mean | 1.608 dps | 1.597 dps |
| Gyro maximum | 68.071 dps | 63.407 dps |
| Temperature drift | 0.950 C | 1.200 C |
| Saturation samples | 0 | 0 |

Both files contain valid data and no sampling gaps. Each file has one short
gyro transient:

```text
round 1: about 0.25-0.62 s, peak 68.071 dps
round 2: about 5.01-5.20 s, peak 63.407 dps
```

These transients are brief and do not cause clipping or timestamp gaps. They
should be excluded when calculating a quiet static baseline, or the captures
should be repeated if a completely quiet ten-second window is required.

## Open Startup Reliability Issue

After switching from the power bank back to computer USB, the operator pressed
RST three times at roughly five-second intervals and the blue idle LED did not
turn on. The fourth RST produced the blue LED.

The valid recovery captures were already recorded before this USB transition,
so the data was not affected. The startup behavior still needs hardware
verification.

Required hardware observations on the next test:

1. Record whether the red LED is on during a failed boot.
2. Record whether COM5 appears before or after the blue LED.
3. Repeat five cold starts: unplug USB, wait 10 s, reconnect, wait 5 s, then
   press RST once and wait up to 10 s.
4. Measure ICM VCC and GND during the first five seconds after connecting USB.
5. Confirm that USB 5V, ESP32 3V3, and the ICM ground do not dip during the
   power-source transition.

Interpretation guide:

```text
red LED remains on: IMU initialization or I2C communication failure
no LED and no COM5: USB enumeration, reset, or power sequencing issue
red then blue after several seconds: startup is slow but eventually succeeds
```

## Hardware Action Items

- Recheck the four-wire quick connector after every power-source change.
- Confirm continuity from NCS to 3V3 and AD0 to GND at the ICM end.
- Confirm that SDA and SCL are not intermittently open while moving the harness.
- Measure VCC and GND at the ICM pins, not only at the ESP32 header.
- Do not continue dynamic testing until one more power-bank static capture
  passes with no empty file.

## Gate for the Next Dynamic Test

The next dynamic run may proceed only when all of the following are true:

```text
CSV rows: approximately 2269
maximum interval: below 10 ms
gaps >= 20 ms: 0
write_failed: 0
clipped acceleration: 0
clipped gyro: 0
```

The startup reliability test should also show at least five consecutive
successful cold starts, or the remaining failure mode must be understood.
