# Hardware Sync - 2026-09-19 Action-Chain Validation

## Current Hardware State

```text
ESP32-S3
ICM-20948 at I2C 0x68
NCS -> 3V3
AD0 -> GND
4 soldered signal/power wires with direct short connections
5 V power bank for field capture
BOOT button for capture trigger
```

The latest USB-cable replacement produced three valid USB captures. The power
bank path separately produced three valid static captures and six valid
desktop action-chain captures.

## Stable Data Evidence

The six desktop action-chain files are stored under:

```text
data/raw/20260919/action_chain_desktop/
```

All six captures have approximately 2269 rows, approximately 226.9 Hz sample
rate, no gaps of 20 ms or more, and no saturation.

The current valid action set is:

```text
static x2
slow arm raise x1
one simulated shot x1
two simulated shots x1
two squats x1
```

## External USB Finding

The prior USB instability is consistent with the USB cable/path, not the
current soldered ICM wiring:

```text
old cable/path: retries, I2C read timeouts, partial or zero-sample captures
new cable: 3/3 valid USB captures
power bank: valid static and action-chain captures
```

One startup brownout occurred when the USB connector was physically bumped.
The board rebooted and then operated normally. This is currently classified as
a mechanical cable/port disturbance, not a confirmed power-design defect.

## Mechanical Fixation Requirements

Before the next field test:

- Keep the four-wire ICM connection and soldered joints unchanged.
- Add a cable strain-relief loop so USB and battery movement cannot pull on the
  ESP32 or ICM connectors.
- Anchor the power bank and ESP32 separately from the sensor-module strap.
- Do not place adhesive or hot-melt directly on exposed solder joints.
- Keep the RGB LED and BOOT button accessible.
- Keep the USB-C port accessible for firmware and export operations.
- Avoid sharp bends at the heat-shrink exits.
- Mark the sensor mounting direction so repeated tests use the same orientation.
- Check NCS-to-3V3 and AD0-to-GND continuity after the enclosure is assembled.

## Validation Gate After Fixation

After strap and enclosure assembly, run three static captures and two simple
arm-raise captures. The gate is:

```text
3/3 static captures valid
2/2 arm-raise captures valid
no empty or partial files
no gaps of 20 ms or more
no saturation
no repeated USB startup retries
```

Only after this gate should the system move to court testing with real shots.
