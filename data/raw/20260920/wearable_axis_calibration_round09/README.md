# Sensor Direction Calibration Review

Date: 2026-09-20

Session: `session_20260920_195803`

## Data Quality

All nine captures passed:

```text
3403-3404 rows
approximately 226.9 Hz
maximum interval below 10 ms
no gaps of 20 ms or more
no acceleration or gyroscope saturation
```

## Rotation Test Result

The last three captures were rotations around the defined body axes. The
dominant measured gyro axes were consistent across all three tests:

| Defined rotation | Dominant sensor axis | Pre-5-second signed mean | Peak |
|---|---|---:|---:|
| around body Y | sensor Z | -24.17 dps | 227.32 dps |
| around body X | sensor Y | -19.82 dps | 187.62 dps |
| around body Z | sensor X | +14.72 dps | 205.49 dps |

This gives a consistent fixed mounting permutation:

```text
body X -> sensor -Y
body Y -> sensor -Z
body Z -> sensor +X
```

Using the operator-defined body axes:

```text
body Y: toward the hand
body Z: toward the back of the hand
body X: toward the ulnar direction
```

The sensor-to-body rotation matrix is:

```text
body = R * sensor

R = [ 0  -1   0 ]
    [ 0   0  -1 ]
    [ 1   0   0 ]
```

This matrix has positive determinant and represents a proper fixed mounting
rotation, not an axis inversion or sensor fault.

## First Six Forward-Axis Captures

These six captures are not a traditional six-face gravity calibration. The
operator placed each designated axis approximately forward and horizontal. The
gravity component along the target axis should therefore be near zero, while
the remaining gravity appears on the other axes.

Using the rotation mapping from captures 7-9, the target-axis gravity
components were approximately:

```text
+X: 47.49 mg
-X: 27.07 mg
+Y: 280.90 mg
-Y: 250.05 mg
+Z: 13.57 mg
-Z: 117.51 mg
```

The X and Z forward-axis tests are close to horizontal. The Y axis tests have
approximately 14-16 degrees of tilt, likely from wrist posture, strap angle, or
mounting-plane alignment.

## Calibration State

```text
rotation mapping: verified and usable
forward-axis orientation test: X/Z good, Y-tilt needs confirmation
full six-face gravity calibration: not performed in this session
gyro bias stability: acceptable
strap fixation repeatability: requires one confirmation session
```
