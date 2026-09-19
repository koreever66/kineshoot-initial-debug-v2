# encoding: utf-8
"""Build a standalone 2D motion report from one or more IMU CSV captures."""

import argparse
import csv
import html
import json
import math
import os
import statistics
import webbrowser
from pathlib import Path


GRAVITY_MG = 1000.0
DEFAULT_GAP_MS = 20.0
DEFAULT_ACC_LIMIT_MG = 16000.0
DEFAULT_GYRO_LIMIT_DPS = 2000.0
HIGHPASS_SECONDS = 0.55
ORIENTATION_CORRECTION_GAIN = 0.035


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a 2D trajectory and motion-curve HTML report."
    )
    parser.add_argument("csv_file", nargs="?", help="Input capture CSV")
    parser.add_argument(
        "--latest",
        help="Process every capture in the newest session directory under this root",
    )
    parser.add_argument("--meta", help="Optional capture metadata JSON")
    parser.add_argument("--output", help="Output HTML path")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the first generated report in the default browser",
    )
    parser.add_argument(
        "--gap-ms",
        type=float,
        default=DEFAULT_GAP_MS,
        help="Minimum timestamp gap considered a data gap",
    )
    parser.add_argument(
        "--acc-limit-mg",
        type=float,
        default=DEFAULT_ACC_LIMIT_MG,
        help="Acceleration component magnitude considered clipped",
    )
    parser.add_argument(
        "--gyro-limit-dps",
        type=float,
        default=DEFAULT_GYRO_LIMIT_DPS,
        help="Angular velocity component magnitude considered clipped",
    )
    return parser.parse_args()


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(fraction * (len(ordered) - 1))
    return ordered[index]


def vector_norm(vector):
    return math.sqrt(sum(value * value for value in vector))


def vector_normalize(vector):
    magnitude = vector_norm(vector)
    if magnitude <= 1e-12:
        return [0.0, 0.0, 1.0]
    return [value / magnitude for value in vector]


def vector_cross(left, right):
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


def quaternion_multiply(left, right):
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return [
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ]


def quaternion_normalize(quaternion):
    magnitude = vector_norm(quaternion)
    if magnitude <= 1e-12:
        return [1.0, 0.0, 0.0, 0.0]
    return [value / magnitude for value in quaternion]


def quaternion_conjugate(quaternion):
    return [quaternion[0], -quaternion[1], -quaternion[2], -quaternion[3]]


def quaternion_from_axis_angle(axis, angle_radians):
    normalized = vector_normalize(axis)
    half_angle = angle_radians * 0.5
    scale = math.sin(half_angle)
    return [
        math.cos(half_angle),
        normalized[0] * scale,
        normalized[1] * scale,
        normalized[2] * scale,
    ]


def quaternion_from_two_vectors(source, target):
    source = vector_normalize(source)
    target = vector_normalize(target)
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(source, target))))
    if dot > 0.999999:
        return [1.0, 0.0, 0.0, 0.0]
    if dot < -0.999999:
        axis = vector_cross(source, [1.0, 0.0, 0.0])
        if vector_norm(axis) < 1e-6:
            axis = vector_cross(source, [0.0, 1.0, 0.0])
        return quaternion_from_axis_angle(axis, math.pi)

    cross = vector_cross(source, target)
    return quaternion_normalize([1.0 + dot, cross[0], cross[1], cross[2]])


def quaternion_rotate(quaternion, vector):
    pure = [0.0, vector[0], vector[1], vector[2]]
    rotated = quaternion_multiply(
        quaternion_multiply(quaternion, pure),
        quaternion_conjugate(quaternion),
    )
    return rotated[1:]


def apply_small_quaternion_correction(quaternion, correction, gain):
    blended = [
        1.0 + gain * (correction[0] - 1.0),
        gain * correction[1],
        gain * correction[2],
        gain * correction[3],
    ]
    return quaternion_normalize(quaternion_multiply(quaternion, blended))


def quaternion_to_euler(quaternion):
    w, x, y, z = quaternion
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch_term = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(pitch_term)
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]


def quaternion_from_euler_degrees(roll_deg, pitch_deg, yaw_deg):
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    half_roll = roll * 0.5
    half_pitch = pitch * 0.5
    half_yaw = yaw * 0.5
    cr = math.cos(half_roll)
    sr = math.sin(half_roll)
    cp = math.cos(half_pitch)
    sp = math.sin(half_pitch)
    cy = math.cos(half_yaw)
    sy = math.sin(half_yaw)
    return [
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ]


def centered_moving_average(values, radius):
    count = len(values)
    if count == 0:
        return []
    radius = max(0, int(radius))
    prefix = [0.0]
    for value in values:
        prefix.append(prefix[-1] + value)

    output = []
    for index in range(count):
        start = max(0, index - radius)
        end = min(count, index + radius + 1)
        output.append((prefix[end] - prefix[start]) / (end - start))
    return output


def highpass(values, seconds, sample_rate_hz):
    radius = max(1, int(seconds * sample_rate_hz * 0.5))
    baseline = centered_moving_average(values, radius)
    return [value - baseline[index] for index, value in enumerate(values)]


def integrate(values, delta_times):
    output = [0.0]
    for index in range(1, len(values)):
        output.append(
            output[-1]
            + 0.5 * (values[index] + values[index - 1]) * delta_times[index]
        )
    return output


def anchor_endpoint(values, time_s):
    if not values or len(values) != len(time_s):
        return values
    duration = time_s[-1] if time_s else 0.0
    if duration <= 0.0:
        return values
    endpoint = values[-1]
    return [
        value - endpoint * (time_s[index] / duration)
        for index, value in enumerate(values)
    ]


def load_csv(csv_file):
    with open(csv_file, "r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise SystemExit(f"CSV has no data rows: {csv_file}")

    if "timestamp_us" in rows[0]:
        timestamps = [int(row["timestamp_us"]) for row in rows]
    elif "timestamp_ms" in rows[0]:
        timestamps = [int(row["timestamp_ms"]) * 1000 for row in rows]
    else:
        raise SystemExit("CSV is missing timestamp_us or timestamp_ms.")

    required = [
        "ax_mg",
        "ay_mg",
        "az_mg",
        "gx_dps",
        "gy_dps",
        "gz_dps",
    ]
    for key in required:
        if key not in rows[0]:
            raise SystemExit(f"CSV is missing required column: {key}")
    return rows, timestamps


def load_metadata(csv_file, explicit_meta):
    candidates = []
    if explicit_meta:
        candidates.append(Path(explicit_meta))
    candidates.append(Path(csv_file).with_suffix(".meta.json"))

    for candidate in candidates:
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as stream:
                return json.load(stream)
    return {}


def estimate_orientation(accel_mg, gyro_dps, time_s, sample_rate_hz):
    gravity_samples = max(1, int(sample_rate_hz * 0.15))
    initial_gravity = [
        statistics.fmean(accel_mg[index][axis] for index in range(min(gravity_samples, len(accel_mg))))
        for axis in range(3)
    ]
    initial_acceleration = vector_normalize(initial_gravity)
    initial_roll = math.degrees(
        math.atan2(initial_acceleration[1], initial_acceleration[2])
    )
    initial_pitch = math.degrees(
        math.atan2(
            -initial_acceleration[0],
            math.hypot(initial_acceleration[1], initial_acceleration[2]),
        )
    )
    quaternion = quaternion_from_euler_degrees(
        initial_roll, initial_pitch, 0.0
    )
    orientations = []

    for index in range(len(time_s)):
        if index:
            delta_t = max(1e-6, time_s[index] - time_s[index - 1])
            omega = [
                math.radians(
                    0.5 * (gyro_dps[index][axis] + gyro_dps[index - 1][axis])
                )
                for axis in range(3)
            ]
            magnitude = vector_norm(omega)
            if magnitude > 1e-9:
                delta = quaternion_from_axis_angle(omega, magnitude * delta_t)
                quaternion = quaternion_normalize(
                    quaternion_multiply(quaternion, delta)
                )

        acceleration = accel_mg[index]
        acceleration_norm = vector_norm(acceleration)
        if 650.0 <= acceleration_norm <= 1450.0:
            observed_up_body = vector_normalize(acceleration)
            predicted_up_body = quaternion_rotate(
                quaternion_conjugate(quaternion), [0.0, 0.0, 1.0]
            )
            correction = quaternion_from_two_vectors(
                predicted_up_body, observed_up_body
            )
            quaternion = apply_small_quaternion_correction(
                quaternion, correction, ORIENTATION_CORRECTION_GAIN
            )

        orientations.append(quaternion)
    return orientations


def derive_motion(rows, timestamps_us):
    time_s = [(value - timestamps_us[0]) / 1_000_000.0 for value in timestamps_us]
    duration_s = time_s[-1] if time_s else 0.0
    sample_rate_hz = (
        (len(time_s) - 1) / duration_s if duration_s > 0.0 else 0.0
    )
    delta_times = [0.0]
    for index in range(1, len(time_s)):
        delta_times.append(max(1e-6, time_s[index] - time_s[index - 1]))

    accel_mg = [
        [
            float(row["ax_mg"]),
            float(row["ay_mg"]),
            float(row["az_mg"]),
        ]
        for row in rows
    ]
    gyro_dps = [
        [
            float(row["gx_dps"]),
            float(row["gy_dps"]),
            float(row["gz_dps"]),
        ]
        for row in rows
    ]
    temperature_c = [float(row.get("temp_c", 0.0)) for row in rows]
    orientations = estimate_orientation(
        accel_mg, gyro_dps, time_s, sample_rate_hz
    )

    linear_world_mg = []
    euler_deg = []
    for index, quaternion in enumerate(orientations):
        acceleration_g = [value / GRAVITY_MG for value in accel_mg[index]]
        world_acceleration = quaternion_rotate(quaternion, acceleration_g)
        linear_world_mg.append(
            [
                (world_acceleration[0]) * GRAVITY_MG,
                (world_acceleration[1]) * GRAVITY_MG,
                (world_acceleration[2] - 1.0) * GRAVITY_MG,
            ]
        )
        euler_deg.append(quaternion_to_euler(quaternion))

    horizontal_x = [value[0] for value in linear_world_mg]
    horizontal_y = [value[1] for value in linear_world_mg]
    filtered_x = highpass(horizontal_x, HIGHPASS_SECONDS, sample_rate_hz)
    filtered_y = highpass(horizontal_y, HIGHPASS_SECONDS, sample_rate_hz)

    velocity_x = integrate(filtered_x, delta_times)
    velocity_y = integrate(filtered_y, delta_times)
    velocity_x = anchor_endpoint(velocity_x, time_s)
    velocity_y = anchor_endpoint(velocity_y, time_s)

    position_x = integrate(velocity_x, delta_times)
    position_y = integrate(velocity_y, delta_times)
    position_x = anchor_endpoint(position_x, time_s)
    position_y = anchor_endpoint(position_y, time_s)

    speed_m_s = [
        math.hypot(velocity_x[index], velocity_y[index])
        for index in range(len(time_s))
    ]
    path_length_m = sum(
        math.hypot(
            position_x[index] - position_x[index - 1],
            position_y[index] - position_y[index - 1],
        )
        for index in range(1, len(time_s))
    )
    min_x = min(position_x) if position_x else 0.0
    max_x = max(position_x) if position_x else 0.0
    min_y = min(position_y) if position_y else 0.0
    max_y = max(position_y) if position_y else 0.0
    path_span_m = max(max_x - min_x, max_y - min_y)
    schematic_scale = 100.0 / path_span_m if path_span_m > 1e-9 else 0.0
    position_schematic = [
        [
            (position_x[index] - position_x[0]) * schematic_scale,
            (position_y[index] - position_y[0]) * schematic_scale,
        ]
        for index in range(len(time_s))
    ]
    return {
        "time_s": time_s,
        "delta_times": delta_times,
        "sample_rate_hz": sample_rate_hz,
        "accel_mg": accel_mg,
        "gyro_dps": gyro_dps,
        "temperature_c": temperature_c,
        "linear_world_mg": linear_world_mg,
        "euler_deg": euler_deg,
        "position_m": [
            [position_x[index], position_y[index]]
            for index in range(len(time_s))
        ],
        "velocity_m_s": [
            [velocity_x[index], velocity_y[index]]
            for index in range(len(time_s))
        ],
        "speed_m_s": speed_m_s,
        "path_length_m": path_length_m,
        "position_schematic": position_schematic,
        "path_length_schematic": path_length_m * schematic_scale,
        "speed_schematic": [
            value * schematic_scale for value in speed_m_s
        ],
    }


def quality_metrics(rows, timestamps_us, derived, args):
    intervals_ms = [
        (timestamps_us[index] - timestamps_us[index - 1]) / 1000.0
        for index in range(1, len(timestamps_us))
    ]
    median_interval_ms = statistics.median(intervals_ms) if intervals_ms else 0.0
    gap_threshold_ms = max(args.gap_ms, median_interval_ms * 4.0)
    gap_count = sum(
        interval >= gap_threshold_ms for interval in intervals_ms
    )

    accel_magnitudes = [
        vector_norm(value) for value in derived["accel_mg"]
    ]
    gyro_magnitudes = [
        vector_norm(value) for value in derived["gyro_dps"]
    ]
    clipped_acc = sum(
        max(abs(component) for component in value) >= args.acc_limit_mg
        for value in derived["accel_mg"]
    )
    clipped_gyro = sum(
        max(abs(component) for component in value) >= args.gyro_limit_dps
        for value in derived["gyro_dps"]
    )
    max_linear_acceleration = max(
        vector_norm(value) for value in derived["linear_world_mg"]
    )
    max_speed_m_s = max(derived["speed_m_s"]) if derived["speed_m_s"] else 0.0
    return {
        "rows": len(rows),
        "duration_s": derived["time_s"][-1] if derived["time_s"] else 0.0,
        "sample_rate_hz": derived["sample_rate_hz"],
        "median_interval_ms": median_interval_ms,
        "p95_interval_ms": percentile(intervals_ms, 0.95),
        "max_interval_ms": max(intervals_ms) if intervals_ms else 0.0,
        "gap_threshold_ms": gap_threshold_ms,
        "gap_count": gap_count,
        "clipped_acc_samples": clipped_acc,
        "clipped_gyro_samples": clipped_gyro,
        "gravity_magnitude_mean_mg": statistics.fmean(accel_magnitudes),
        "gravity_magnitude_stdev_mg": statistics.pstdev(accel_magnitudes),
        "accel_peak_mg": max(accel_magnitudes),
        "gyro_peak_dps": max(gyro_magnitudes),
        "linear_accel_peak_mg": max_linear_acceleration,
        "max_speed_m_s": max_speed_m_s,
        "temperature_min_c": min(derived["temperature_c"]),
        "temperature_max_c": max(derived["temperature_c"]),
        "path_length_m": derived["path_length_m"],
        "path_length_units": derived["path_length_schematic"],
    }


def rounded(values, digits=4):
    return [round(float(value), digits) for value in values]


def report_payload(csv_file, metadata, derived, metrics):
    position_units = [
        [round(value[0], 4), round(value[1], 4)]
        for value in derived["position_schematic"]
    ]
    return {
        "title": Path(csv_file).stem,
        "file": os.path.basename(csv_file),
        "metadata": metadata,
        "metrics": metrics,
        "time": rounded(derived["time_s"], 5),
        "accel": {
            "x": rounded([value[0] for value in derived["accel_mg"]], 2),
            "y": rounded([value[1] for value in derived["accel_mg"]], 2),
            "z": rounded([value[2] for value in derived["accel_mg"]], 2),
        },
        "gyro": {
            "x": rounded([value[0] for value in derived["gyro_dps"]], 2),
            "y": rounded([value[1] for value in derived["gyro_dps"]], 2),
            "z": rounded([value[2] for value in derived["gyro_dps"]], 2),
        },
        "linear": {
            "x": rounded([value[0] for value in derived["linear_world_mg"]], 2),
            "y": rounded([value[1] for value in derived["linear_world_mg"]], 2),
            "z": rounded([value[2] for value in derived["linear_world_mg"]], 2),
        },
        "orientation": {
            "roll": rounded([value[0] for value in derived["euler_deg"]], 2),
            "pitch": rounded([value[1] for value in derived["euler_deg"]], 2),
            "yaw": rounded([value[2] for value in derived["euler_deg"]], 2),
        },
        "position_units": position_units,
        "speed_cm_s": rounded(
            [value * 100.0 for value in derived["speed_m_s"]], 2
        ),
        "speed_units_s": rounded(derived["speed_schematic"], 2),
    }


def write_derived_csv(path, derived):
    with open(path, "w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "index",
                "time_s",
                "ax_mg",
                "ay_mg",
                "az_mg",
                "gx_dps",
                "gy_dps",
                "gz_dps",
                "linear_x_mg",
                "linear_y_mg",
                "linear_z_mg",
                "vx_m_s",
                "vy_m_s",
                "px_m",
                "py_m",
                "px_u",
                "py_u",
                "speed_u_s",
                "roll_deg",
                "pitch_deg",
                "yaw_deg",
            ]
        )
        for index, time_value in enumerate(derived["time_s"]):
            writer.writerow(
                [
                    index,
                    f"{time_value:.6f}",
                    *[f"{value:.3f}" for value in derived["accel_mg"][index]],
                    *[f"{value:.3f}" for value in derived["gyro_dps"][index]],
                    *[
                        f"{value:.3f}"
                        for value in derived["linear_world_mg"][index]
                    ],
                    f"{derived['velocity_m_s'][index][0]:.6f}",
                    f"{derived['velocity_m_s'][index][1]:.6f}",
                    f"{derived['position_m'][index][0]:.6f}",
                    f"{derived['position_m'][index][1]:.6f}",
                    f"{derived['position_schematic'][index][0]:.3f}",
                    f"{derived['position_schematic'][index][1]:.3f}",
                    f"{derived['speed_schematic'][index]:.3f}",
                    *[f"{value:.3f}" for value in derived["euler_deg"][index]],
                ]
            )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ - 动作报告</title>
<style>
:root {
  --bg: #eef3f6;
  --surface: #ffffff;
  --surface-alt: #f7fafb;
  --ink: #17232d;
  --muted: #607180;
  --line: #d5e0e6;
  --blue: #2e6fd6;
  --green: #0b8f72;
  --orange: #d77b25;
  --red: #c94b55;
  --violet: #7656c9;
}
* { box-sizing: border-box; }
html, body { margin: 0; min-height: 100%; }
body {
  background: var(--bg);
  color: var(--ink);
  font: 14px/1.4 "Segoe UI", Arial, sans-serif;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 22px;
  background: #ffffff;
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  z-index: 10;
}
.title-block h1 { margin: 0; font-size: 20px; letter-spacing: 0; }
.title-block p { margin: 3px 0 0; color: var(--muted); }
.quality-strip {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  min-width: 0;
}
.quality-item {
  min-width: 116px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: var(--surface-alt);
}
.quality-item span { display: block; color: var(--muted); font-size: 11px; }
.quality-item strong { display: block; margin-top: 2px; font-size: 15px; }
main { max-width: 1520px; margin: 0 auto; padding: 18px 18px 100px; }
.notice {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-left: 4px solid var(--orange);
  background: #fff8ef;
  color: #68421f;
}
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  margin: 0 0 14px;
  color: var(--muted);
}
.meta-row b { color: var(--ink); font-weight: 600; }
.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.panel {
  min-width: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding: 11px 13px 8px;
  border-bottom: 1px solid #edf2f4;
}
.panel-head h2 { margin: 0; font-size: 15px; letter-spacing: 0; }
.panel-head span { color: var(--muted); font-size: 12px; }
.canvas-wrap { position: relative; height: 255px; padding: 4px 6px 6px; }
.canvas-wrap { min-width: 0; }
.trajectory-panel { margin-top: 14px; }
.trajectory-panel .canvas-wrap { height: min(62vh, 650px); min-height: 390px; }
canvas { display: block; width: 100%; height: 100%; }
.timeline {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  display: grid;
  grid-template-columns: auto auto minmax(160px, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 10px 18px;
  border-top: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(8px);
}
button, select {
  height: 34px;
  border: 1px solid #bfccd4;
  border-radius: 6px;
  background: #ffffff;
  color: var(--ink);
  font: inherit;
}
button { min-width: 76px; cursor: pointer; }
button:hover { border-color: #7f919e; }
select { padding: 0 7px; }
input[type="range"] { width: 100%; accent-color: var(--blue); }
.time-readout { min-width: 172px; text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; }
.time-readout b { color: var(--ink); }
@media (max-width: 900px) {
  .topbar { position: static; align-items: flex-start; flex-direction: column; }
  .quality-strip { justify-content: flex-start; }
  .chart-grid { grid-template-columns: 1fr; }
  .timeline { grid-template-columns: auto auto 1fr; }
  .time-readout { grid-column: 1 / -1; text-align: left; }
}
@media (max-width: 520px) {
  .topbar { padding: 14px; }
  .quality-strip {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }
  .quality-item { min-width: 0; }
  main { padding: 14px 10px 96px; }
  .timeline {
    grid-template-columns: auto auto minmax(0, 1fr);
    padding: 9px 10px;
    gap: 8px;
    width: 100vw;
  }
  button { min-width: 68px; }
  html, body { overflow-x: hidden; }
}
</style>
</head>
<body>
<header class="topbar">
  <div class="title-block">
    <h1 id="reportTitle"></h1>
    <p id="reportFile"></p>
  </div>
  <div class="quality-strip" id="qualityStrip"></div>
</header>
<main>
  <div class="notice">
    传感器轨迹与力方向均由单个 IMU 估算，仅用于观察动作形状。轨迹坐标采用归一化示意单位，不代表经过标定的厘米级真实位移。
  </div>
  <div class="meta-row" id="metaRow"></div>
  <section class="chart-grid">
    <article class="panel">
      <div class="panel-head"><h2>加速度</h2><span>mg</span></div>
      <div class="canvas-wrap"><canvas id="accelChart"></canvas></div>
    </article>
    <article class="panel">
      <div class="panel-head"><h2>角速度</h2><span>°/s</span></div>
      <div class="canvas-wrap"><canvas id="gyroChart"></canvas></div>
    </article>
    <article class="panel">
      <div class="panel-head"><h2>去重力线性加速度</h2><span>mg，世界坐标系</span></div>
      <div class="canvas-wrap"><canvas id="linearChart"></canvas></div>
    </article>
    <article class="panel">
      <div class="panel-head"><h2>姿态角</h2><span>°，相对初始朝向</span></div>
      <div class="canvas-wrap"><canvas id="orientationChart"></canvas></div>
    </article>
  </section>
  <section class="panel trajectory-panel">
    <div class="panel-head"><h2>二维运动轨迹与力的方向</h2><span>示意单位；绿色为起点，红色为终点</span></div>
    <div class="canvas-wrap"><canvas id="trajectoryChart"></canvas></div>
  </section>
</main>
<footer class="timeline">
  <button id="playButton" type="button">播放</button>
  <select id="speedSelect" aria-label="播放速度">
    <option value="0.25">0.25x</option>
    <option value="0.5">0.5x</option>
    <option value="1" selected>1x</option>
    <option value="2">2x</option>
  </select>
  <input id="timeSlider" type="range" min="0" max="1000" value="0">
  <div class="time-readout" id="timeReadout"></div>
</footer>
<script>
const REPORT = __REPORT__;
const seriesDefinitions = {
  accelChart: [
    { key: "x", label: "AX", color: "#2e6fd6", data: REPORT.accel.x },
    { key: "y", label: "AY", color: "#0b8f72", data: REPORT.accel.y },
    { key: "z", label: "AZ", color: "#d77b25", data: REPORT.accel.z }
  ],
  gyroChart: [
    { key: "x", label: "GX", color: "#2e6fd6", data: REPORT.gyro.x },
    { key: "y", label: "GY", color: "#0b8f72", data: REPORT.gyro.y },
    { key: "z", label: "GZ", color: "#d77b25", data: REPORT.gyro.z }
  ],
  linearChart: [
    { key: "x", label: "LX", color: "#2e6fd6", data: REPORT.linear.x },
    { key: "y", label: "LY", color: "#0b8f72", data: REPORT.linear.y },
    { key: "z", label: "LZ", color: "#d77b25", data: REPORT.linear.z }
  ],
  orientationChart: [
    { key: "roll", label: "横滚", color: "#2e6fd6", data: REPORT.orientation.roll },
    { key: "pitch", label: "俯仰", color: "#0b8f72", data: REPORT.orientation.pitch },
    { key: "yaw", label: "偏航", color: "#7656c9", data: REPORT.orientation.yaw }
  ]
};
const charts = Object.keys(seriesDefinitions).map(id => ({
  id,
  canvas: document.getElementById(id),
  series: seriesDefinitions[id]
}));
const trajectoryCanvas = document.getElementById("trajectoryChart");
const playButton = document.getElementById("playButton");
const speedSelect = document.getElementById("speedSelect");
const timeSlider = document.getElementById("timeSlider");
const timeReadout = document.getElementById("timeReadout");
let state = { index: 0, playing: false, lastFrame: 0 };
let chartLayouts = {};
let trajectoryLayout = null;

function sampleIndex() {
  return Math.max(0, Math.min(REPORT.time.length - 1, Math.round(state.index)));
}

function formatMetric(value, decimals = 2) {
  return Number(value).toFixed(decimals);
}

function metadataValue(value) {
  if (value === null || value === undefined || value === "") return "未记录";
  const labels = {
    power_bank: "充电宝",
    computer_usb: "电脑 USB",
    usb_computer: "电脑 USB",
    boot_button: "BOOT 按键",
    serial_start: "串口 START 命令",
    simulated_shot: "模拟投篮",
    small_motion: "小幅动作",
    static: "静止",
    unspecified: "未指定",
    bench_handheld: "手持，桌面基准"
  };
  return labels[String(value)] || String(value).replaceAll("_", " ");
}

function buildHeader() {
  document.getElementById("reportTitle").textContent = `${REPORT.title} · 动作报告`;
  document.getElementById("reportFile").textContent = REPORT.file;
  const metrics = [
    ["采集时长", `${formatMetric(REPORT.metrics.duration_s, 3)} 秒`],
    ["采样率", `${formatMetric(REPORT.metrics.sample_rate_hz)} Hz`],
    ["采样缺口", `${REPORT.metrics.gap_count}`],
    ["陀螺仪峰值", `${formatMetric(REPORT.metrics.gyro_peak_dps, 1)} dps`],
    ["线性加速度峰值", `${formatMetric(REPORT.metrics.linear_accel_peak_mg, 0)} mg`],
    ["轨迹长度", `${formatMetric(REPORT.metrics.path_length_units, 0)} 单位`]
  ];
  const strip = document.getElementById("qualityStrip");
  for (const [label, value] of metrics) {
    const item = document.createElement("div");
    item.className = "quality-item";
    item.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    strip.appendChild(item);
  }
  const meta = REPORT.metadata || {};
  const rows = [
    ["供电", metadataValue(meta.power_source)],
    ["触发方式", metadataValue(meta.trigger_source)],
    ["测试类型", metadataValue(meta.test_type)],
    ["安装方式", metadataValue(meta.mount_position)],
    ["温度", `${formatMetric(REPORT.metrics.temperature_min_c, 1)} 至 ${formatMetric(REPORT.metrics.temperature_max_c, 1)} °C`],
    ["重力模长", `${formatMetric(REPORT.metrics.gravity_magnitude_mean_mg, 1)} mg`]
  ];
  document.getElementById("metaRow").innerHTML = rows
    .map(([label, value]) => `<span>${label}: <b>${value}</b></span>`)
    .join("");
}

function setupCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.floor(rect.width * dpr));
  const height = Math.max(1, Math.floor(rect.height * dpr));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d");
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { context, width: rect.width, height: rect.height };
}

function niceTicks(minValue, maxValue, count = 5) {
  const range = maxValue - minValue || 1;
  const rough = range / count;
  const power = Math.pow(10, Math.floor(Math.log10(rough)));
  const fraction = rough / power;
  const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  const step = niceFraction * power;
  const start = Math.ceil(minValue / step) * step;
  const ticks = [];
  for (let value = start; value <= maxValue + step * 0.25; value += step) {
    ticks.push(value);
  }
  return ticks;
}

function arrayMin(values) {
  let result = Infinity;
  for (const value of values) {
    if (value < result) result = value;
  }
  return result;
}

function arrayMax(values) {
  let result = -Infinity;
  for (const value of values) {
    if (value > result) result = value;
  }
  return result;
}

function drawChart(chart) {
  const { context, width, height } = setupCanvas(chart.canvas);
  context.clearRect(0, 0, width, height);
  const padding = { left: 52, right: 12, top: 28, bottom: 28 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const allValues = chart.series.flatMap(item => item.data);
  let minValue = arrayMin(allValues);
  let maxValue = arrayMax(allValues);
  if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
    minValue = -1; maxValue = 1;
  }
  const valuePadding = Math.max(1, (maxValue - minValue) * 0.08);
  minValue -= valuePadding;
  maxValue += valuePadding;
  const xMax = REPORT.time.at(-1) || 1;

  const xFor = value => padding.left + value / xMax * plotWidth;
  const yFor = value => padding.top + (maxValue - value) / (maxValue - minValue) * plotHeight;
  context.font = "12px Segoe UI, Arial";
  context.lineWidth = 1;
  context.strokeStyle = "#e5edf1";
  context.fillStyle = "#667784";
  context.textAlign = "right";
  for (const tick of niceTicks(minValue, maxValue, 5)) {
    const y = yFor(tick);
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
    context.fillText(tick.toFixed(Math.abs(tick) < 10 ? 1 : 0), padding.left - 7, y + 4);
  }
  context.textAlign = "center";
  for (let index = 0; index <= 5; index++) {
    const timeValue = xMax * index / 5;
    const x = xFor(timeValue);
    context.beginPath();
    context.moveTo(x, padding.top);
    context.lineTo(x, height - padding.bottom);
    context.stroke();
    context.fillText(`${timeValue.toFixed(1)}s`, x, height - 8);
  }
  context.save();
  context.beginPath();
  context.rect(padding.left, padding.top, plotWidth, plotHeight);
  context.clip();
  for (const item of chart.series) {
    context.beginPath();
    context.strokeStyle = item.color;
    context.lineWidth = 1.55;
    for (let index = 0; index < item.data.length; index += 1) {
      const x = xFor(REPORT.time[index]);
      const y = yFor(item.data[index]);
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    }
    context.stroke();
  }
  context.restore();

  const currentX = xFor(REPORT.time[sampleIndex()]);
  context.strokeStyle = "#17232d";
  context.lineWidth = 1;
  context.beginPath();
  context.moveTo(currentX, padding.top);
  context.lineTo(currentX, height - padding.bottom);
  context.stroke();

  let legendX = padding.left;
  context.textAlign = "left";
  for (const item of chart.series) {
    context.fillStyle = item.color;
    context.fillRect(legendX, 9, 14, 3);
    context.fillStyle = "#435563";
    context.fillText(item.label, legendX + 18, 13);
    legendX += 62;
  }
  chartLayouts[chart.id] = { padding, plotWidth, plotHeight, xMax };
}

function trajectoryColor(fraction) {
  const stops = [
    [46, 111, 214],
    [11, 143, 114],
    [215, 123, 37],
    [201, 75, 85],
    [118, 86, 201]
  ];
  const scaled = Math.max(0, Math.min(0.999999, fraction)) * (stops.length - 1);
  const index = Math.floor(scaled);
  const blend = scaled - index;
  const start = stops[index];
  const end = stops[Math.min(stops.length - 1, index + 1)];
  const rgb = start.map((value, channel) => Math.round(value + (end[channel] - value) * blend));
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
}

function calculateTrajectoryLayout(width, height) {
  const points = REPORT.position_units;
  const xs = points.map(point => point[0]);
  const ys = points.map(point => point[1]);
  let minX = arrayMin(xs);
  let maxX = arrayMax(xs);
  let minY = arrayMin(ys);
  let maxY = arrayMax(ys);
  const rangeX = Math.max(1e-6, maxX - minX);
  const rangeY = Math.max(1e-6, maxY - minY);
  const padding = { left: 58, right: 24, top: 28, bottom: 38 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const scale = Math.min(plotWidth / rangeX, plotHeight / rangeY);
  const usedWidth = rangeX * scale;
  const usedHeight = rangeY * scale;
  const offsetX = padding.left + (plotWidth - usedWidth) * 0.5;
  const offsetY = padding.top + (plotHeight - usedHeight) * 0.5;
  return {
    points,
    minX,
    maxX,
    minY,
    maxY,
    padding,
    plotWidth,
    plotHeight,
    scale,
    offsetX,
    offsetY
  };
}

function drawTrajectory() {
  const { context, width, height } = setupCanvas(trajectoryCanvas);
  context.clearRect(0, 0, width, height);
  const layout = calculateTrajectoryLayout(width, height);
  trajectoryLayout = layout;
  context.font = "12px Segoe UI, Arial";
  context.fillStyle = "#667784";
  context.strokeStyle = "#e5edf1";
  context.lineWidth = 1;

  const xFor = value => layout.offsetX + (value - layout.minX) * layout.scale;
  const yFor = value => layout.offsetY + layout.plotHeight - (value - layout.minY) * layout.scale;
  const tickCount = 5;
  for (let index = 0; index <= tickCount; index++) {
    const xValue = layout.minX + (layout.maxX - layout.minX) * index / tickCount;
    const yValue = layout.minY + (layout.maxY - layout.minY) * index / tickCount;
    const x = xFor(xValue);
    const y = yFor(yValue);
    context.beginPath();
    context.moveTo(x, layout.padding.top);
    context.lineTo(x, height - layout.padding.bottom);
    context.stroke();
    context.beginPath();
    context.moveTo(layout.padding.left, y);
    context.lineTo(width - layout.padding.right, y);
    context.stroke();
    context.textAlign = "center";
    context.fillText(`${xValue.toFixed(1)}`, x, height - 14);
    context.textAlign = "right";
    context.fillText(`${yValue.toFixed(1)}`, layout.padding.left - 8, y + 4);
  }

  const total = Math.max(1, layout.points.length - 1);
  for (let index = 1; index < layout.points.length; index += 1) {
    const previous = layout.points[index - 1];
    const current = layout.points[index];
    context.strokeStyle = trajectoryColor((index - 1) / total);
    context.lineWidth = 2.1;
    context.beginPath();
    context.moveTo(xFor(previous[0]), yFor(previous[1]));
    context.lineTo(xFor(current[0]), yFor(current[1]));
    context.stroke();
  }

  const start = layout.points[0];
  const end = layout.points.at(-1);
  context.fillStyle = "#0b8f72";
  context.beginPath();
  context.arc(xFor(start[0]), yFor(start[1]), 6, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = "#c94b55";
  context.beginPath();
  context.arc(xFor(end[0]), yFor(end[1]), 6, 0, Math.PI * 2);
  context.fill();

  const currentIndex = sampleIndex();
  const currentPoint = layout.points[currentIndex];
  const x = xFor(currentPoint[0]);
  const y = yFor(currentPoint[1]);
  const forceX = REPORT.linear.x[currentIndex];
  const forceY = REPORT.linear.y[currentIndex];
  const forceMagnitude = Math.hypot(forceX, forceY);
  if (forceMagnitude > 1) {
    const maxForce = REPORT.linear.x.reduce(
      (maximum, value, index) => Math.max(maximum, Math.hypot(value, REPORT.linear.y[index])),
      1
    );
    const length = 20 + 38 * Math.min(1, forceMagnitude / maxForce);
    const directionX = forceX / forceMagnitude;
    const directionY = -forceY / forceMagnitude;
    context.strokeStyle = "#17232d";
    context.fillStyle = "#17232d";
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(x, y);
    context.lineTo(x + directionX * length, y + directionY * length);
    context.stroke();
    const angle = Math.atan2(directionY, directionX);
    context.beginPath();
    context.moveTo(x + directionX * length, y + directionY * length);
    context.lineTo(
      x + directionX * length - 8 * Math.cos(angle - 0.45),
      y + directionY * length - 8 * Math.sin(angle - 0.45)
    );
    context.lineTo(
      x + directionX * length - 8 * Math.cos(angle + 0.45),
      y + directionY * length - 8 * Math.sin(angle + 0.45)
    );
    context.closePath();
    context.fill();
  }
  context.strokeStyle = "#ffffff";
  context.lineWidth = 2;
  context.fillStyle = "#17232d";
  context.beginPath();
  context.arc(x, y, 6, 0, Math.PI * 2);
  context.fill();
  context.stroke();

  context.fillStyle = "#435563";
  context.textAlign = "left";
  context.fillText("X 相对位置（示意单位）", width - 194, height - 8);
  context.save();
  context.translate(16, 72);
  context.rotate(-Math.PI / 2);
  context.fillText("Y 相对位置（示意单位）", 0, 0);
  context.restore();
}

function updateReadout() {
  const currentIndex = sampleIndex();
  const timeValue = REPORT.time[currentIndex];
  const speed = REPORT.speed_units_s[currentIndex];
  const accel = Math.hypot(REPORT.linear.x[currentIndex], REPORT.linear.y[currentIndex]);
  timeReadout.innerHTML = `<b>${timeValue.toFixed(3)} 秒</b> | 相对速度 ${speed.toFixed(1)} 单位/秒 | 横向加速度 ${accel.toFixed(0)} mg`;
  timeSlider.value = String(Math.round(state.index / Math.max(1, REPORT.time.length - 1) * 1000));
}

function redraw() {
  for (const chart of charts) drawChart(chart);
  drawTrajectory();
  updateReadout();
}

function stopPlayback() {
  state.playing = false;
  playButton.textContent = "播放";
}

function animationFrame(timestamp) {
  if (!state.playing) return;
  if (!state.lastFrame) state.lastFrame = timestamp;
  const deltaSeconds = Math.min(0.05, (timestamp - state.lastFrame) / 1000);
  state.lastFrame = timestamp;
  const speedMultiplier = Number(speedSelect.value);
  const duration = Math.max(1e-6, REPORT.time.at(-1));
  const increment = deltaSeconds * speedMultiplier / duration * (REPORT.time.length - 1);
  state.index += increment;
  if (state.index >= REPORT.time.length - 1) {
    state.index = REPORT.time.length - 1;
    stopPlayback();
  }
  redraw();
  if (state.playing) requestAnimationFrame(animationFrame);
}

playButton.addEventListener("click", () => {
  if (state.playing) {
    stopPlayback();
    redraw();
    return;
  }
  if (state.index >= REPORT.time.length - 1) state.index = 0;
  state.playing = true;
  state.lastFrame = 0;
  playButton.textContent = "暂停";
  requestAnimationFrame(animationFrame);
});
timeSlider.addEventListener("input", () => {
  stopPlayback();
  state.index = Number(timeSlider.value) / 1000 * (REPORT.time.length - 1);
  redraw();
});
window.addEventListener("resize", () => {
  window.clearTimeout(window.__reportResizeTimer);
  window.__reportResizeTimer = window.setTimeout(redraw, 120);
});

buildHeader();
redraw();
</script>
</body>
</html>
"""


def build_html(csv_file, metadata, derived, metrics):
    payload = report_payload(csv_file, metadata, derived, metrics)
    title = html.escape(Path(csv_file).stem)
    return (
        HTML_TEMPLATE.replace("__TITLE__", title)
        .replace("__REPORT__", json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    )


def process_capture(csv_file, args):
    csv_path = Path(csv_file).resolve()
    rows, timestamps_us = load_csv(csv_path)
    metadata = load_metadata(csv_path, args.meta)
    derived = derive_motion(rows, timestamps_us)
    metrics = quality_metrics(rows, timestamps_us, derived, args)
    output_html = (
        Path(args.output).resolve()
        if args.output
        else csv_path.with_name(f"{csv_path.stem}_motion_report.html")
    )
    output_csv = csv_path.with_name(f"{csv_path.stem}_motion.csv")
    output_html.parent.mkdir(parents=True, exist_ok=True)
    write_derived_csv(output_csv, derived)
    output_html.write_text(
        build_html(csv_path, metadata, derived, metrics),
        encoding="utf-8",
    )
    print(f"Report: {output_html}")
    print(f"Derived data: {output_csv}")
    return output_html


def latest_session_csvs(root):
    root_path = Path(root).resolve()
    session_dirs = sorted(
        [path for path in root_path.iterdir() if path.is_dir()],
        key=lambda path: (path.name, path.stat().st_mtime),
        reverse=True,
    )
    for session_dir in session_dirs:
        csv_files = sorted(
            path
            for path in session_dir.glob("capture_*.csv")
            if not path.stem.endswith("_motion")
        )
        if csv_files:
            return csv_files
    return []


def main():
    args = parse_args()
    if args.latest:
        csv_files = latest_session_csvs(args.latest)
        if not csv_files:
            raise SystemExit(f"No capture CSV files found under: {args.latest}")
    elif args.csv_file:
        csv_files = [Path(args.csv_file)]
    else:
        raise SystemExit("Provide a CSV file or --latest <output-root>.")

    generated = []
    for csv_file in csv_files:
        generated.append(process_capture(csv_file, args))
    if args.open and generated:
        webbrowser.open(generated[0].as_uri())


if __name__ == "__main__":
    main()
