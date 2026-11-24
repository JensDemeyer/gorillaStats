"""Builds static/js/muscle-figure.js: a gorilla-proportioned muscle figure for the app.

The muscle outlines come from react-native-body-highlighter by Hicham Elabbassi (MIT License,
https://github.com/HichamELBSI/react-native-body-highlighter). They are warped here to gorilla proportions:
a broad, high-shouldered upper body, long thick arms, short legs and bigger hands and feet. The head is drawn
by hand in static/js/muscles.js.

Needs `pip install svgelements` and an internet connection; the app itself does not need either.
Usage: python tools/build_muscle_figure.py
"""

import json
import re
import urllib.request
from pathlib import Path

from svgelements import Close, CubicBezier, Line, Move, Path as SvgPath, QuadraticBezier

SOURCE = "https://raw.githubusercontent.com/HichamELBSI/react-native-body-highlighter/main/assets/"
OUTPUT = Path(__file__).resolve().parent.parent / "static" / "js" / "muscle-figure.js"
CENTER = {"front": 364.1, "back": 1083.7 - 724}
ARM = {"biceps", "triceps", "forearm", "hands"}
SKIP = {"head", "hair"}

# Gorilla proportions
CHEST_WIDTH = 1.3          # shoulders, chest and arms
HIP_WIDTH = 1.2            # waist and legs
LEG_SQUASH = 0.62          # legs are short
LEG_FROM = 700
ARM_STRETCH = 1.2          # arms are long
ARM_FROM = 400
ARM_PULL = 0.3             # arms hang closer to the body
HAND_SCALE = 1.4
FOOT_SCALE = 1.25


def fetch(name):
    with urllib.request.urlopen(SOURCE + name) as response:
        return response.read().decode("utf-8")


def parse_ts(text):
    parts = {}
    for block in re.split(r"\n\s*\{\s*\n\s*slug:", text)[1:]:
        slug = re.match(r'\s*"([^"]+)"', block).group(1)
        entry = parts.setdefault(slug, [])
        for side in ("left", "right", "common"):
            match = re.search(side + r":\s*\[(.*?)\],", block, re.S)
            if match:
                entry.extend(re.findall(r'"([^"]+)"', match.group(1)))
    return parts


def width_at(y):
    """Horizontal scale of the torso: widest at the chest, narrower at the waist."""
    points = [(250, 1.0), (330, CHEST_WIDTH), (450, CHEST_WIDTH), (LEG_FROM, HIP_WIDTH)]
    if y <= points[0][0]:
        return points[0][1]
    for (y0, s0), (y1, s1) in zip(points, points[1:]):
        if y <= y1:
            return s0 + (s1 - s0) * (y - y0) / (y1 - y0)
    return HIP_WIDTH


def squash(y):
    return y if y <= LEG_FROM else LEG_FROM + (y - LEG_FROM) * LEG_SQUASH


def warp(slug, view, x, y):
    dx = x - (724 if view == "back" else 0) - CENTER[view]
    if slug in ARM:
        out_y = y if y <= ARM_FROM else ARM_FROM + (y - ARM_FROM) * ARM_STRETCH
        out_x = dx * CHEST_WIDTH
        if y > ARM_FROM:
            out_x -= (1 if dx > 0 else -1) * ARM_PULL * (y - ARM_FROM)
        return out_x, out_y
    if slug == "trapezius" and view == "front":
        return dx * 1.9, 311 - (311 - y) * 2.0
    return dx * (HIP_WIDTH if y > LEG_FROM else width_at(y)), squash(y)


def warp_path(slug, view, d):
    path = SvgPath(d)
    path.approximate_arcs_with_cubics()
    segments = []
    for segment in path:
        if isinstance(segment, Move):
            segments.append(("M", [warp(slug, view, segment.end.x, segment.end.y)]))
        elif isinstance(segment, Line):
            segments.append(("L", [warp(slug, view, segment.end.x, segment.end.y)]))
        elif isinstance(segment, QuadraticBezier):
            segments.append(("Q", [warp(slug, view, p.x, p.y) for p in (segment.control, segment.end)]))
        elif isinstance(segment, CubicBezier):
            segments.append(("C", [warp(slug, view, p.x, p.y) for p in (segment.control1, segment.control2, segment.end)]))
        elif isinstance(segment, Close):
            segments.append(("Z", []))
    return segments


def scale_group(shapes, factor):
    """Scales every shape of one side (left or right hand/foot) around its own centre."""
    for side in (-1, 1):
        points = [p for shape in shapes if shape["side"] == side for _, pts in shape["segments"] for p in pts]
        if not points:
            continue
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        for shape in shapes:
            if shape["side"] == side:
                shape["segments"] = [(c, [(cx + (x - cx) * factor, cy + (y - cy) * factor) for x, y in pts])
                                     for c, pts in shape["segments"]]


def to_d(segments):
    return "".join(c + " ".join(f"{x:.1f} {y:.1f}" for x, y in pts) for c, pts in segments)


def build():
    figure = {}
    for view, name in (("front", "bodyFront.ts"), ("back", "bodyBack.ts")):
        parts = parse_ts(fetch(name))
        shapes = []
        for slug, paths in parts.items():
            if slug in SKIP:
                continue
            for d in paths:
                segments = warp_path(slug, view, d)
                xs = [p[0] for _, pts in segments for p in pts]
                shapes.append({"slug": slug, "segments": segments, "side": 1 if sum(xs) / len(xs) > 0 else -1})
        for slug, factor in (("hands", HAND_SCALE), ("feet", FOOT_SCALE)):
            scale_group([s for s in shapes if s["slug"] == slug], factor)
        figure[view] = shapes
    points = [p for shapes in figure.values() for s in shapes for _, pts in s["segments"] for p in pts]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return figure, {"minX": min(xs), "maxX": max(xs), "minY": min(ys), "maxY": max(ys)}


def main():
    figure, bounds = build()
    data = {view: [{"s": s["slug"], "d": to_d(s["segments"])} for s in shapes] for view, shapes in figure.items()}
    data["bounds"] = {key: round(value, 1) for key, value in bounds.items()}
    OUTPUT.write_text(
        "// Generated by tools/build_muscle_figure.py - do not edit by hand.\n"
        "// Muscle outlines: react-native-body-highlighter, Copyright (c) 2022 Hicham Elabbassi, MIT License,\n"
        "// https://github.com/HichamELBSI/react-native-body-highlighter, reshaped to gorilla proportions.\n"
        "const MUSCLE_FIGURE = " + json.dumps(data, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"{OUTPUT} {OUTPUT.stat().st_size} bytes, bounds {data['bounds']}")


if __name__ == "__main__":
    main()
