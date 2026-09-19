# 2026-09-19 Battery and Boost Validation

Power source: protected 3.7 V battery through TP4057, SS-12E07G4 switch, and
TPS61088 fixed 5 V boost.

Trigger source: BOOT button.

All five captures passed the basic data-quality gate.

| File | Action | Rows | Sample rate | Maximum interval | Gaps >= 20 ms | Gyro maximum |
|---|---|---:|---:|---:|---:|---:|
| `static_battery_round01.csv` | Static | 2270 | 226.984 Hz | 5.844 ms | 0 | 16.4 dps |
| `static_battery_round02.csv` | Static | 2269 | 226.896 Hz | 5.844 ms | 0 | 17.6 dps |
| `static_battery_round03.csv` | Static | 2270 | 226.938 Hz | 5.918 ms | 0 | 6.6 dps |
| `small_arm_raise_battery_round01.csv` | Small arm raise | 2269 | 226.930 Hz | 5.913 ms | 0 | 161.5 dps |
| `small_arm_raise_battery_round02.csv` | Small arm raise | 2270 | 226.983 Hz | 5.844 ms | 0 | 173.5 dps |

Static behavior:

```text
gravity magnitude: approximately 992.9-993.0 mg
gravity standard deviation: approximately 2.7-4.8 mg
gyro mean after transient: approximately 1.0 dps
```

The two arm-raise captures show clear motion while remaining within the sensor
ranges and preserving timestamp continuity.

Metadata note: the raw files were exported with the generic capture script, so
sidecar metadata does not yet contain `power_source = battery_boost` or
`trigger_source = boot_button`. The source and action mapping are recorded in
this manifest.
