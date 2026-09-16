# encoding: utf-8
import argparse
import csv
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

import serial

from project_metadata import build_capture_metadata, find_project_root


REPO_ROOT = find_project_root(Path(__file__).resolve().parent)
DEFAULT_OUTPUT = REPO_ROOT / "data"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Record IMU CSV data and write an event log plus quality report."
    )
    parser.add_argument("--port", default="COM5", help="Serial port, for example COM5")
    parser.add_argument("--baud", type=int, default=230400, help="Serial baud rate")
    parser.add_argument("--seconds", type=float, default=30.0, help="Recording duration")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output directory or CSV file",
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=8.0,
        help="Seconds to wait for IMU_READY or the first DATA row",
    )
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
    parser.add_argument("--hardware-revision")
    parser.add_argument("--mount-position")
    parser.add_argument("--test-type")
    parser.add_argument("--operator")
    parser.add_argument("--power-source")
    parser.add_argument("--trigger-source")
    parser.add_argument("--motion-speed")
    return parser.parse_args()


def resolve_output_path(output):
    output_path = Path(output).expanduser()
    if output_path.suffix.lower() == ".csv":
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path

    output_path.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_path / f"imu_v2_{stamp}.csv"


def parse_line(line):
    parts = line.split(",")
    if parts[0] == "DATA" and len(parts) == 10:
        try:
            return {
                "kind": "data",
                "seq": int(parts[1]),
                "timestamp_us": int(parts[2]),
                "values": [float(value) for value in parts[3:]],
            }
        except ValueError:
            return {"kind": "event"}

    if len(parts) == 8 and parts[0].isdigit():
        try:
            return {
                "kind": "legacy_data",
                "seq": 0,
                "timestamp_us": int(parts[0]) * 1000,
                "values": [float(value) for value in parts[1:]],
            }
        except ValueError:
            return {"kind": "event"}

    return {"kind": "event"}


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = int(fraction * (len(ordered) - 1))
    return ordered[index]


def build_quality(samples, args, duration_s):
    timestamps = [sample["timestamp_us"] for sample in samples]
    intervals_us = [
        timestamps[index] - timestamps[index - 1]
        for index in range(1, len(timestamps))
    ]
    median_interval_us = statistics.median(intervals_us) if intervals_us else None
    gap_threshold_us = args.gap_ms * 1000.0
    if median_interval_us:
        gap_threshold_us = max(gap_threshold_us, median_interval_us * 4.0)

    gaps = []
    for index, interval_us in enumerate(intervals_us, start=1):
        if interval_us >= gap_threshold_us:
            gaps.append(
                {
                    "timestamp_us": timestamps[index],
                    "gap_ms": interval_us / 1000.0,
                }
            )

    accelerations = []
    temperatures = []
    clipped_acc_samples = 0
    clipped_gyro_samples = 0

    for sample in samples:
        ax, ay, az, gx, gy, gz, temperature = sample["values"]
        accelerations.append((ax * ax + ay * ay + az * az) ** 0.5)
        temperatures.append(temperature)
        if max(abs(ax), abs(ay), abs(az)) >= args.acc_limit_mg:
            clipped_acc_samples += 1
        if max(abs(gx), abs(gy), abs(gz)) >= args.gyro_limit_dps:
            clipped_gyro_samples += 1

    firmware_duration_s = (
        (timestamps[-1] - timestamps[0]) / 1_000_000.0
        if len(timestamps) > 1
        else 0.0
    )
    sample_rate_hz = (
        (len(samples) - 1) / firmware_duration_s
        if firmware_duration_s > 0
        else 0.0
    )

    return {
        "rows": len(samples),
        "host_duration_s": round(duration_s, 3),
        "firmware_duration_s": round(firmware_duration_s, 3),
        "sample_rate_hz": round(sample_rate_hz, 2),
        "median_interval_ms": (
            round(median_interval_us / 1000.0, 3)
            if median_interval_us
            else None
        ),
        "p95_interval_ms": (
            round(percentile(intervals_us, 0.95) / 1000.0, 3)
            if intervals_us
            else None
        ),
        "gap_threshold_ms": round(gap_threshold_us / 1000.0, 3),
        "gap_count": len(gaps),
        "largest_gaps": sorted(gaps, key=lambda item: item["gap_ms"], reverse=True)[
            :10
        ],
        "gravity_magnitude_mean_mg": (
            round(statistics.fmean(accelerations), 2) if accelerations else None
        ),
        "gravity_magnitude_stdev_mg": (
            round(statistics.pstdev(accelerations), 2) if accelerations else None
        ),
        "temperature_min_c": round(min(temperatures), 2) if temperatures else None,
        "temperature_max_c": round(max(temperatures), 2) if temperatures else None,
        "clipped_acc_samples": clipped_acc_samples,
        "clipped_gyro_samples": clipped_gyro_samples,
    }


def count_events(event_lines, prefix):
    return sum(1 for line in event_lines if line["line"].startswith(prefix))


def main():
    args = parse_args()
    output_path = resolve_output_path(args.output)
    events_path = output_path.with_suffix(".events.log")
    metadata_path = output_path.with_suffix(".meta.json")

    print(f"Opening {args.port} at {args.baud} baud")
    print(f"Saving to {output_path}")
    print(f"Recording for {args.seconds:g} seconds")

    samples = []
    event_lines = []
    config_line = None
    ready_seen = False
    recording_started_monotonic = None
    start_wall_time = None

    with serial.Serial(args.port, args.baud, timeout=1) as ser:
        try:
            ser.setDTR(False)
            ser.setRTS(False)
        except Exception:
            pass

        with output_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "host_elapsed_s",
                    "seq",
                    "timestamp_us",
                    "ax_mg",
                    "ay_mg",
                    "az_mg",
                    "gx_dps",
                    "gy_dps",
                    "gz_dps",
                    "temp_c",
                ]
            )
            last_flush = time.monotonic()
            ready_deadline = time.monotonic() + args.ready_timeout

            while True:
                now = time.monotonic()

                if recording_started_monotonic is None:
                    if now >= ready_deadline:
                        raise SystemExit(
                            "No IMU_READY or DATA row received before the ready timeout."
                        )
                elif now - recording_started_monotonic >= args.seconds:
                    break

                raw = ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                parsed = parse_line(line)
                now = time.monotonic()

                if parsed["kind"] == "event":
                    elapsed = (
                        now - recording_started_monotonic
                        if recording_started_monotonic is not None
                        else 0.0
                    )
                    event_lines.append({"elapsed_s": elapsed, "line": line})
                    if line.startswith("IMU_CONFIG,"):
                        config_line = line
                    elif line in ("IMU_V2_READY", "IMU_READY"):
                        ready_seen = True
                    continue

                if recording_started_monotonic is None:
                    recording_started_monotonic = now
                    start_wall_time = datetime.now().astimezone()

                elapsed = now - recording_started_monotonic
                values = parsed["values"]
                writer.writerow(
                    [
                        f"{elapsed:.6f}",
                        parsed["seq"],
                        parsed["timestamp_us"],
                        *[f"{value:.4f}" for value in values],
                    ]
                )
                samples.append(
                    {
                        "timestamp_us": parsed["timestamp_us"],
                        "values": values,
                    }
                )

                if now - last_flush >= 1.0:
                    stream.flush()
                    last_flush = now

            stream.flush()

    duration_s = (
        time.monotonic() - recording_started_monotonic
        if recording_started_monotonic is not None
        else 0.0
    )
    quality = build_quality(samples, args, duration_s)
    quality["error_events"] = count_events(event_lines, "ERR,")
    quality["reset_events"] = count_events(event_lines, "RESET,")
    quality["ready_seen"] = ready_seen

    metadata = {
        "port": args.port,
        "baud": args.baud,
        "requested_seconds": args.seconds,
        "start_time": (
            start_wall_time.isoformat() if start_wall_time is not None else None
        ),
        "end_time": datetime.now().astimezone().isoformat(),
        "config": config_line,
        "project": build_capture_metadata(
            REPO_ROOT,
            hardware_revision=args.hardware_revision,
            mount_position=args.mount_position,
            test_type=args.test_type,
            operator=args.operator,
            power_source=args.power_source,
            trigger_source=args.trigger_source,
            motion_speed=args.motion_speed,
        ),
        "quality": quality,
    }

    with events_path.open("w", encoding="utf-8") as event_stream:
        for event in event_lines:
            event_stream.write(f"{event['elapsed_s']:.6f},{event['line']}\n")

    with metadata_path.open("w", encoding="utf-8") as metadata_stream:
        json.dump(metadata, metadata_stream, ensure_ascii=False, indent=2)
        metadata_stream.write("\n")

    print(f"Done. Saved {quality['rows']} rows.")
    print(
        "Rate: "
        f"{quality['sample_rate_hz']:.2f} Hz, "
        f"median interval {quality['median_interval_ms']} ms, "
        f"p95 {quality['p95_interval_ms']} ms"
    )
    print(
        "Gaps: "
        f"{quality['gap_count']}, "
        f"errors: {quality['error_events']}, "
        f"resets: {quality['reset_events']}"
    )
    print(
        "Gravity magnitude: "
        f"{quality['gravity_magnitude_mean_mg']} mg "
        f"(stdev {quality['gravity_magnitude_stdev_mg']} mg)"
    )
    print(f"Events: {events_path}")
    print(f"Metadata: {metadata_path}")


if __name__ == "__main__":
    main()
