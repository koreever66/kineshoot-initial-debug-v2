# encoding: utf-8

import csv
import html
from pathlib import Path


def make_svg(points):
    width, height, margin = 900, 260, 46
    if not points:
        return '<p>没有遥测数据。</p>'
    xmax = max(point['elapsed_ms'] for point in points) or 1
    values = [point['free_bytes'] / 1048576.0 for point in points]
    ymin, ymax = min(values), max(values)
    if ymin == ymax:
        ymin -= 0.1
        ymax += 0.1
    pad = (ymax - ymin) * 0.08
    ymin -= pad
    ymax += pad
    coords = []
    for point in points:
        x = margin + point['elapsed_ms'] / xmax * (width - margin - 20)
        y = height - margin - (point['free_bytes'] / 1048576.0 - ymin) / (ymax - ymin) * (height - margin - 30)
        coords.append(f'{x:.1f},{y:.1f}')
    return (
        f'<svg viewBox="0 0 {width} {height}">'
        f'<text x="12" y="20" font-size="16" font-weight="700">LittleFS 可用空间</text>'
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-20}" y2="{height-margin}" stroke="#94a3b8"/>'
        f'<line x1="{margin}" y1="30" x2="{margin}" y2="{height-margin}" stroke="#94a3b8"/>'
        f'<polyline fill="none" stroke="#0f766e" stroke-width="2.5" points="{" ".join(coords)}"/>'
        f'<text x="4" y="38" font-size="11">{ymax:.2f} MB</text>'
        f'<text x="4" y="{height-margin}" font-size="11">{ymin:.2f} MB</text>'
        f'<text x="{margin}" y="{height-18}" font-size="12">0s</text>'
        f'<text x="{width-70}" y="{height-18}" font-size="12">{xmax/1000:.1f}s</text>'
        '</svg>'
    )


def build_report(directory):
    directory = Path(directory)
    files = sorted(directory.glob('capture_*.telemetry.csv'))
    if not files:
        return None
    all_rows = []
    charts = []
    table_rows = []
    for path in files:
        with path.open(newline='', encoding='utf-8-sig') as handle:
            points = [{'elapsed_ms': int(row['elapsed_ms']), 'free_bytes': int(row['free_bytes'])} for row in csv.DictReader(handle)]
        capture = path.name.replace('.telemetry.csv', '.csv')
        for point in points:
            all_rows.append({'capture': capture, **point})
        charts.append(make_svg(points))
        values = [point['free_bytes'] / 1048576.0 for point in points]
        table_rows.append(f'<tr><td>{html.escape(capture)}</td><td>{min(values):.3f}</td><td>{max(values):.3f}</td></tr>')
    with (directory / 'session_telemetry.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=['capture', 'elapsed_ms', 'free_bytes'])
        writer.writeheader()
        writer.writerows(all_rows)
    report = """<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>采集内存遥测</title>
    <style>body{font-family:'Microsoft YaHei',sans-serif;margin:24px;color:#172033}.charts{display:grid;grid-template-columns:1fr 1fr;gap:16px}svg{width:100%;border:1px solid #d7e0ea;border-radius:8px;background:#fff}table{border-collapse:collapse;width:100%;margin-top:18px}th,td{border:1px solid #cbd5e1;padding:8px;text-align:center}th{background:#eaf1f8}@media(max-width:900px){.charts{grid-template-columns:1fr}}</style>
    <h1>采集内存可视报告</h1><p>电量不新增任何接线，因此不记录电池电压。</p><div class='charts'>""" + ''.join(charts) + """</div>
    <table><thead><tr><th>采集</th><th>最小可用 MB</th><th>最大可用 MB</th></tr></thead><tbody>""" + ''.join(table_rows) + """</tbody></table></html>"""
    output = directory / 'session_telemetry_report.html'
    output.write_text(report, encoding='utf-8')
    return output


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    args = parser.parse_args()
    result = build_report(args.directory)
    print(result if result else 'No telemetry files found.')
