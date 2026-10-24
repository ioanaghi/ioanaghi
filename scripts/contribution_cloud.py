"""Render a public GitHub calendar as a self-contained animated SVG."""

import argparse
from datetime import date
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.request import Request, urlopen


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-date" not in attrs or "data-level" not in attrs:
            return
        day = date.fromisoformat(attrs["data-date"])
        level = int(attrs["data-level"])
        if not 0 <= level <= 4:
            raise ValueError("Unexpected contribution level")
        if day in self.days:
            raise ValueError("Duplicate calendar date")
        self.days[day] = level


def render_calendar(source, username):
    parser = CalendarParser()
    parser.feed(source)
    days = sorted(parser.days.items())
    if not 350 <= len(days) <= 371:
        raise ValueError("Incomplete calendar; refusing to publish misleading data")
    first, last = days[0][0], days[-1][0]
    if (last - first).days + 1 != len(days):
        raise ValueError("Calendar dates are not contiguous")
    first_sunday = first.toordinal() - (first.weekday() + 1) % 7
    columns = (last.toordinal() - first_sunday) // 7 + 1
    width, height, left, top = 1000, 285, 48, 128
    pitch = 936 / columns
    size = min(13.5, pitch - 3)
    colors = ["#172333", "#164f3d", "#18754e", "#29a965", "#55d983"]

    def position(day):
        offset = day.toordinal() - first_sunday
        return left + offset // 7 * pitch, top + offset % 7 * 18

    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
<title id="title">{escape(username)} — Cloud Network contribution calendar</title>
<desc id="description">Public GitHub activity from {first.isoformat()} to {last.isoformat()}. Seven rows show weekdays and columns show weeks. Real activity levels remain visible while decorative pulses travel from active days to a cloud. The animation does not add contributions.</desc>
<style>
text{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif}}
.wire{{fill:none;stroke:#31576a;stroke-width:.8;opacity:.3}}
.packet{{fill:none;stroke:#62d9ca;stroke-width:1.6;stroke-linecap:round;stroke-dasharray:5 95;opacity:0;animation:packet 12s linear infinite}}
.beat{{fill:none;stroke:#9ef0dd;stroke-width:1;opacity:0;animation:beat 12s linear infinite}}
@keyframes packet{{0%,4%{{opacity:0;stroke-dashoffset:8}}5%{{opacity:.85}}17%{{opacity:.85;stroke-dashoffset:-100}}18%,100%{{opacity:0;stroke-dashoffset:-100}}}}
@keyframes beat{{0%,3%{{opacity:0}}5%{{opacity:1}}15%{{opacity:.15}}24%,100%{{opacity:0}}}}
@media(prefers-reduced-motion:reduce){{.packet,.beat{{animation:none;opacity:0}}}}
</style>
<rect width="1000" height="285" rx="14" fill="#0b1220"/>
<text x="26" y="30" fill="#8da5be" font-size="12">{escape(username)} / contributions</text>
<text x="26" y="56" fill="#d5e4f1" font-size="18" font-weight="500">Cloud Network</text>''']
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    seen = set()
    previous_label_x = -100
    for day, level in days:
        key = (day.year, day.month)
        if key not in seen:
            seen.add(key)
            x, _ = position(day)
            if x < 960 and x - previous_label_x >= 34:
                svg.append(f'<text x="{x:.2f}" y="115" fill="#8da5be" font-size="11">{months[day.month - 1]}</text>')
                previous_label_x = x
    for row, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        svg.append(f'<text x="14" y="{top + row * 18 + 10}" fill="#8da5be" font-size="11">{label}</text>')
    for day, level in days:
        x, y = position(day)
        svg.append(f'<rect data-date="{day.isoformat()}" data-level="{level}" x="{x:.2f}" y="{y}" width="{size:.2f}" height="{size:.2f}" rx="2" fill="{colors[level]}"><title>{day.isoformat()}: GitHub activity level {level}/4</title></rect>')
    active = [day for day, level in days if level]
    # Spread connection points across the year; never invent active cells.
    indices = sorted({round(i * (len(active) - 1) / 11) for i in range(12)}) if active else []
    for i in indices:
        day = active[i]
        x, y = position(day)
        path = f'M{x + size / 2:.2f},{y + size / 2:.2f} C{x + size / 2:.2f},86 500,86 500,66'
        delay = -indices.index(i) * .94
        svg.append(f'<path class="wire" d="{path}"/>')
        svg.append(f'<path class="packet" d="{path}" pathLength="100" style="animation-delay:{delay:.2f}s"/>')
        svg.append(f'<rect class="beat" x="{x - .7:.2f}" y="{y - .7:.2f}" width="{size + 1.4:.2f}" height="{size + 1.4:.2f}" rx="2" style="animation-delay:{delay:.2f}s"/>')
    svg.append('''<path d="M481 68h39c12 0 19-8 19-17s-8-17-18-17h-1c-5-12-15-18-26-18-15 0-27 10-29 24-9 0-16 6-16 14s6 14 15 14Z" fill="#0b1220" stroke="#62d9ca" stroke-width="2" stroke-linejoin="round"/>
<path d="M500 46v17m-6-6 6 6 6-6" fill="none" stroke="#9ef0dd" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>''')
    svg.append(f'<text x="26" y="265" fill="#8da5be" font-size="11">Public activity · {first.isoformat()} — {last.isoformat()}</text>')
    svg.append('<text x="804" y="265" fill="#8da5be" font-size="11">Less</text>')
    for i, color in enumerate(colors):
        svg.append(f'<rect x="{839 + i * 15}" y="255" width="11" height="11" rx="2" fill="{color}"/>')
    svg.append('<text x="922" y="265" fill="#8da5be" font-size="11">More</text></svg>')
    return "\n".join(svg)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--username", default="ioanaghi")
    cli.add_argument("--input", type=Path, help="Saved GitHub calendar HTML, for offline checks")
    cli.add_argument("--output", type=Path, default=Path("dist/cloud-network.svg"))
    args = cli.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", args.username):
        cli.error("Invalid GitHub username")
    if args.input:
        source = args.input.read_text(encoding="utf-8")
    else:
        request = Request(f"https://github.com/users/{args.username}/contributions", headers={"User-Agent": "GitHub-Contribution-Cloud", "Accept": "text/html"})
        with urlopen(request, timeout=30) as response:
            source = response.read().decode("utf-8")
    svg = render_calendar(source, args.username)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Generated {args.output}")


if __name__ == "__main__":
    main()
