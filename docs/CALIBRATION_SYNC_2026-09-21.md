# Calibration and Wearable Sync - 2026-09-21

## Current Software State

```text
capture duration: 15 seconds
sample rate: approximately 226.9 Hz
expected rows: approximately 3403-3404
LittleFS partition total: 12451840 bytes
```

The F4 firmware now runs from a custom 16 MB partition table with a 4 MB app
partition and an 11.875 MB `spiffs` LittleFS partition.

## Validated Calibration Sessions

### Wearable Axis Calibration

Session: `session_20260920_195803`

```text
9 valid captures
3 static forward-axis groups and 3 controlled rotations
no empty files, gaps, or saturation
```

Confirmed fixed sensor-to-body rotation:

```text
body +X -> sensor -Y
body +Y -> sensor -Z
body +Z -> sensor +X

R = [ 0  -1   0 ]
    [ 0   0  -1 ]
    [ 1   0   0 ]
```

### Forward-Axis Repeatability

Session: `session_20260921_003615`

The second capture was excluded because body heading was approximately 211
degrees while the other captures used approximately 123 degrees.

The table-supported `+Y/-Y` captures were approximately 5-6 degrees from
horizontal. Wall-supported captures were approximately 11-15 degrees from
horizontal and are retained only as comparison data.

### Desktop Six-Face Calibration

Session: `session_20260921_015500`

`capture_001` was discarded by the operator. The remaining 9 captures passed
data-quality checks.

The desktop test independently confirmed the same fixed mounting rotation. The
documented table tilt of approximately 2 degrees toward 324-326 degrees and the
known enclosure-face tilts were retained in the measured residual angles.

## Next Field Capture Rule

At each new shooting session:

1. Keep the same wrist strap position and sensor orientation.
2. Hold the starting posture still for 2 seconds.
3. Define that posture as the local body reference.
4. Record body heading separately if court-relative direction is needed.
5. Use battery power and BOOT-triggered captures.
6. Export with the battery-specific export scripts.

Random court heading does not invalidate the mounting matrix or relative joint
analysis. It only changes the absolute court-heading component.
