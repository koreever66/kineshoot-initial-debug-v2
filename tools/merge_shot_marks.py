# encoding: utf-8
"""Merge KineShoot app shot marks into the WPS workbook.

The script intentionally writes only the shooting annotation columns:
D=action, E=distance, F=orientation, G=result, H=validity, M=notes.
Player 000 and sessions marked as abolished are excluded by default.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from collections import defaultdict
from copy import copy
from pathlib import Path
from typing import Iterable

import openpyxl


COLUMNS = {
    "action": 4,
    "distance": 5,
    "orientation": 6,
    "shot_result": 7,
    "data_valid": 8,
    "notes": 13,
}
HEADER_ROW = 9
FIRST_DATA_ROW = 10

VALUE_LABELS = {
    "action": {
        "staticSimulation": "静止模拟投篮",
        "shot": "投篮",
        "rhythmVariation": "变化节奏",
        "stanceVariation": "变化站姿",
        "freeVariation": "自由变化组投篮",
        "freeTest": "自由测试",
    },
    "distance": {
        "noBall": "无球",
        "close": "近距离",
        "mid": "中距离",
        "three": "三分",
        "free": "自由",
    },
    "orientation": {
        "facingBasket": "正对篮筐",
        "side": "侧身",
        "free": "自由朝向",
    },
    "shot_result": {
        "made": "进",
        "missed": "不进",
        "undecided": "",
    },
    "data_valid": {
        "valid": "有效",
        "invalid": "无效",
        "pending": "待检",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge app-generated shot CSV files into a WPS workbook."
    )
    parser.add_argument("--template", required=True, help="Source WPS .xlsx template")
    parser.add_argument("--csv", nargs="+", required=True, help="One or more app CSV files")
    parser.add_argument("--output", help="Output XLSX path")
    parser.add_argument(
        "--include-abolished",
        action="store_true",
        help="Include sessions marked abolished, hidden by default",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing XLSX")
    return parser.parse_args()


def read_sessions(paths: Iterable[Path]) -> list[dict[str, str]]:
    sessions: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"player_id", "session_id", "session_type", "shot_no"}
            missing = required.difference(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{path}: missing columns: {sorted(missing)}")
            sessions.extend(dict(row) for row in reader if row.get("player_id"))
    return sessions


def group_sessions(rows: Iterable[dict[str, str]]) -> list[list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = row.get("session_id") or "|".join(
            [
                row.get("player_id", ""),
                row.get("session_type", ""),
                row.get("captured_at", ""),
            ]
        )
        grouped[key].append(row)
    return sorted(
        grouped.values(),
        key=lambda session: (
            session[0].get("player_id", ""),
            session[0].get("captured_at", ""),
            session[0].get("session_id", ""),
        ),
    )


def map_value(field: str, value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return VALUE_LABELS.get(field, {}).get(value, value)


def sheet_name_for_session(
    session: list[dict[str, str]],
    workbook,
    planned_names: set[str],
) -> str:
    first = session[0]
    player_id = first["player_id"]
    session_type = first.get("session_type", "standard20")

    if session_type == "standard20" and player_id in workbook.sheetnames:
        return player_id

    if session_type in {"repeat20", "supplementary20"}:
        base = f"{player_id}_S{parse_revision(first):02d}"
    elif session_type == "fatigue":
        existing = {
            name
            for name in workbook.sheetnames
            if name.startswith(f"{player_id}_FATIGUE_")
        }
        existing.update(name for name in planned_names if name.startswith(f"{player_id}_FATIGUE_"))
        index = len(existing) + 1
        base = f"{player_id}_FATIGUE_{index:02d}"
    else:
        base = f"{player_id}_{sanitize_sheet_title(session_type)}"

    return next_available_sheet_name(workbook.sheetnames, planned_names, base)


def parse_revision(session_row: dict[str, str]) -> int:
    session_id = session_row.get("session_id", "")
    for part in reversed(session_id.split("-")):
        if part.startswith("r") and part[1:].isdigit():
            return int(part[1:])
    return 1


def sanitize_sheet_title(value: str) -> str:
    invalid = set("[]:*?/\\")
    cleaned = "".join("_" if char in invalid else char for char in value)
    return cleaned[:31] or "SESSION"


def next_available_sheet_name(
    existing: Iterable[str],
    planned: set[str],
    base: str,
) -> str:
    occupied = set(existing).union(planned)
    base = sanitize_sheet_title(base)
    if base not in occupied:
        return base
    for index in range(2, 100):
        suffix = f"_{index:02d}"
        candidate = sanitize_sheet_title(base[: 31 - len(suffix)] + suffix)
        if candidate not in occupied:
            return candidate
    raise RuntimeError(f"Unable to allocate worksheet name for {base}")


def copy_template_sheet(workbook, title: str):
    source_name = "001" if "001" in workbook.sheetnames else next(
        (name for name in workbook.sheetnames if name != "说明"),
        workbook.sheetnames[0],
    )
    sheet = workbook.copy_worksheet(workbook[source_name])
    sheet.title = title
    sheet["A1"] = f"球员 {title.split('_')[0]} 投篮采集临时记录"
    sheet["B5"] = title.split("_")[0]
    return sheet


def ensure_capacity(sheet, last_shot_no: int, target_valid_count: int) -> None:
    required_shot_no = max(last_shot_no, target_valid_count, 20)
    capacity = max(0, sheet.max_row - HEADER_ROW)
    if capacity >= required_shot_no:
        return
    style_row = FIRST_DATA_ROW
    for shot_no in range(capacity + 1, required_shot_no + 1):
        row = HEADER_ROW + shot_no
        for column in range(1, 14):
            target = sheet.cell(row=row, column=column)
            template = sheet.cell(row=style_row, column=column)
            target._style = copy(template._style)
        sheet.cell(row=row, column=1).value = shot_no
        sheet.cell(row=row, column=2).value = f"capture_{shot_no:03d}.csv"


def clear_session_rows(sheet, target_valid_count: int, last_shot_no: int) -> None:
    ensure_capacity(sheet, last_shot_no, target_valid_count)
    for shot_no in range(1, max(last_shot_no, target_valid_count) + 1):
        row = HEADER_ROW + shot_no
        for column in COLUMNS.values():
            sheet.cell(row=row, column=column).value = None


def apply_session(
    workbook,
    session: list[dict[str, str]],
    planned_names: set[str],
    include_abolished: bool = False,
) -> str:
    first = session[0]
    player_id = first["player_id"]
    status = first.get("session_status", "").strip()

    if player_id == "000" or first.get("is_test", "").lower() == "true":
        raise ValueError("test session is excluded from the official workbook")
    if status in {"abolished", "已废除"} and not include_abolished:
        raise ValueError("abolished session is excluded by default")

    title = sheet_name_for_session(session, workbook, planned_names)
    if title in workbook.sheetnames:
        sheet = workbook[title]
    else:
        sheet = copy_template_sheet(workbook, title)
        planned_names.add(title)

    target_valid_count = int(first.get("target_valid_count") or 0)
    last_shot_no = max(int(row.get("shot_no") or 0) for row in session)
    clear_session_rows(sheet, target_valid_count, last_shot_no)

    seen: set[int] = set()
    for row in session:
        shot_no = int(row.get("shot_no") or 0)
        if shot_no < 1:
            continue
        if shot_no in seen:
            raise ValueError(f"duplicate shot_no {shot_no} in {first['session_id']}")
        seen.add(shot_no)
        excel_row = HEADER_ROW + shot_no
        for field, column in COLUMNS.items():
            sheet.cell(row=excel_row, column=column).value = map_value(field, row.get(field, ""))

    return title


def output_path(template_path: Path, requested: str | None) -> Path:
    if requested:
        return Path(requested).resolve()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return template_path.with_name(f"{template_path.stem}_merged_{stamp}.xlsx")


def main() -> int:
    args = parse_args()
    template_path = Path(args.template).resolve()
    csv_paths = [Path(path).resolve() for path in args.csv]
    rows = read_sessions(csv_paths)
    sessions = group_sessions(rows)

    workbook = openpyxl.load_workbook(template_path)
    planned_names: set[str] = set()
    applied: list[tuple[str, str, int]] = []
    skipped: list[tuple[str, str, str]] = []

    for session in sessions:
        first = session[0]
        try:
            title = apply_session(workbook, session, planned_names, args.include_abolished)
            applied.append((first["player_id"], title, len(session)))
        except ValueError as error:
            skipped.append((first.get("player_id", ""), first.get("session_id", ""), str(error)))

    destination = output_path(template_path, args.output)
    if not args.dry_run:
        workbook.save(destination)

    for player_id, title, count in applied:
        print(f"APPLIED player={player_id} sheet={title} rows={count}")
    for player_id, session_id, reason in skipped:
        print(f"SKIPPED player={player_id} session={session_id} reason={reason}")
    if args.dry_run:
        print("DRY_RUN no workbook written")
    else:
        print(f"OUTPUT {destination}")
        print(f"SOURCE {template_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
