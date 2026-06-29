"""Shared UI drawing helpers and theme constants.

OpenCV only ships axis-aligned rectangles, so the rounded panels, buttons and
centred labels that give the interface its modern look are built here once and
reused by both the toolbar (:mod:`ui_manager`) and the HUD (:mod:`main`).
"""

import cv2

from config import (
    UI_ACCENT, UI_PANEL_BG, UI_BTN_BG, UI_BTN_HOVER, UI_STROKE,
    UI_TEXT, UI_TEXT_DIM, UI_BTN_RADIUS,
)

FONT = cv2.FONT_HERSHEY_DUPLEX

# Re-export theme colours so callers can `from ui_theme import ...` in one place.
ACCENT, PANEL_BG, BTN_BG, BTN_HOVER = UI_ACCENT, UI_PANEL_BG, UI_BTN_BG, UI_BTN_HOVER
STROKE, TEXT, TEXT_DIM, RADIUS = UI_STROKE, UI_TEXT, UI_TEXT_DIM, UI_BTN_RADIUS


def blend(c1, c2, t):
    """Linear blend from ``c1`` to ``c2`` by ``t`` in [0, 1]."""
    return tuple(int(a * (1 - t) + b * t) for a, b in zip(c1, c2))


def rounded_rect(img, p1, p2, color, radius=RADIUS, thickness=-1):
    """Filled (thickness < 0) or stroked rounded rectangle, anti-aliased."""
    x1, y1 = p1
    x2, y2 = p2
    r = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    lt = cv2.LINE_AA

    if thickness < 0:
        cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, -1, lt)
        cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, -1, lt)
        for cx, cy in ((x1 + r, y1 + r), (x2 - r, y1 + r),
                       (x1 + r, y2 - r), (x2 - r, y2 - r)):
            cv2.circle(img, (cx, cy), r, color, -1, lt)
    else:
        cv2.line(img, (x1 + r, y1), (x2 - r, y1), color, thickness, lt)
        cv2.line(img, (x1 + r, y2), (x2 - r, y2), color, thickness, lt)
        cv2.line(img, (x1, y1 + r), (x1, y2 - r), color, thickness, lt)
        cv2.line(img, (x2, y1 + r), (x2, y2 - r), color, thickness, lt)
        cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness, lt)
        cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness, lt)
        cv2.ellipse(img, (x1 + r, y2 - r), (r, r),  90, 0, 90, color, thickness, lt)
        cv2.ellipse(img, (x2 - r, y2 - r), (r, r),   0, 0, 90, color, thickness, lt)


def translucent_panel(img, p1, p2, color=PANEL_BG, alpha=0.78, radius=RADIUS,
                      border=None):
    """Blend a rounded panel over the frame so text stays readable on any
    background. Optionally outline it with ``border``."""
    x1, y1 = p1
    x2, y2 = p2
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return
    overlay = img.copy()
    rounded_rect(overlay, (x1, y1), (x2, y2), color, radius, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    if border is not None:
        rounded_rect(img, (x1, y1), (x2, y2), border, radius, 1)


def text_size(text, scale=0.5, thickness=1):
    (tw, th), _ = cv2.getTextSize(text, FONT, scale, thickness)
    return tw, th


def text_center(img, text, box, color, scale=0.5):
    """Draw ``text`` centred inside ``box`` = (x, y, w, h)."""
    x, y, w, h = box
    tw, th = text_size(text, scale)
    cv2.putText(img, text, (x + (w - tw) // 2, y + (h + th) // 2),
                FONT, scale, color, 1, cv2.LINE_AA)
