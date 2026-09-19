# KineShoot Cross-Conversation Sync - 2026-09-19

## 1. Project Positioning

KineShoot is a portable wearable basketball shooting motion-chain capture and
feedback system.

Current truthful definition:

```text
Use wearable IMU nodes to capture shooting actions at high frequency;
perform data-quality checks, orientation and angular-velocity analysis;
eventually reconstruct joint angles, action phases, and training feedback.
```

Current completed stage:

```text
Single-node trusted capture and action-expression validation.
```

Do not currently claim:

```text
full joint-angle reconstruction
accurate ball release speed
complete AI scoring
sports-science laboratory accuracy
```

## 2. Locked Technical Baseline

```text
hardware_revision = H1
software_revision = F4
interface_revision = I1
ICM-20948 I2C address = 0x68
I2C clock = 50 kHz
WHO_AM_I = 0xEA
sample rate ~226.9 Hz
capture length = 10 s
trigger = BOOT button
```

Current sensor wiring:

```text
ESP32 3V3    -> ICM VCC
ESP32 GND    -> ICM GND
ESP32 GPIO8  -> ICM SDI/SDA
ESP32 GPIO9  -> ICM SCLK/SCL
ICM NCS      -> 3V3
ICM AD0      -> GND
```

The four signal/power lines are soldered and heat-shrunk. Both a 5 V power bank
and the battery/TP4057/SS-12E07G4/TPS61088 power chain have now completed valid
capture testing. Mechanical fixation of the battery power unit remains in
progress.

## 3. Validated Test Data

### Power-Bank Static Recovery

```text
session_20260919_185858
```

Three consecutive static captures passed:

| Capture | Rows | Sample rate | Gaps >= 20 ms | Gravity mean | Gyro max |
|---|---:|---:|---:|---:|---:|
| capture_001 | 2269 | 226.888 Hz | 0 | 995.064 mg | 7.299 dps |
| capture_002 | 2270 | 226.906 Hz | 0 | 994.821 mg | 2.766 dps |
| capture_003 | 2269 | 226.884 Hz | 0 | 994.934 mg | 1.531 dps |

### USB Cable Replacement Check

```text
session_20260919_191246
```

Three consecutive USB captures passed after replacing the USB cable:

| Capture | Rows | Sample rate | Gaps >= 20 ms | no_data_reads |
|---|---:|---:|---:|---:|
| capture_001 | 2270 | 226.974 Hz | 0 | 0 |
| capture_002 | 2269 | 226.920 Hz | 0 | 0 |
| capture_003 | 2270 | 226.975 Hz | 0 | 0 |

One brownout occurred when the USB connector was physically bumped. The board
rebooted normally and later captures passed. This is currently classified as a
mechanical cable disturbance, not a confirmed power-design defect.

### Desktop Action Chain

```text
session_20260919_193451
```

Six consecutive valid action captures:

| File | Action | Rows | Sample rate | Gyro max |
|---|---|---:|---:|---:|
| capture_001 | static | 2269 | 226.878 Hz | 11.782 dps |
| capture_002 | static | 2270 | 226.930 Hz | 8.069 dps |
| capture_003 | slow arm raise | 2269 | 226.846 Hz | 63.761 dps |
| capture_004 | one simulated shot | 2269 | 226.875 Hz | 235.785 dps |
| capture_005 | two simulated shots | 2269 | 226.893 Hz | 302.820 dps |
| capture_006 | two squats | 2269 | 226.848 Hz | 52.447 dps |

All six:

```text
no gaps >= 20 ms
no saturation
stable temperature
approximately 10 seconds
```

Several actions started earlier than the planned 2-5 second window. Formal
phase labels must come from synchronized video, not from the verbal timing plan.

### Battery and Boost Validation

```text
session_20260919_220755
```

Five consecutive captures passed on battery power:

| Capture | Action | Rows | Sample rate | Gaps >= 20 ms | Gyro maximum |
|---|---|---:|---:|---:|---:|
| capture_001 | static | 2270 | 226.984 Hz | 0 | 16.4 dps |
| capture_002 | static | 2269 | 226.896 Hz | 0 | 17.6 dps |
| capture_003 | static | 2270 | 226.938 Hz | 0 | 6.6 dps |
| capture_004 | small arm raise | 2269 | 226.930 Hz | 0 | 161.5 dps |
| capture_005 | small arm raise | 2270 | 226.983 Hz | 0 | 173.5 dps |

The battery and boost path is now electrically validated. The remaining task is
mechanical fixation and strain relief, followed by five repeated captures after
assembly.

## 4. Current Software Capabilities

- high-frequency IMU capture at approximately 226.9 Hz
- RAM buffering and LittleFS batch write
- BOOT-button trigger
- RGB status: blue idle, red capture, green write success
- CSV export and metadata generation
- data-quality checks for gaps, saturation, errors, and resets
- Chinese motion report
- acceleration, angular velocity, gravity-removed acceleration, orientation
- 2D motion-path and force-direction visualization
- on-demand report generation

The zero-sample guard now removes an empty capture file and reports
`no_samples=1` instead of leaving a header-only CSV.

## 5. Hardware Status

Completed:

- ICM-20948 communication at `0x68`
- soldered four-wire connection
- direct hardware initialization and high-rate capture
- static and desktop dynamic validation
- power-bank field-capture path validated
- battery + TP4057 + SS-12E07G4 + TPS61088 electrical validation

In progress:

- strap fixation and sensor enclosure embedding
- strain relief for USB and IMU cables
- battery and boost module mechanical fixation
- forearm pouch layout and cable strain relief

Not yet complete:

- battery-powered field validation after final fixation
- multi-node IMU setup
- elbow angle and relative-joint calculation
- hand/footage synchronization
- ball-speed measurement

## 6. Power Integration Decision

Main scheme:

```text
3.7 V protected battery
-> TP4057 BAT+ / BAT-
-> SS-12E07G4 3 A switch on battery positive
-> TPS61088 fixed 5 V boost
-> ESP32 5V and GND
```

Fallback scheme:

```text
battery -> P-MOSFET high-side switch -> SS12D07VG4 low-current control
-> TPS61088 -> ESP32
```

`SS12D07VG4` is around 0.5 A and must not carry the main boost input current.
TP4057 has no load sharing. Charging and ESP32 load must not operate at the
same time. USB 5 V and battery boost 5 V must never be connected simultaneously.

## 7. Recommended Project/PPT Message

Problem:

```text
Basketball training records whether shots go in, but not why a shot is stable
or inconsistent. Professional motion capture is expensive and not portable.
```

Solution:

```text
KineShoot uses wearable IMU nodes to capture the full shooting motion chain,
extract physical motion metrics, and eventually provide explainable training
feedback.
```

Current evidence:

```text
We have stable 10-second, approximately 227 Hz single-node data with no gaps,
including static, arm-raise, simulated-shot, and squat actions.
```

Next milestone:

```text
Complete wearable fixation and battery power, then add a second IMU for elbow
angle and relative joint motion.
```

Final goal:

```text
Multi-node motion-chain analysis and a personalized feedback loop from data
collection to training recommendation.
```

## 8. GitHub State

Software repository:

```text
repository: koreever66/kineshoot-initial-debug-v2
branch: codex/software-data
status: includes the latest battery and boost validation sync
```

Hardware repository:

```text
repository: koreever66/kineshoot-initial-debug-v1
branch: codex/hardware-bringup
status: includes the latest battery and boost validation record
```

Offline bundles:

```text
outputs/kineshoot-initial-debug-v2-software-sync-20260919.bundle
outputs/kineshoot-hardware-sync-20260919.bundle
```
