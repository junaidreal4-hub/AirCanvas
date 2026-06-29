"""Brush engine — five stroke styles drawn onto the raster canvas.

Every brush exposes the same signature::

    fn(layer, prev, point, color, size)

where ``layer`` is the BGR canvas (mutated in place), ``prev`` is the previous
stroke sample (``None`` at the start of a stroke), ``point`` is the current
sample, ``color`` is a BGR tuple and ``size`` is the brush diameter in pixels.

Keeping each brush as a small pure function makes them trivial to test and to
extend; :class:`BrushEngine.stroke` just dispatches on the brush name.
"""

import math
import random

import cv2
import numpy as np

from config import (
    MARKER_OPACITY, SPRAY_DENSITY, SPRAY_RADIUS_FACTOR,
    CALLIGRAPHY_NIB_RATIO, NEON_BLUR_KERNEL, NEON_CORE_BOOST,
)


def _pen(layer, prev, point, color, size):
    """Solid anti-aliased line — the default opaque brush."""
    if prev:
        cv2.line(layer, prev, point, color, size, cv2.LINE_AA)
    else:
        cv2.circle(layer, point, max(1, size // 2), color, -1, cv2.LINE_AA)


def _marker(layer, prev, point, color, size):
    """Semi-transparent highlighter — the new segment is blended at 60%.

    Only the freshly drawn pixels are blended (everything else in ``overlay``
    equals ``layer`` and survives the weighting unchanged), so existing strokes
    keep their colour and overlapping marker passes build up naturally.
    """
    overlay = layer.copy()
    _pen(overlay, prev, point, color, size)
    cv2.addWeighted(overlay, MARKER_OPACITY, layer, 1 - MARKER_OPACITY, 0, layer)


def _spray(layer, prev, point, color, size):
    """Airbrush — scatter random single-pixel dots around the cursor."""
    radius = max(2, int(size * SPRAY_RADIUS_FACTOR))
    count  = max(4, int(size * SPRAY_DENSITY))
    for _ in range(count):
        ang = random.uniform(0, 2 * math.pi)
        rad = random.uniform(0, radius)
        x = int(point[0] + rad * math.cos(ang))
        y = int(point[1] + rad * math.sin(ang))
        cv2.circle(layer, (x, y), 1, color, -1)


def _calligraphy(layer, prev, point, color, size):
    """Flat-nib pen — a rotated ellipse whose long axis follows the stroke.

    Ellipses are stamped along the segment so fast hand movements stay
    continuous instead of leaving gaps.
    """
    major = max(2, size)
    minor = max(1, int(size * CALLIGRAPHY_NIB_RATIO))

    if not prev:
        cv2.ellipse(layer, point, (major, minor), 0, 0, 360, color, -1, cv2.LINE_AA)
        return

    dx, dy = point[0] - prev[0], point[1] - prev[1]
    angle  = math.degrees(math.atan2(dy, dx))
    steps  = max(1, int(math.hypot(dx, dy) / 2))
    for i in range(steps + 1):
        t = i / steps
        cx = int(prev[0] + dx * t)
        cy = int(prev[1] + dy * t)
        cv2.ellipse(layer, (cx, cy), (major, minor), angle, 0, 360, color, -1, cv2.LINE_AA)


def _neon(layer, prev, point, color, size):
    """Glowing neon — an additive gaussian-blurred halo with a bright core.

    The blur runs on a small ROI around the segment rather than the whole
    frame, so the effect stays cheap even at full resolution.
    """
    h, w = layer.shape[:2]
    p0 = prev if prev else point
    pad = NEON_BLUR_KERNEL + size * 2

    xs = sorted((p0[0], point[0]))
    ys = sorted((p0[1], point[1]))
    x1, y1 = max(0, xs[0] - pad), max(0, ys[0] - pad)
    x2, y2 = min(w, xs[1] + pad), min(h, ys[1] + pad)
    if x2 <= x1 or y2 <= y1:
        return

    glow = np.zeros((y2 - y1, x2 - x1, 3), dtype=np.uint8)
    a = (p0[0] - x1, p0[1] - y1)
    b = (point[0] - x1, point[1] - y1)
    cv2.line(glow, a, b, color, max(2, size * 2), cv2.LINE_AA)

    k = NEON_BLUR_KERNEL | 1                       # gaussian needs an odd kernel
    glow = cv2.GaussianBlur(glow, (k, k), 0)

    roi = layer[y1:y2, x1:x2]
    cv2.add(roi, glow, roi)                        # additive halo (saturating)

    bright = tuple(min(255, c + NEON_CORE_BOOST) for c in color)
    cv2.line(layer, p0, point, bright, max(1, size // 2), cv2.LINE_AA)


_BRUSHES = {
    "pen":         _pen,
    "marker":      _marker,
    "spray":       _spray,
    "calligraphy": _calligraphy,
    "neon":        _neon,
}


class BrushEngine:
    """Stateless dispatcher: pick a brush by name and stamp one segment."""

    @staticmethod
    def stroke(layer, brush, prev, point, color, size):
        _BRUSHES.get(brush, _pen)(layer, prev, point, color, size)
