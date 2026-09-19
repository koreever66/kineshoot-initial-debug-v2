# encoding: utf-8
"""Render a readable 2D motion-trajectory PNG from one IMU capture CSV."""

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import build_motion_report as motion_report


WIDTH = 1800
HEIGHT = 1120
BACKGROUND = "#eef3f6"
SURFACE = "#ffffff"
INK = "#17232d"
MUTED = "#607180"
GRID = "#dfe8ec"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render vertical and horizontal 2D trajectory projections."
    )
    parser.add_argument("csv_file")
    parser.add_argument("--output", help="Output PNG path")
    parser.add_argument("--title", help="Optional report title")
    return parser.parse_args()


def load_font(size, bold=False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def normalize_plane(points):
    if not points:
        return []
    origin_x, origin_y = points[0]
    shifted = [[point[0] - origin_x, point[1] - origin_y] for point in points]
    min_x = min(point[0] for point in shifted)
    max_x = max(point[0] for point in shifted)
    min_y = min(point[1] for point in shifted)
    max_y = max(point[1] for point in shifted)
    span = max(max_x - min_x, max_y - min_y, 1e-9)
    scale = 100.0 / span
    return [[point[0] * scale, point[1] * scale] for point in shifted]


def trajectory_color(fraction):
    stops = [
        (46, 111, 214),
        (11, 143, 114),
        (215, 123, 37),
        (201, 75, 85),
        (118, 86, 201),
    ]
    scaled = max(0.0, min(0.999999, fraction)) * (len(stops) - 1)
    index = int(scaled)
    blend = scaled - index
    start = stops[index]
    end = stops[min(index + 1, len(stops) - 1)]
    return tuple(
        round(start[channel] + (end[channel] - start[channel]) * blend)
        for channel in range(3)
    )


def draw_arrow(draw, start, end, color, width=2):
    draw.line([start, end], fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    length = 10
    draw.line(
        [
            end,
            (
                end[0] - length * math.cos(angle - 0.5),
                end[1] - length * math.sin(angle - 0.5),
            ),
        ],
        fill=color,
        width=width,
    )
    draw.line(
        [
            end,
            (
                end[0] - length * math.cos(angle + 0.5),
                end[1] - length * math.sin(angle + 0.5),
            ),
        ],
        fill=color,
        width=width,
    )


def draw_panel(
    draw,
    box,
    points,
    force_points,
    sample_fractions,
    title,
    xlabel,
    ylabel,
    font_title,
    font_label,
):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=10, fill=SURFACE, outline="#d5e0e6", width=2)
    draw.text((x0 + 22, y0 + 16), title, fill=INK, font=font_title)
    draw.text(
        (x0 + 22, y0 + 49),
        "单 IMU 示意投影，仅用于形状对比",
        fill=MUTED,
        font=font_label,
    )

    padding = {"left": 86, "right": 34, "top": 118, "bottom": 74}
    plot_left = x0 + padding["left"]
    plot_top = y0 + padding["top"]
    plot_right = x1 - padding["right"]
    plot_bottom = y1 - padding["bottom"]
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    range_x = max(1e-6, max_x - min_x)
    range_y = max(1e-6, max_y - min_y)
    pad_x = max(4.0, range_x * 0.12)
    pad_y = max(4.0, range_y * 0.12)
    min_x -= pad_x
    max_x += pad_x
    min_y -= pad_y
    max_y += pad_y
    scale = min(plot_width / (max_x - min_x), plot_height / (max_y - min_y))
    used_width = (max_x - min_x) * scale
    used_height = (max_y - min_y) * scale
    offset_x = plot_left + (plot_width - used_width) * 0.5
    offset_y = plot_top + (plot_height - used_height) * 0.5

    def map_point(point):
        x = offset_x + (point[0] - min_x) * scale
        y = offset_y + plot_height - (point[1] - min_y) * scale
        return x, y

    for index in range(6):
        fraction = index / 5
        x = plot_left + plot_width * fraction
        y = plot_top + plot_height * fraction
        draw.line([(x, plot_top), (x, plot_bottom)], fill=GRID, width=1)
        draw.line([(plot_left, y), (plot_right, y)], fill=GRID, width=1)

    total = max(1, len(points) - 1)
    for index in range(1, len(points)):
        start = map_point(points[index - 1])
        end = map_point(points[index])
        draw.line(
            [start, end],
            fill=trajectory_color((index - 1) / total),
            width=3,
        )

    max_force = max(
        (math.hypot(force[0], force[1]) for force in force_points),
        default=1.0,
    )
    max_force = max(max_force, 1.0)
    for index in sample_fractions:
        point = points[index]
        force = force_points[index]
        magnitude = math.hypot(force[0], force[1])
        if magnitude < 1.0:
            continue
        origin = map_point(point)
        length = 18 + 34 * min(1.0, magnitude / max_force)
        direction = (force[0] / magnitude, -force[1] / magnitude)
        end = (
            origin[0] + direction[0] * length,
            origin[1] + direction[1] * length,
        )
        draw_arrow(draw, origin, end, "#33444f", width=2)

    start = map_point(points[0])
    end = map_point(points[-1])
    draw.ellipse(
        [start[0] - 9, start[1] - 9, start[0] + 9, start[1] + 9],
        fill="#0b8f72",
        outline=SURFACE,
        width=3,
    )
    draw.ellipse(
        [end[0] - 9, end[1] - 9, end[0] + 9, end[1] + 9],
        fill="#c94b55",
        outline=SURFACE,
        width=3,
    )
    draw.text(
        (plot_right - 220, plot_bottom + 38),
        xlabel,
        fill=MUTED,
        font=font_label,
    )
    draw.text(
        (x0 + 22, y0 + 82),
        ylabel,
        fill=MUTED,
        font=font_label,
    )


def main():
    args = parse_args()
    csv_path = Path(args.csv_file).resolve()
    rows, timestamps_us = motion_report.load_csv(csv_path)
    derived = motion_report.derive_motion(rows, timestamps_us)
    metrics = motion_report.quality_metrics(
        rows,
        timestamps_us,
        derived,
        argparse.Namespace(
            gap_ms=motion_report.DEFAULT_GAP_MS,
            acc_limit_mg=motion_report.DEFAULT_ACC_LIMIT_MG,
            gyro_limit_dps=motion_report.DEFAULT_GYRO_LIMIT_DPS,
        ),
    )

    linear = derived["linear_world_mg"]
    delta_times = derived["delta_times"]
    time_s = derived["time_s"]
    vertical_acceleration = [point[2] for point in linear]
    filtered_vertical = motion_report.highpass(
        vertical_acceleration,
        motion_report.HIGHPASS_SECONDS,
        derived["sample_rate_hz"],
    )
    vertical_velocity = motion_report.anchor_endpoint(
        motion_report.integrate(filtered_vertical, delta_times),
        time_s,
    )
    vertical_position = motion_report.anchor_endpoint(
        motion_report.integrate(vertical_velocity, delta_times),
        time_s,
    )

    vertical_points = normalize_plane(
        [
            [derived["position_m"][index][0], vertical_position[index]]
            for index in range(len(time_s))
        ]
    )
    horizontal_points = normalize_plane(
        [
            [derived["position_m"][index][0], derived["position_m"][index][1]]
            for index in range(len(time_s))
        ]
    )
    vertical_forces = [
        [linear[index][0], linear[index][2]] for index in range(len(time_s))
    ]
    horizontal_forces = [
        [linear[index][0], linear[index][1]] for index in range(len(time_s))
    ]
    sample_fractions = list(
        range(0, len(time_s), max(1, round(len(time_s) / 20)))
    )

    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    font_title = load_font(34, bold=True)
    font_subtitle = load_font(20)
    font_metric = load_font(22, bold=True)
    font_metric_label = load_font(17)
    font_panel = load_font(24, bold=True)
    font_label = load_font(17)

    title = args.title or csv_path.stem
    draw.text((42, 26), title, fill=INK, font=font_title)
    draw.text(
        (42, 70),
        "基于 IMU 数据的二维运动轨迹",
        fill=MUTED,
        font=font_subtitle,
    )

    metric_items = [
        ("采集时长", f"{metrics['duration_s']:.3f} 秒"),
        ("采样率", f"{metrics['sample_rate_hz']:.2f} Hz"),
        ("加速度峰值", f"{metrics['accel_peak_mg']:.0f} mg"),
        ("陀螺仪峰值", f"{metrics['gyro_peak_dps']:.1f} dps"),
        ("采样缺口", str(metrics["gap_count"])),
    ]
    metric_x = 760
    for label, value in metric_items:
        draw.rounded_rectangle(
            [metric_x, 28, metric_x + 180, 98],
            radius=8,
            fill=SURFACE,
            outline="#d5e0e6",
            width=2,
        )
        draw.text((metric_x + 14, 39), label, fill=MUTED, font=font_metric_label)
        draw.text((metric_x + 14, 62), value, fill=INK, font=font_metric)
        metric_x += 194

    draw_panel(
        draw,
        (36, 130, 1190, 1030),
        vertical_points,
        vertical_forces,
        sample_fractions,
        "垂直投影",
        "世界 X 轴（示意单位）",
        "世界 Z 轴（示意单位）",
        font_panel,
        font_label,
    )
    draw_panel(
        draw,
        (1212, 130, 1764, 1030),
        horizontal_points,
        horizontal_forces,
        sample_fractions,
        "水平投影",
        "世界 X 轴（示意单位）",
        "世界 Y 轴（示意单位）",
        font_panel,
        font_label,
    )

    output_path = (
        Path(args.output).resolve()
        if args.output
        else csv_path.with_name(f"{csv_path.stem}_motion_trajectory.png")
    )
    image.save(output_path)
    print(f"Trajectory image: {output_path}")


if __name__ == "__main__":
    main()
