"""Build synchronized IMU/video timelines and draft action-phase candidates."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alignment", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--contact-frames", type=int, default=12)
    return parser.parse_args()


def smooth(values: np.ndarray, window: int = 15) -> np.ndarray:
    if len(values) < window:
        return values
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def load_capture(path: Path) -> dict[str, np.ndarray]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    timestamp_us = np.array([int(row["timestamp_us"]) for row in rows], dtype=float)
    time_s = (timestamp_us - timestamp_us[0]) / 1_000_000.0
    return {
        "time_s": time_s,
        "ax_g": np.array([float(row["ax_mg"]) for row in rows]) / 1000.0,
        "ay_g": np.array([float(row["ay_mg"]) for row in rows]) / 1000.0,
        "az_g": np.array([float(row["az_mg"]) for row in rows]) / 1000.0,
        "gx_dps": np.array([float(row["gx_dps"]) for row in rows]),
        "gy_dps": np.array([float(row["gy_dps"]) for row in rows]),
        "gz_dps": np.array([float(row["gz_dps"]) for row in rows]),
    }


def candidate_phases(data: dict[str, np.ndarray]) -> dict[str, float]:
    time_s = data["time_s"]
    gyro_magnitude = np.sqrt(
        data["gx_dps"] ** 2 + data["gy_dps"] ** 2 + data["gz_dps"] ** 2
    )
    acceleration_magnitude = np.sqrt(
        data["ax_g"] ** 2 + data["ay_g"] ** 2 + data["az_g"] ** 2
    )
    gyro_smooth = smooth(gyro_magnitude)
    accel_smooth = smooth(acceleration_magnitude)

    baseline_end = max(5, min(len(time_s) // 4, int(np.searchsorted(time_s, 0.6))))
    baseline_gyro = float(np.median(gyro_smooth[:baseline_end]))
    baseline_accel = float(np.median(accel_smooth[:baseline_end]))

    search_start = int(np.searchsorted(time_s, 0.8))
    search_end = max(search_start + 1, int(np.searchsorted(time_s, 9.8)))
    peak_index = search_start + int(np.argmax(gyro_smooth[search_start:search_end]))
    peak_value = float(gyro_smooth[peak_index])
    peak_prominence = max(1.0, peak_value - baseline_gyro)

    onset_threshold = baseline_gyro + max(8.0, peak_prominence * 0.18)
    action_index = search_start
    for index in range(search_start, peak_index + 1):
        future_end = min(len(gyro_smooth), index + 8)
        if np.all(gyro_smooth[index:future_end] >= onset_threshold):
            action_index = index
            break

    centered_vertical = data["az_g"] - float(np.median(data["az_g"][:baseline_end]))
    dip_start = action_index
    dip_end = max(dip_start + 1, peak_index)
    dip_index = dip_start + int(np.argmin(centered_vertical[dip_start:dip_end]))

    lift_threshold = baseline_gyro + max(5.0, peak_prominence * 0.35)
    lift_index = dip_index
    for index in range(dip_index, peak_index + 1):
        if gyro_smooth[index] >= lift_threshold:
            lift_index = index
            break

    follow_index = min(len(time_s) - 1, peak_index + int(round(0.45 / max(1e-6, np.median(np.diff(time_s))))))

    return {
        "baseline_gyro_dps": baseline_gyro,
        "baseline_accel_g": baseline_accel,
        "candidate_action_start_s": float(time_s[action_index]),
        "candidate_dip_s": float(time_s[dip_index]),
        "candidate_lift_s": float(time_s[lift_index]),
        "candidate_peak_s": float(time_s[peak_index]),
        "candidate_peak_window_start_s": max(0.0, float(time_s[peak_index]) - 0.20),
        "candidate_peak_window_end_s": min(float(time_s[-1]), float(time_s[peak_index]) + 0.20),
        "candidate_follow_s": float(time_s[follow_index]),
        "candidate_peak_dps": peak_value,
        "static_gyro_rms_dps": float(np.sqrt(np.mean(gyro_smooth[:baseline_end] ** 2))),
        "phase_confidence": "draft",
    }


def write_aligned_csv(path: Path, data: dict[str, np.ndarray], sensor_t0_video: float) -> None:
    columns = [
        "time_s",
        "video_time_s",
        "ax_g",
        "ay_g",
        "az_g",
        "gx_dps",
        "gy_dps",
        "gz_dps",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for index, time_value in enumerate(data["time_s"]):
            writer.writerow(
                [
                    f"{time_value:.6f}",
                    f"{time_value + sensor_t0_video:.6f}",
                    f"{data['ax_g'][index]:.6f}",
                    f"{data['ay_g'][index]:.6f}",
                    f"{data['az_g'][index]:.6f}",
                    f"{data['gx_dps'][index]:.3f}",
                    f"{data['gy_dps'][index]:.3f}",
                    f"{data['gz_dps'][index]:.3f}",
                ]
            )


def draw_plot(path: Path, data: dict[str, np.ndarray], phases: dict[str, float]) -> None:
    width, height = 1400, 760
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = 70, 50, width - 30, height - 60
    draw.rectangle((left, top, right, bottom), outline=(60, 60, 60), width=2)

    time_s = data["time_s"]
    gyro = smooth(np.sqrt(data["gx_dps"] ** 2 + data["gy_dps"] ** 2 + data["gz_dps"] ** 2))
    residual = np.sqrt(
        (data["ax_g"] - np.median(data["ax_g"][: max(5, len(time_s) // 4)])) ** 2
        + (data["ay_g"] - np.median(data["ay_g"][: max(5, len(time_s) // 4)])) ** 2
        + (data["az_g"] - np.median(data["az_g"][: max(5, len(time_s) // 4)])) ** 2
    )

    def x_coordinate(value: float) -> float:
        return left + (right - left) * value / max(0.001, time_s[-1])

    gyro_max = max(1.0, float(np.max(gyro)))
    for series, color, maximum in ((gyro, (180, 30, 30), gyro_max), (residual * 1000.0, (20, 90, 180), max(1.0, float(np.max(residual * 1000.0))))):
        points = [
            (x_coordinate(float(time_value)), bottom - (bottom - top) * float(value) / maximum)
            for time_value, value in zip(time_s, series)
        ]
        draw.line(points, fill=color, width=2)

    for key, color in (
        ("candidate_action_start_s", (0, 120, 0)),
        ("candidate_dip_s", (150, 80, 0)),
        ("candidate_lift_s", (130, 0, 130)),
        ("candidate_peak_s", (200, 0, 0)),
        ("candidate_follow_s", (0, 120, 120)),
    ):
        x = x_coordinate(phases[key])
        draw.line((x, top, x, bottom), fill=color, width=2)
        draw.text((x + 3, top + 5), key.replace("candidate_", ""), fill=color)

    draw.text((left, 18), "IMU magnitude (red) and residual acceleration x1000 (blue)", fill=(0, 0, 0))
    image.save(path, quality=92)


def review_sheet(
    video_path: Path,
    output_path: Path,
    t0_s: float,
    phase_s: float,
    frame_count: int,
) -> None:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return
    fps = capture.get(cv2.CAP_PROP_FPS) or 60.0
    duration = capture.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    start = max(0.0, t0_s + phase_s - 0.5)
    end = min(duration, t0_s + phase_s + 0.5)
    timestamps = np.linspace(start, end, frame_count)
    tiles = []
    for timestamp in timestamps:
        capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp * 1000.0))
        ok, frame = capture.read()
        if not ok:
            frame = np.zeros((480, 270, 3), dtype=np.uint8)
        frame = cv2.resize(frame, (270, 480), interpolation=cv2.INTER_AREA)
        cv2.rectangle(frame, (0, 0), (270, 28), (0, 0, 0), -1)
        cv2.putText(
            frame,
            f"{timestamp:.2f}s",
            (8, 21),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        tiles.append(frame)
    capture.release()
    columns = 4
    rows = int(math.ceil(len(tiles) / columns))
    tiles.extend([np.zeros((480, 270, 3), dtype=np.uint8)] * (rows * columns - len(tiles)))
    sheet = np.vstack([np.hstack(tiles[index * columns : (index + 1) * columns]) for index in range(rows)])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    aligned_dir = output / "aligned_csv"
    plot_dir = output / "plots"
    review_dir = output / "release_review"
    for directory in (aligned_dir, plot_dir, review_dir):
        directory.mkdir(parents=True, exist_ok=True)

    alignment_rows = list(
        csv.DictReader(Path(args.alignment).open(encoding="utf-8-sig", newline=""))
    )
    summary_rows = []

    for row in alignment_rows:
        t0_s = float(row["sensor_t0_in_video_s"])
        data = load_capture(Path(row["capture_file"]))
        phases = candidate_phases(data)
        stem = f"{row['player_id']}_{int(row['shot_no']):03d}_{row['video_original_name']}"
        aligned_path = aligned_dir / f"{stem}_aligned.csv"
        plot_path = plot_dir / f"{stem}_imu_phases.jpg"
        review_path = review_dir / f"{stem}_release_review.jpg"

        write_aligned_csv(aligned_path, data, t0_s)
        draw_plot(plot_path, data, phases)
        review_sheet(
            Path(row["video_file"]),
            review_path,
            t0_s,
            phases["candidate_peak_s"],
            args.contact_frames,
        )

        summary_rows.append(
            {
                **row,
                **phases,
                "aligned_csv": str(aligned_path),
                "phase_plot": str(plot_path),
                "release_review_sheet": str(review_path),
            }
        )
        print(stem)

    summary_path = output / "imu_phase_candidates.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"SUMMARY {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
