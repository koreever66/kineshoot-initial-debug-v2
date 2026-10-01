"""Pair review videos with IMU captures and estimate LED t=0 in each video."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import cv2
import numpy as np


VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--video-mapping", required=True)
    parser.add_argument("--video-root", required=True)
    parser.add_argument("--capture-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sample-fps", type=float, default=20.0)
    parser.add_argument("--search-start", type=float, default=0.4)
    parser.add_argument("--search-end", type=float, default=3.0)
    return parser.parse_args()


def video_path(root: Path, player: str, stem: str) -> Path:
    folder = root / player
    for path in folder.iterdir():
        if path.is_file() and path.stem.lower() == stem.lower() and path.suffix.lower() in VIDEO_EXTENSIONS:
            return path
    raise FileNotFoundError(f"Video {stem} not found under {folder}")


def capture_files(directory: Path) -> list[Path]:
    files = []
    for path in directory.glob("capture_*.csv"):
        match = re.fullmatch(r"capture_(\d{3})\.csv", path.name)
        if match:
            files.append((int(match.group(1)), path))
    return [path for _, path in sorted(files)]


def capture_info(path: Path) -> tuple[int, float]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        timestamps = [int(row["timestamp_us"]) for row in reader]
    if len(timestamps) < 2:
        raise ValueError(f"{path} has too few IMU rows")
    return len(timestamps), (timestamps[-1] - timestamps[0]) / 1_000_000.0


def red_pixel_count(frame: np.ndarray, roi: tuple[int, int, int, int] | None = None) -> int:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    if roi is not None:
        x, y, width, height = roi
        hsv = hsv[y : y + height, x : x + width]
    lower_red = cv2.inRange(hsv, (0, 100, 80), (12, 255, 255))
    upper_red = cv2.inRange(hsv, (165, 100, 80), (180, 255, 255))
    return int(np.count_nonzero(cv2.bitwise_or(lower_red, upper_red)))


def find_led_roi(frame: np.ndarray) -> tuple[int, int, int, int] | None:
    height, width = frame.shape[:2]
    blue, green, red = cv2.split(frame.astype(np.int16))
    blue_dominance = (blue - np.maximum(red, green)).astype(np.float32)
    blue_dominance = cv2.GaussianBlur(blue_dominance, (0, 0), 3.0)
    _, maximum, _, location = cv2.minMaxLoc(blue_dominance)
    if maximum < 18:
        return None

    center_x, center_y = location
    if not (width * 0.05 < center_x < width * 0.95 and height * 0.15 < center_y < height * 0.95):
        return None
    radius = 90
    x = max(0, int(center_x) - radius)
    y = max(0, int(center_y) - radius)
    right = min(width, int(center_x) + radius)
    bottom = min(height, int(center_y) + radius)
    return x, y, right - x, bottom - y


def detect_led_start(video: Path, sample_fps: float, search_start: float, search_end: float) -> dict[str, object]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open {video}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    duration = frame_count / fps
    interval = 1.0 / sample_fps
    timestamps = np.arange(search_start, min(search_end, duration), interval)
    roi = None
    counts: list[int] = []

    for timestamp in timestamps[:3]:
        capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp * 1000.0))
        ok, frame = capture.read()
        if ok:
            roi = find_led_roi(frame)
            if roi is not None:
                break

    for timestamp in timestamps:
        capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp * 1000.0))
        ok, frame = capture.read()
        counts.append(red_pixel_count(frame, roi) if ok else 0)
    capture.release()

    if len(counts) < 5:
        raise ValueError(f"Not enough samples for {video}")

    baseline_values = counts[: max(5, min(10, len(counts) // 4))]
    baseline = float(np.median(baseline_values))
    threshold = max(baseline * 2.0, baseline + 12.0)
    run: list[int] = []
    start_index: int | None = None

    for index, count in enumerate(counts):
        if count >= threshold:
            run.append(index)
            if len(run) >= 3:
                start_index = run[0]
                break
        else:
            run = []

    if start_index is None:
        return {
            "led_red_start_s": "",
            "led_confidence": "review",
            "red_baseline_px": int(baseline),
            "red_threshold_px": int(threshold),
            "red_before_px": int(np.median(counts[: max(3, start_index or 8)])),
            "red_after_px": int(np.median(counts[start_index : start_index + 10])) if start_index is not None else "",
        }

    detected = max(0.0, float(timestamps[start_index]) - interval / 2.0)
    increase = np.median(counts[start_index : start_index + 10]) - np.median(
        counts[max(0, start_index - 5) : start_index] or counts[:1]
    )
    confidence = "detected" if increase >= 5 else "review"
    before = counts[max(0, start_index - 5) : start_index] or counts[:1]
    after = counts[start_index : start_index + 10]
    return {
        "led_red_start_s": f"{detected:.3f}",
        "led_confidence": confidence,
        "red_baseline_px": int(baseline),
        "red_threshold_px": int(threshold),
        "red_before_px": int(np.median(before)),
            "red_after_px": int(np.median(after)),
            "led_roi": ",".join(str(value) for value in roi) if roi else "",
        }


def session_lookup(registry: dict) -> dict[tuple[str, str], dict]:
    result = {}
    for session in registry["sessions"]:
        result[(session["playerId"], session["sessionType"])] = session
    return result


def main() -> int:
    args = parse_args()
    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    mapping = list(csv.DictReader(Path(args.video_mapping).open(encoding="utf-8-sig", newline="")))
    capture_paths = capture_files(Path(args.capture_dir))
    root = Path(args.video_root)
    sessions = session_lookup(registry)

    groups = [
        ("007", "repeat20", "007-20"),
        ("008", "standard20", "008-S01"),
        ("008", "supplementary20", "008-S02"),
        ("009", "standard20", "009-20"),
    ]

    records: list[dict[str, object]] = []
    capture_index = 0
    for player, session_type, label in groups:
        session = sessions[(player, session_type)]
        session_records = sorted(session["records"], key=lambda row: row["shotNo"])
        videos = sorted(
            (row for row in mapping if row["GroupLabel"] == label),
            key=lambda row: row["CreatedExact"],
        )
        if len(session_records) != len(videos):
            raise ValueError(
                f"{player}/{session_type}: {len(session_records)} records != {len(videos)} videos"
            )

        for app_record, video_record in zip(session_records, videos):
            capture_path = capture_paths[capture_index]
            shot_count, duration = capture_info(capture_path)
            path = video_path(root, player, video_record["OriginalName"])
            led = detect_led_start(
                path,
                args.sample_fps,
                args.search_start,
                args.search_end,
            )
            records.append(
                {
                    "player_id": player,
                    "session_id": session["id"],
                    "session_type": session_type,
                    "session_revision": session["revision"],
                    "shot_no": app_record["shotNo"],
                    "video_file": str(path),
                    "video_original_name": video_record["OriginalName"],
                    "video_created_local": video_record["CreatedExact"],
                    "capture_file": str(capture_path),
                    "capture_name": capture_path.name,
                    "imu_rows": shot_count,
                    "imu_duration_s": f"{duration:.3f}",
                    "planned_action": app_record.get("plannedAction") or "",
                    "planned_distance": app_record.get("plannedDistance") or "",
                    "action": app_record["action"],
                    "distance": app_record["distance"],
                    "shot_result": app_record["shotResult"],
                    "data_valid": app_record["dataValidity"],
                    "notes": app_record.get("notes", ""),
                    "sensor_t0_in_video_s": "1.075",
                    "video_to_imu_offset_s": "-1.075",
                    "alignment_status": (
                        "led_verified"
                        if led["led_confidence"] == "detected"
                        and led["led_red_start_s"]
                        and abs(float(led["led_red_start_s"]) - 1.075) <= 0.25
                        else "estimated_pending_manual_review"
                    ),
                    **led,
                }
            )
            capture_index += 1

    if capture_index != len(capture_paths):
        raise ValueError(f"Used {capture_index} captures but found {len(capture_paths)}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

    review_count = sum(row["led_confidence"] == "review" for row in records)
    print(output)
    print(f"rows={len(records)} review={review_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
