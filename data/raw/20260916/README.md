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
