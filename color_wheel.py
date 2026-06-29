"""Circular HSV colour palette shown on an open palm.

An outer ring of 36 fully-saturated hues (generated with
:func:`colorsys.hsv_to_rgb`) surrounds an inner ring of greyscale swatches.
The palette is a *latch*: an open palm shows it, and it stays up until the user
either makes a fist or picks a colour — so the hand is free to pinch a swatch
without the palette vanishing mid-gesture.
"""

import colorsys
import math

import cv2

from config import (
    FRAME_WIDTH, FRAME_HEIGHT,
    WHEEL_SWATCHES, WHEEL_R_OUTER, WHEEL_R_INNER,
    WHEEL_SWATCH_R, WHEEL_HOVER_PX, WHEEL_INNER_COLORS,
)
from ui_theme import FONT, ACCENT, STROKE, TEXT_DIM


class ColorWheel:
    def __init__(self):
        self.visible = False
        self.center  = (FRAME_WIDTH // 2, FRAME_HEIGHT // 2)
        self.hovered = None                 # index into self.swatches, or None
        self.swatches = []                  # [{"bgr": (b,g,r), "pos": (x,y)}, ...]
        self._build()

    def _build(self):
        cx, cy = self.center

        # Outer ring — full hue spectrum, fully saturated.
        for i in range(WHEEL_SWATCHES):
            ang = 2 * math.pi * i / WHEEL_SWATCHES - math.pi / 2
            r, g, b = colorsys.hsv_to_rgb(i / WHEEL_SWATCHES, 1.0, 1.0)
            self.swatches.append({
                "bgr": (int(b * 255), int(g * 255), int(r * 255)),
                "pos": (int(cx + WHEEL_R_OUTER * math.cos(ang)),
                        int(cy + WHEEL_R_OUTER * math.sin(ang))),
            })

        # Inner ring — white / greys / black.
        n = len(WHEEL_INNER_COLORS)
        for i, bgr in enumerate(WHEEL_INNER_COLORS):
            ang = 2 * math.pi * i / n - math.pi / 2
            self.swatches.append({
                "bgr": tuple(bgr),
                "pos": (int(cx + WHEEL_R_INNER * math.cos(ang)),
                        int(cy + WHEEL_R_INNER * math.sin(ang))),
            })

    # ── state ────────────────────────────────────────────────────────────────
    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False
        self.hovered = None

    # ── interaction ──────────────────────────────────────────────────────────
    def update_hover(self, pt):
        """Record which swatch the index tip is over (nearest within range)."""
        self.hovered = None
        if not self.visible or pt is None:
            return
        best = WHEEL_SWATCH_R + WHEEL_HOVER_PX
        for i, sw in enumerate(self.swatches):
            d = math.hypot(pt[0] - sw["pos"][0], pt[1] - sw["pos"][1])
            if d <= best:
                best = d
                self.hovered = i

    def select(self):
        """Return the hovered swatch's BGR colour, or ``None``."""
        if self.hovered is None:
            return None
        return self.swatches[self.hovered]["bgr"]

    # ── rendering ────────────────────────────────────────────────────────────
    def render(self, frame, active_color=None):
        if not self.visible:
            return

        # Dim disc behind the swatches so they read against any background.
        overlay = frame.copy()
        cv2.circle(overlay, self.center, WHEEL_R_OUTER + WHEEL_SWATCH_R + 16,
                   (16, 14, 12), -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        # Faint guide rings give the two tiers structure.
        cv2.circle(frame, self.center, WHEEL_R_OUTER, STROKE, 1, cv2.LINE_AA)
        cv2.circle(frame, self.center, WHEEL_R_INNER, STROKE, 1, cv2.LINE_AA)

        for sw in self.swatches:
            cv2.circle(frame, sw["pos"], WHEEL_SWATCH_R, sw["bgr"], -1, cv2.LINE_AA)
            cv2.circle(frame, sw["pos"], WHEEL_SWATCH_R, (30, 30, 30), 1, cv2.LINE_AA)

        if self.hovered is not None:
            sw = self.swatches[self.hovered]
            cv2.circle(frame, sw["pos"], WHEEL_SWATCH_R + 6, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.circle(frame, sw["pos"], WHEEL_SWATCH_R + 5, ACCENT, 2, cv2.LINE_AA)

        # Central hub previews the current colour.
        hub = 34
        cx, cy = self.center
        cv2.circle(frame, self.center, hub + 4, (240, 240, 240), 1, cv2.LINE_AA)
        cv2.circle(frame, self.center, hub, tuple(int(c) for c in (active_color or (180, 180, 180))),
                   -1, cv2.LINE_AA)
        cv2.putText(frame, "PINCH TO PICK", (cx - 52, cy + hub + 26),
                    FONT, 0.45, TEXT_DIM, 1, cv2.LINE_AA)
