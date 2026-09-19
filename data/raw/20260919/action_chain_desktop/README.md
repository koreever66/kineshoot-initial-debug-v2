# 2026-09-19 Desktop Action-Chain Validation

Power source: power bank

Trigger source: BOOT button

All six captures are approximately 10 seconds long, have no gaps of 20 ms or
more, and contain no acceleration or gyroscope saturation.

| File | Intended action | Source capture | Rows | Sample rate | Gyro maximum |
|---|---|---|---:|---:|---:|
| `static_round01.csv` | Static | `capture_001.csv` | 2269 | 226.878 Hz | 11.782 dps |
| `static_round02.csv` | Static | `capture_002.csv` | 2270 | 226.930 Hz | 8.069 dps |
| `slow_arm_raise_round01.csv` | Slow arm raise | `capture_003.csv` | 2269 | 226.846 Hz | 63.761 dps |
| `simulated_shot_single_round01.csv` | One simulated shot | `capture_004.csv` | 2269 | 226.875 Hz | 235.785 dps |
| `simulated_shot_double_round01.csv` | Two simulated shots | `capture_005.csv` | 2269 | 226.893 Hz | 302.820 dps |
| `squat_double_round01.csv` | Two squats | `capture_006.csv` | 2269 | 226.848 Hz | 52.447 dps |

Video order supplied by the operator:

1. `7cb31795cc729a1089c456609e9c3d67.mp4` - static
2. `1902d3e69c155f6cf32afed13614865b.mp4` - static
3. `b1788e0d256ebe4820d70a055d5fcfdd.mp4` - slow arm raise
4. `393e0ca1e118d2fcbbbf4f450a2fafcb.mp4` - one simulated shot
5. `f22d937e3bb766582befb7c8234dfe25.mp4` - two simulated shots
6. `b60b3481a4d489195b8d3c8d5580fd0c.mp4` - two squats

Important timing note: several actions began earlier than the planned 2-5
second window. Formal phase labels should be aligned to the videos rather than
assuming the original timing plan. The raw generic export metadata marks all
six files as `test_type = simulated_shot`; this manifest is the authoritative
action mapping.
