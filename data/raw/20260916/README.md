# 2026-09-16 Six-Round Stability Test

Hardware:

```text
H1 six-wire direct connection
ESP32-S3 N16R8
ICM-20948
5V USB power bank
```

Software:

```text
F4 imu_flash_logger_v4
10 second capture
RAM buffering
LittleFS write after capture
```

Results:

| File | Rows | Sample rate | Maximum interval | Gaps >= 10ms | Errors | Resets |
|---|---:|---:|---:|---:|---:|---:|
| `stability_run01_round01.csv` | 2269 | 226.846 Hz | 5.908 ms | 0 | 0 | 0 |
| `stability_run01_round02.csv` | 2269 | 226.854 Hz | 5.844 ms | 0 | 0 | 0 |
| `stability_run01_round03.csv` | 2269 | 226.882 Hz | 6.110 ms | 0 | 0 | 0 |
| `stability_run01_round04.csv` | 2269 | 226.877 Hz | 6.350 ms | 0 | 0 | 0 |
| `stability_run01_round05.csv` | 2269 | 226.893 Hz | 5.844 ms | 0 | 0 | 0 |
| `stability_run01_round06.csv` | 2270 | 226.931 Hz | 5.992 ms | 0 | 0 | 0 |

All six captures passed:

- No timestamp gaps above 10 ms.
- No sequence discontinuities.
- No all-zero samples.
- No clipped samples.
- Temperature remained in a narrow range.
- Static gyro magnitude after the first second was about 1.1 dps.

The initial peaks within the first 0.5 seconds match the physical BOOT button press and are excluded from the static stability interpretation.

## Small-Motion Dynamic Test

Three additional 10-second captures used the requested motion sequence:

Power and trigger provenance:

```text
power_source = computer_usb
trigger_source = serial_start
```

These dynamic files are not a battery-powered comparison. They validate the
sampling and export path while powered by the computer.

```text
0-2 s: still
2-5 s: wrist flexion and forearm rotation
5-10 s: still
```

| File | Rows | Sample rate | Maximum interval | Gyro max | Acc magnitude max | Result |
|---|---:|---:|---:|---:|---:|---|
| `dynamic_run01_round01.csv` | 2269 | 226.877 Hz | 6.360 ms | 263.49 dps | 1460.23 mg | Pass |
| `dynamic_run01_round02.csv` | 2269 | 226.854 Hz | 5.902 ms | 356.54 dps | 1534.83 mg | Pass |
| `dynamic_run01_round03.csv` | 2270 | 226.940 Hz | 5.843 ms | 388.66 dps | 1286.24 mg | Pass |

All three captures passed:

- No gaps above 10 ms.
- No sequence discontinuity.
- No reset or communication failure.
- No all-zero segment.
- No fixed saturation.
- No clipping at +/-16g or +/-2000dps.

## Power-Bank + BOOT Validation

Three captures used:

```text
power_source = power_bank
trigger_source = boot_button
```

Files:

```text
powerbank_boot_run01_round01.csv
powerbank_boot_run01_round02.csv
powerbank_boot_run01_round03.csv
```

All three files were saved successfully and contain no communication errors.
However, the requested motion did not occur during the 2-5 second window.
Gyro magnitude remained near 1.1 dps after the BOOT-button transient.

Conclusion:

- Power-bank supply and BOOT-triggered local recording work.
- These files must not be used as dynamic-motion data.

## Power-Bank + BOOT Motion Run 02

Three captures:

| File | Rows | Sample rate | Maximum interval | Gyro max | Acc magnitude max | Result |
|---|---:|---:|---:|---:|---:|---|
| `powerbank_boot_motion_run02_round01.csv` | 2269 | 226.886 Hz | 5.844 ms | 175.98 dps | 1315.89 mg | Pass |
| `powerbank_boot_motion_run02_round02.csv` | 2270 | 226.924 Hz | 6.335 ms | 271.98 dps | 1530.47 mg | Pass |
| `powerbank_boot_motion_run02_round03.csv` | 2269 | 226.888 Hz | 5.844 ms | 466.36 dps | 3270.16 mg | Pass |

Round 2 used a complete upper-body shooting motion. Round 3 used a standing
jump shooting motion. Both returned to the starting posture during the
5-10 second window.

All three files:

- No gaps above 10 ms.
- No sequence discontinuity.
- No reset or communication error.
- No all-zero segment.
- No fixed saturation.
- No clipping at +/-16g or +/-2000dps.

## Static Control Run 02

Five static captures:

| File | Rows | Sample rate | Maximum interval | Gyro after 1 s mean | Gyro after 1 s max | Result |
|---|---:|---:|---:|---:|---:|---|
| `static_control_run02_round01.csv` | 2269 | 226.845 Hz | 5.982 ms | 1.543 dps | 15.054 dps | Pass |
| `static_control_run02_round02.csv` | 2270 | 226.924 Hz | 6.331 ms | 1.422 dps | 10.101 dps | Pass |
| `static_control_run02_round03.csv` | 2270 | 226.934 Hz | 5.844 ms | 1.483 dps | 12.968 dps | Pass |
| `static_control_run02_round04.csv` | 2270 | 226.939 Hz | 5.844 ms | 1.347 dps | 8.260 dps | Pass |
| `static_control_run02_round05.csv` | 2270 | 226.927 Hz | 6.228 ms | 1.227 dps | 4.182 dps | Pass |

All five captures:

- No gaps above 10 ms.
- No sequence discontinuity.
- No reset or communication error.
- No all-zero segment.
- No fixed saturation.
- No clipping at +/-16g or +/-2000dps.
