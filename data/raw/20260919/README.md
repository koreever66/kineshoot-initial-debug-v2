# 2026-09-19 Power-Bank Static Recovery

These two captures were recorded after the F4 firmware was re-uploaded and the
ICM-20948 was confirmed at address `0x68` with `WHO_AM_I = 0xEA`.

Provenance:

```text
hardware: H1
software: F4
interface: I1
power_source: power_bank
trigger_source: boot_button
test_type: static
posture: sensor module placed on table
```

| File | Rows | Sample rate | Maximum interval | Gaps >= 20 ms | Gyro maximum | Result |
|---|---:|---:|---:|---:|---:|---|
| `powerbank_boot_static_recovery_round01.csv` | 2270 | 226.977 Hz | 5.844 ms | 0 | 68.071 dps | Pass with short transient |
| `powerbank_boot_static_recovery_round02.csv` | 2270 | 226.945 Hz | 5.844 ms | 0 | 63.407 dps | Pass with short transient |

Both files contain valid data and no clipping or timestamp gaps. Each file has
one brief gyro transient; see `docs/HARDWARE_SYNC_2026-09-19.md` for details.
