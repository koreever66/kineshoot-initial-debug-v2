# encoding: utf-8
import argparse
import csv
import math
import os
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_args():
    parser = argparse.ArgumentParser(
        description="Plot IMU CSV data with gaps and clipping marked."
    )
    parser.add_argument("csv_file")
    parser.add_argument("--output", help="Output PNG path")
    parser.add_argument(
        "--gap-ms",
        type=float,
        default=20.0,
        help="Minimum timestamp gap considered a data gap",
    )
    parser.add_argument(
        "--acc-limit-mg",
        type=float,
        default=16000.0,
        help="Acceleration magnitude considered clipped",
    )
    parser.add_argument(
        "--gyro-limit-dps",
        type=float,
        default=2000.0,
        help="Angular velocity magnitude considered clipped",
    )
    return parser.parse_args()


def percentile(values, fraction):
    ordered = sorted(values)
    index = int(fraction * (len(ordered) - 1))
    return ordered[index]


def load_csv(csv_file):
    with open(csv_file, "r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    if not rows:
        raise SystemExit("CSV has no data rows.")

    if "timestamp_us" in rows[0]:
        timestamps = [int(row["timestamp_us"]) for row in rows]
    elif "timestamp_ms" in rows[0]:
        timestamps = [int(row["timestamp_ms"]) * 1000 for row in rows]
    else:
        raise SystemExit("CSV is missing timestamp_us or timestamp_ms.")

    return rows, timestamps


def insert_gap_breaks(time_s, values, gap_threshold_s):
    output_time = []
    output_values = []
    gaps = []

    for index, value in enumerate(values):
        if index:
            gap_s = time_s[index] - time_s[index - 1]
            if gap_s >= gap_threshold_s:
                output_time.append(time_s[index - 1])
                output_values.append(float("nan"))
                gaps.append((time_s[index - 1], time_s[index]))

        output_time.append(time_s[index])
        output_values.append(value)

    return output_time, output_values, gaps


def mark_clipping(axes, x_values, values, limit, label):
    clipped = [abs(value) >= limit - 1e-6 for value in values]
    if not any(clipped):
        return 0

    clipped_x = [x for x, is_clipped in zip(x_values, clipped) if is_clipped]
    clipped_y = [value for value, is_clipped in zip(values, clipped) if is_clipped]
    axes.scatter(
        clipped_x,
        clipped_y,
        color="black",
        marker="x",
        s=24,
        linewidths=1.2,
        label=label,
        zorder=5,
    )
    return sum(clipped)


def default_output_path(csv_file):
    csv_directory = os.path.dirname(os.path.abspath(csv_file))
    if os.path.basename(csv_directory).lower() == "data":
        output_directory = os.path.join(os.path.dirname(csv_directory), "plots")
    else:
        output_directory = csv_directory

    os.makedirs(output_directory, exist_ok=True)
    stem = os.path.splitext(os.path.basename(csv_file))[0]
    return os.path.join(output_directory, f"{stem}_quality.png")


def main():
    args = parse_args()
    csv_file = os.path.abspath(args.csv_file)
    output_png = os.path.abspath(args.output) if args.output else default_output_path(csv_file)
    os.makedirs(os.path.dirname(output_png), exist_ok=True)

    rows, timestamps_us = load_csv(csv_file)
    start_us = timestamps_us[0]
    time_s = [(value - start_us) / 1_000_000.0 for value in timestamps_us]

    ax = [float(row["ax_mg"]) for row in rows]
    ay = [float(row["ay_mg"]) for row in rows]
    az = [float(row["az_mg"]) for row in rows]
    gx = [float(row["gx_dps"]) for row in rows]
    gy = [float(row["gy_dps"]) for row in rows]
    gz = [float(row["gz_dps"]) for row in rows]
    temperature = [float(row["temp_c"]) for row in rows]

    intervals_ms = [
        (timestamps_us[index] - timestamps_us[index - 1]) / 1000.0
        for index in range(1, len(timestamps_us))
    ]
    median_interval_ms = statistics.median(intervals_ms) if intervals_ms else 0.0
    gap_threshold_s = max(args.gap_ms / 1000.0, median_interval_ms * 4.0 / 1000.0)

    plot_time, plot_ax, gaps = insert_gap_breaks(time_s, ax, gap_threshold_s)
    _, plot_ay, _ = insert_gap_breaks(time_s, ay, gap_threshold_s)
    _, plot_az, _ = insert_gap_breaks(time_s, az, gap_threshold_s)
    _, plot_gx, _ = insert_gap_breaks(time_s, gx, gap_threshold_s)
    _, plot_gy, _ = insert_gap_breaks(time_s, gy, gap_threshold_s)
    _, plot_gz, _ = insert_gap_breaks(time_s, gz, gap_threshold_s)
    _, plot_temperature, _ = insert_gap_breaks(time_s, temperature, gap_threshold_s)

    acc_magnitude = [
        math.sqrt(x * x + y * y + z * z) for x, y, z in zip(ax, ay, az)
    ]
    gyro_magnitude = [
        math.sqrt(x * x + y * y + z * z) for x, y, z in zip(gx, gy, gz)
    ]
    _, plot_acc_magnitude, _ = insert_gap_breaks(
        time_s, acc_magnitude, gap_threshold_s
    )
    _, plot_gyro_magnitude, _ = insert_gap_breaks(
        time_s, gyro_magnitude, gap_threshold_s
    )

    interval_time = time_s[1:]
    plot_interval_time, plot_intervals, _ = insert_gap_breaks(
        interval_time, intervals_ms, gap_threshold_s
    )

    fig, axes = plt.subplots(3, 2, figsize=(14, 10), constrained_layout=True)
    fig.suptitle(f"ICM-20948 Sensor Record | {os.path.basename(csv_file)}", fontsize=15)

    for axis in axes.flat:
        for gap_start, gap_end in gaps:
            axis.axvspan(gap_start, gap_end, color="0.85", alpha=0.45, zorder=0)

    axes[0, 0].plot(plot_time, plot_ax, label="AX")
    axes[0, 0].plot(plot_time, plot_ay, label="AY")
    axes[0, 0].plot(plot_time, plot_az, label="AZ")
    axes[0, 0].set_title("Acceleration (mg)")
    axes[0, 0].set_xlabel("Time (s)")
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend()

    clipped_acc = 0
    clipped_acc += mark_clipping(
        axes[0, 0], time_s, ax, args.acc_limit_mg, "AX clipped"
    )
    clipped_acc += mark_clipping(
        axes[0, 0], time_s, ay, args.acc_limit_mg, "AY clipped"
    )
    clipped_acc += mark_clipping(
        axes[0, 0], time_s, az, args.acc_limit_mg, "AZ clipped"
    )

    axes[0, 1].plot(plot_time, plot_gx, label="GX")
    axes[0, 1].plot(plot_time, plot_gy, label="GY")
    axes[0, 1].plot(plot_time, plot_gz, label="GZ")
    axes[0, 1].set_title("Angular Velocity (deg/s)")
    axes[0, 1].set_xlabel("Time (s)")
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].legend()

    clipped_gyro = 0
    clipped_gyro += mark_clipping(
        axes[0, 1], time_s, gx, args.gyro_limit_dps, "GX clipped"
    )
    clipped_gyro += mark_clipping(
        axes[0, 1], time_s, gy, args.gyro_limit_dps, "GY clipped"
    )
    clipped_gyro += mark_clipping(
        axes[0, 1], time_s, gz, args.gyro_limit_dps, "GZ clipped"
    )

    axes[1, 0].plot(plot_time, plot_acc_magnitude, color="tab:green")
    axes[1, 0].axhline(1000.0, color="0.4", linestyle="--", linewidth=1)
    axes[1, 0].set_title("Acceleration Magnitude (mg)")
    axes[1, 0].set_xlabel("Time (s)")
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].plot(plot_time, plot_gyro_magnitude, color="tab:red")
    axes[1, 1].set_title("Gyroscope Magnitude (deg/s)")
    axes[1, 1].set_xlabel("Time (s)")
    axes[1, 1].grid(True, alpha=0.3)

    axes[2, 0].plot(plot_time, plot_temperature, color="tab:orange")
    axes[2, 0].set_title("Temperature (C)")
    axes[2, 0].set_xlabel("Time (s)")
    axes[2, 0].grid(True, alpha=0.3)

    axes[2, 1].plot(plot_interval_time, plot_intervals, color="tab:blue")
    axes[2, 1].axhline(
        median_interval_ms,
        color="tab:green",
        linestyle="--",
        linewidth=1,
        label=f"median {median_interval_ms:.2f} ms",
    )
    axes[2, 1].axhline(
        gap_threshold_s * 1000.0,
        color="tab:red",
        linestyle=":",
        linewidth=1,
        label=f"gap threshold {gap_threshold_s * 1000.0:.1f} ms",
    )
    axes[2, 1].set_title("Sample Interval (ms)")
    axes[2, 1].set_xlabel("Time (s)")
    axes[2, 1].grid(True, alpha=0.3)
    axes[2, 1].legend()

    fig.savefig(output_png, dpi=160)

    duration_s = time_s[-1] if time_s else 0.0
    sample_rate_hz = (len(rows) - 1) / duration_s if duration_s > 0 else 0.0
    p95_interval_ms = percentile(intervals_ms, 0.95) if intervals_ms else 0.0

    print(f"Rows: {len(rows)}")
    print(f"Duration: {duration_s:.3f} s")
    print(f"Average sample rate: {sample_rate_hz:.2f} Hz")
    print(f"Median interval: {median_interval_ms:.3f} ms")
    print(f"P95 interval: {p95_interval_ms:.3f} ms")
    print(f"Gaps >= {gap_threshold_s * 1000.0:.1f} ms: {len(gaps)}")
    print(f"Clipped acceleration samples: {clipped_acc}")
    print(f"Clipped gyroscope samples: {clipped_gyro}")
    print(f"Plot: {output_png}")


if __name__ == "__main__":
    main()
