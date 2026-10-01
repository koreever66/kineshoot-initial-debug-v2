"""Create timestamped contact sheets for KineShoot review videos."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("video_dirs", nargs="+", help="Directories containing review videos")
    parser.add_argument("--output", required=True, help="Contact-sheet output directory")
    parser.add_argument("--frames", type=int, default=16, help="Frames sampled per video")
    parser.add_argument("--columns", type=int, default=4, help="Contact-sheet columns")
    parser.add_argument("--tile-width", type=int, default=270)
    return parser.parse_args()


def video_files(directory: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        ),
        key=lambda path: (path.stat().st_mtime, path.name.lower()),
    )


def add_label(frame: np.ndarray, text: str) -> np.ndarray:
    labeled = frame.copy()
    cv2.rectangle(labeled, (0, 0), (labeled.shape[1], 32), (0, 0, 0), -1)
    cv2.putText(
        labeled,
        text,
        (8, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return labeled


def build_sheet(
    video: Path,
    output: Path,
    frame_count: int,
    columns: int,
    tile_width: int,
) -> dict[str, object]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open {video}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    duration = total_frames / fps
    timestamps = np.linspace(0.0, max(0.0, duration - 0.1), frame_count)
    tile_height = int(tile_width * 16 / 9)
    tiles: list[np.ndarray] = []

    for timestamp in timestamps:
        capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp * 1000.0))
        ok, frame = capture.read()
        if not ok:
            frame = np.zeros((tile_height, tile_width, 3), dtype=np.uint8)
        frame = cv2.resize(frame, (tile_width, tile_height), interpolation=cv2.INTER_AREA)
        tiles.append(add_label(frame, f"{timestamp:05.2f}s"))

    capture.release()
    rows = int(np.ceil(len(tiles) / columns))
    while len(tiles) < rows * columns:
        tiles.append(np.zeros((tile_height, tile_width, 3), dtype=np.uint8))

    sheet_rows = [
        np.hstack(tiles[index * columns : (index + 1) * columns])
        for index in range(rows)
    ]
    sheet = np.vstack(sheet_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return {
        "video": str(video),
        "sheet": str(output),
        "duration_seconds": f"{duration:.3f}",
        "fps": f"{fps:.3f}",
        "frames": total_frames,
    }


def main() -> int:
    args = parse_args()
    output = Path(args.output).resolve()
    records: list[dict[str, object]] = []
    index = 1

    for directory_name in args.video_dirs:
        directory = Path(directory_name).resolve()
        for video in video_files(directory):
            stem = f"{index:03d}_{directory.name}_{video.stem}"
            output_path = output / f"{stem}.jpg"
            record = build_sheet(
                video,
                output_path,
                args.frames,
                args.columns,
                args.tile_width,
            )
            record["index"] = index
            record["player"] = directory.name
            records.append(record)
            print(output_path)
            index += 1

    manifest = output / "contact_sheet_manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(f"MANIFEST {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
