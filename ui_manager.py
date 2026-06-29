import cv2

from config import (
    COLORS, COLOR_NAMES, SHAPE_TYPES, BRUSH_TYPES,
    UI_BAR_HEIGHT, FRAME_WIDTH, HOVER_CLICK_FRAMES,
)
from ui_theme import (
    FONT, blend, rounded_rect, text_center,
    ACCENT, PANEL_BG, BTN_BG, BTN_HOVER, STROKE, TEXT, TEXT_DIM, RADIUS,
)

# Brushes get abbreviated labels so they fit the standard button width while
# keeping their real value for dispatch.
BRUSH_LABELS = {"calligraphy": "callig"}


class Button:
    def __init__(self, label, x, y, w, h, value=None):
        self.label   = label
        self.rect    = (x, y, w, h)
        self.value   = value if value is not None else label
        self.hovered = False
        self.active  = False

    def contains(self, pt):
        x, y, w, h = self.rect
        return x <= pt[0] <= x + w and y <= pt[1] <= y + h

    def draw(self, frame):
        x, y, w, h = self.rect
        p1, p2 = (x, y), (x + w, y + h)

        if self.active:                                   # accent-tinted, glowing
            rounded_rect(frame, p1, p2, blend(PANEL_BG, ACCENT, 0.30), RADIUS, -1)
            rounded_rect(frame, p1, p2, ACCENT, RADIUS, 2)
            txt = ACCENT
        elif self.hovered:                                # lifted, hinting at accent
            rounded_rect(frame, p1, p2, BTN_HOVER, RADIUS, -1)
            rounded_rect(frame, p1, p2, blend(STROKE, ACCENT, 0.6), RADIUS, 1)
            txt = TEXT
        else:                                             # quiet idle state
            rounded_rect(frame, p1, p2, BTN_BG, RADIUS, -1)
            rounded_rect(frame, p1, p2, STROKE, RADIUS, 1)
            txt = TEXT_DIM

        text_center(frame, self.label, self.rect, txt, 0.44)


class UIManager:
    def __init__(self):
        self.buttons        = []   # shapes, tools and the 3D button
        self.brush_buttons  = []   # brush selectors (highlight by active_brush)
        self.color_swatches = []
        self.captions       = []   # (text, x, baseline_y) group headers
        self.dividers       = []   # (x, y1, y2) thin separators between groups
        self.hover_frames   = {}  # button/swatch value → frames hovered
        self.CLICK_HOLD     = HOVER_CLICK_FRAMES
        self._build()

    def _caption(self, text, x, row_y):
        """Record a small group header and return the x where its items start."""
        self.captions.append((text, x, row_y + 19))
        return x + 58                          # gutter reserved for the caption

    def _divider(self, x, row_y, row_h=28):
        self.dividers.append((x, row_y - 3, row_y + row_h + 3))
        return x + 14

    def _build(self):
        btn_w, btn_h, gap = 80, 28, 6

        # Row 1 — COLOUR swatches
        swatch_size, sgap = 30, 8
        y = 12
        x = self._caption("COLOR", 20, y)
        for name in COLOR_NAMES:
            self.color_swatches.append({
                "name": name,
                "color": COLORS[name],
                "rect": (x, y, swatch_size, swatch_size),
            })
            x += swatch_size + sgap

        # Row 2 — SHAPE buttons, then BRUSH buttons
        y = 50
        x = self._caption("SHAPE", 20, y)
        for shape in SHAPE_TYPES:
            self.buttons.append(Button(shape, x, y, btn_w, btn_h, shape))
            x += btn_w + gap
        x = self._divider(x + 8, y)
        x = self._caption("BRUSH", x, y)
        for brush in BRUSH_TYPES:
            self.brush_buttons.append(
                Button(BRUSH_LABELS.get(brush, brush), x, y, btn_w, btn_h, brush))
            x += btn_w + gap

        # Row 3 — TOOL buttons, then the 3D extrusion trigger
        y = 88
        x = self._caption("TOOL", 20, y)
        for label in ["select", "eraser", "clear", "undo", "redo"]:
            self.buttons.append(Button(label, x, y, btn_w, btn_h, label))
            x += btn_w + gap
        x = self._divider(x + 8, y)
        x = self._caption("FX", x, y)
        self.buttons.append(Button("3D Preview", x, y, 120, btn_h, "extrude3d"))

    def render(self, frame, active_color, active_shape, active_tool, active_brush):
        # Translucent dark bar — blend only the bar region, not the whole frame.
        bar = frame[0:UI_BAR_HEIGHT, 0:FRAME_WIDTH]
        tint = bar.copy()
        tint[:] = PANEL_BG
        cv2.addWeighted(tint, 0.88, bar, 0.12, 0, bar)
        # A thin accent rule grounds the bar against the canvas below it.
        cv2.line(frame, (0, UI_BAR_HEIGHT - 1), (FRAME_WIDTH, UI_BAR_HEIGHT - 1),
                 STROKE, 1, cv2.LINE_AA)
        cv2.line(frame, (0, UI_BAR_HEIGHT), (FRAME_WIDTH, UI_BAR_HEIGHT),
                 ACCENT, 2, cv2.LINE_AA)

        for text, cx, cy in self.captions:
            cv2.putText(frame, text, (cx, cy), FONT, 0.4, TEXT_DIM, 1, cv2.LINE_AA)
        for dx, y1, y2 in self.dividers:
            cv2.line(frame, (dx, y1), (dx, y2), STROKE, 1, cv2.LINE_AA)

        for sw in self.color_swatches:
            x, y, w, h = sw["rect"]
            is_active = tuple(sw["color"]) == tuple(active_color)
            rounded_rect(frame, (x, y), (x + w, y + h), sw["color"], 7, -1)
            if is_active:
                rounded_rect(frame, (x - 2, y - 2), (x + w + 2, y + h + 2), ACCENT, 8, 2)
            else:
                rounded_rect(frame, (x, y), (x + w, y + h), STROKE, 7, 1)

        for btn in self.buttons:
            btn.active = btn.value in (active_shape, active_tool)
            btn.draw(frame)
        for btn in self.brush_buttons:
            btn.active = btn.value == active_brush
            btn.draw(frame)

        # Dwell-progress arc around whatever the cursor is hovering — a faint
        # track plus a bright accent sweep so it reads like a loading ring.
        for value, count in self.hover_frames.items():
            progress = min(count / self.CLICK_HOLD, 1.0)
            if progress <= 0:
                continue
            rect = self._rect_for(value)
            if rect is None:
                continue
            x, y, w, h = rect
            center = (x + w // 2, y + h // 2)
            axes   = (w // 2 + 5, h // 2 + 5)
            # angle=0 with startAngle=-90 sweeps from the top without rotating
            # (and distorting) the ellipse on non-square buttons.
            cv2.ellipse(frame, center, axes, 0, -90, 270,
                        blend(PANEL_BG, ACCENT, 0.30), 2, cv2.LINE_AA)
            cv2.ellipse(frame, center, axes, 0, -90, -90 + int(360 * progress),
                        ACCENT, 2, cv2.LINE_AA)

    def _rect_for(self, value):
        if value.startswith("color_"):
            name = value[len("color_"):]
            for sw in self.color_swatches:
                if sw["name"] == name:
                    return sw["rect"]
        for btn in (*self.buttons, *self.brush_buttons):
            if btn.value == value:
                return btn.rect
        return None

    def get_swatch_at(self, pt):
        for sw in self.color_swatches:
            x, y, w, h = sw["rect"]
            if x <= pt[0] <= x + w and y <= pt[1] <= y + h:
                return sw["name"]
        return None

    def update_hover(self, pt):
        """Call every frame with the cursor point. Returns a triggered action
        string (e.g. "circle", "undo", "color_red") once the dwell completes,
        else None."""
        triggered = None
        hovered_key = None

        for btn in (*self.buttons, *self.brush_buttons):
            btn.hovered = btn.contains(pt)
            if btn.hovered:
                hovered_key = btn.value

        swatch = self.get_swatch_at(pt)
        if swatch:
            hovered_key = f"color_{swatch}"

        # Only the currently hovered control accumulates; everything else decays.
        if hovered_key is not None:
            self.hover_frames[hovered_key] = self.hover_frames.get(hovered_key, 0) + 1
            if self.hover_frames[hovered_key] >= self.CLICK_HOLD:
                self.hover_frames[hovered_key] = 0
                triggered = hovered_key
            for k in self.hover_frames:
                if k != hovered_key:
                    self.hover_frames[k] = 0
        else:
            self.hover_frames.clear()

        return triggered
