# encoding: utf-8
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import serial

from project_metadata import build_capture_metadata, find_project_root


REPO_ROOT = find_project_root(Path(__file__).resolve().parent)
DEFAULT_OUTPUT = REPO_ROOT / "data"


def parse_args():
    parser = argparse.ArgumentParser(
        description="List and export IMU capture files stored in ESP32 LittleFS."
    )
    parser.add_argument("--port", default="COM5", help="Serial port, for example COM5")
    parser.add_argument("--baud", type=int, default=230400, help="Serial baud rate")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Directory for downloaded CSV files",
    )
    parser.add_argument(
        "--delete-after-download",
        action="store_true",
        help="Delete each capture from ESP32 after successful download",
    )
    parser.add_argument(
        "--session-dir",
        action="store_true",
        help="Create a timestamped subdirectory for each export session",
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for IMU_FLASH_V3_READY or IMU_FLASH_V4_READY",
    )
    parser.add_argument("--hardware-revision")
    parser.add_argument("--mount-position")
    parser.add_argument("--test-type")
    parser.add_argument("--operator")
    parser.add_argument("--power-source")
    parser.add_argument("--trigger-source")
    return parser.parse_args()


def read_line(ser, deadline):
    while time.monotonic() < deadline:
        raw = ser.readline()
        if raw:
            return raw.decode("utf-8", errors="ignore").strip()
    raise TimeoutError("Timed out waiting for a serial line.")


def wait_for_ready(ser, timeout_s):
    deadline = time.monotonic() + timeout_s
    next_probe = time.monotonic()
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_probe:
            ser.write(b"INFO\n")
            ser.flush()
            next_probe = now + 1.0

        try:
            line = read_line(ser, min(deadline, time.monotonic() + 1.0))
        except TimeoutError:
            continue

        if line:
            print(f"device: {line}")
        if line in ("IMU_FLASH_V3_READY", "IMU_FLASH_V4_READY") or line.startswith(
            "INFO,"
        ):
            return
        if line == "FILESYSTEM_ERROR":
            raise RuntimeError("LittleFS initialization failed on the ESP32.")
        if line in ("IMU_FLASH_V3_FATAL", "IMU_FLASH_V4_FATAL"):
            raise RuntimeError("IMU initialization failed on the ESP32.")
        if "DOWNLOAD(USB/UART0)" in line or line == "waiting for download":
            raise RuntimeError(
                "ESP32 is in download mode. Release BOOT and press RST, "
                "then run the export again."
            )
    raise TimeoutError("ESP32 did not become ready.")


def list_remote_files(ser):
    ser.reset_input_buffer()
    ser.write(b"LIST\n")
    ser.flush()

    files = []
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        line = read_line(ser, deadline)
        if line == "LIST_END":
            return files
        if line.startswith("FILE,"):
            _, path, size = line.split(",", 2)
            files.append({"path": path, "size": int(size)})
    raise TimeoutError("Timed out waiting for LIST_END.")


def read_exact(ser, byte_count, deadline):
    chunks = []
    remaining = byte_count
    while remaining > 0 and time.monotonic() < deadline:
        chunk = ser.read(remaining)
        if not chunk:
            continue
        chunks.append(chunk)
        remaining -= len(chunk)

    if remaining:
        raise TimeoutError(
            f"Timed out with {remaining} bytes remaining in the download."
        )
    return b"".join(chunks)


def download_file(ser, remote_path, remote_size, output_directory):
    ser.reset_input_buffer()
    ser.write(f"DUMP {remote_path}\n".encode("ascii"))
    ser.flush()

    deadline = time.monotonic() + 10.0
    begin_line = read_line(ser, deadline)
    if not begin_line.startswith("BEGIN_FILE,"):
        raise RuntimeError(f"Unexpected download response: {begin_line}")

    _, returned_path, returned_size = begin_line.split(",", 2)
    if returned_path != remote_path or int(returned_size) != remote_size:
        raise RuntimeError(
            "Download header did not match the LIST response: "
            f"{begin_line}"
        )

    payload = read_exact(
        ser,
        remote_size,
        time.monotonic() + max(30.0, remote_size / 15000.0),
    )

    tail_deadline = time.monotonic() + 5.0
    while time.monotonic() < tail_deadline:
        line = read_line(ser, tail_deadline)
        if line == "END_FILE":
            break
    else:
        raise TimeoutError("Timed out waiting for END_FILE.")

    local_path = output_directory / Path(remote_path).name
    local_path.write_bytes(payload)
    return local_path


def delete_remote_file(ser, remote_path):
    ser.write(f"DELETE {remote_path}\n".encode("ascii"))
    ser.flush()

    deadline = time.monotonic() + 5.0
    response = read_line(ser, deadline)
    if not response.startswith("DELETE_OK,"):
        raise RuntimeError(f"Delete failed: {response}")


def main():
    args = parse_args()
    output_directory = Path(args.output).expanduser()
    if args.session_dir:
        if output_directory.suffix.lower() == ".csv":
            raise SystemExit("--session-dir cannot be used with a CSV file output.")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_directory = output_directory / f"session_{stamp}"

    output_directory.mkdir(parents=True, exist_ok=True)
    print(f"Export session: {output_directory}")

    print(f"Opening {args.port} at {args.baud} baud")
    with serial.Serial(args.port, args.baud, timeout=0.25) as ser:
        try:
            ser.setDTR(False)
            ser.setRTS(False)
        except Exception:
            pass

        wait_for_ready(ser, args.ready_timeout)
        files = list_remote_files(ser)

        if not files:
            print("No capture files found.")
            return

        print(f"Found {len(files)} capture file(s).")
        for remote in files:
            local_path = download_file(
                ser,
                remote["path"],
                remote["size"],
                output_directory,
            )
            metadata = build_capture_metadata(
                REPO_ROOT,
                hardware_revision=args.hardware_revision,
                mount_position=args.mount_position,
                test_type=args.test_type,
                operator=args.operator,
                power_source=args.power_source,
                trigger_source=args.trigger_source,
            )
            metadata.update(
                {
                    "remote_path": remote["path"],
                    "remote_size": remote["size"],
                    "local_path": str(local_path),
                    "downloaded_at": datetime.now().astimezone().isoformat(),
                }
            )
            metadata_path = local_path.with_suffix(".meta.json")
            with metadata_path.open("w", encoding="utf-8") as stream:
                json.dump(metadata, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            print(f"Downloaded: {local_path}")
            print(f"Metadata: {metadata_path}")

            if args.delete_after_download:
                delete_remote_file(ser, remote["path"])
                print(f"Deleted from ESP32: {remote['path']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Export failed: {exc}")
        raise SystemExit(1)
