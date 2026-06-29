import cv2

from config import (
    COLORS, COLOR_NAMES, SHAPE_TYPES,
    UI_BAR_HEIGHT, FRAME_WIDTH, HOVER_CLICK_FRAMES,
)


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
        base_color = (50, 50, 50)
        if self.active:
            base_color = (80, 180, 80)
        elif self.hovered:
            base_color = (80, 80, 80)

        cv2.rectangle(frame, (x, y), (x + w, y + h), base_color, -1)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (120, 120, 120), 1)
        cv2.putText(frame, self.label, (x + 6, y + h - 8),
                    cv2.FONT_HERSHEY_DUPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)


class UIManager:
    def __init__(self):
        self.buttons        = []
        self.color_swatches = []
        self.hover_frames   = {}  # button/swatch value → frames hovered
        self.CLICK_HOLD     = HOVER_CLICK_FRAMES
        self._build()

    def _build(self):
        # Row 1 — colour swatches
        swatch_size, gap = 32, 8
        start_x, y = 20, 12
        for name in COLOR_NAMES:
            self.color_swatches.append({
                "name": name,
                "color": COLORS[name],
                "rect": (start_x, y, swatch_size, swatch_size),
            })
            start_x += swatch_size + gap

        # Row 2 — shape buttons
        btn_w, btn_h = 80, 28
        bx, by = 20, 56
        for shape in SHAPE_TYPES:
            self.buttons.append(Button(shape, bx, by, btn_w, btn_h, shape))
            bx += btn_w + 6

        # Row 2 — tool buttons
        bx += 20
        for label in ["select", "eraser", "clear", "undo", "redo"]:
            self.buttons.append(Button(label, bx, by, btn_w, btn_h, label))
            bx += btn_w + 6

    def render(self, frame, active_color, active_shape, active_tool):
        # Translucent dark bar — blend only the bar region, not the whole frame.
        bar = frame[0:UI_BAR_HEIGHT, 0:FRAME_WIDTH]
        tint = bar.copy()
        tint[:] = (18, 18, 18)
        cv2.addWeighted(tint, 0.85, bar, 0.15, 0, bar)
        cv2.line(frame, (0, UI_BAR_HEIGHT), (FRAME_WIDTH, UI_BAR_HEIGHT), (60, 60, 60), 1)

        for sw in self.color_swatches:
            x, y, w, h = sw["rect"]
            is_active = sw["name"] == active_color
            cv2.rectangle(frame, (x, y), (x + w, y + h), sw["color"], -1)
            border    = (255, 255, 255) if is_active else (80, 80, 80)
            thickness = 2 if is_active else 1
            cv2.rectangle(frame, (x - 1, y - 1), (x + w + 1, y + h + 1), border, thickness)

        for btn in self.buttons:
            btn.active = btn.value in (active_shape, active_tool)
            btn.draw(frame)

        # Dwell-progress arc around whatever the cursor is hovering.
        for value, count in self.hover_frames.items():
            progress = min(count / self.CLICK_HOLD, 1.0)
            if progress <= 0:
                continue
            rect = self._rect_for(value)
            if rect is None:
                continue
            x, y, w, h = rect
            cv2.ellipse(frame, (x + w // 2, y + h // 2),
                        (w // 2 + 4, h // 2 + 4),
                        -90, 0, int(360 * progress), (0, 220, 180), 2)

    def _rect_for(self, value):
        if value.startswith("color_"):
            name = value[len("color_"):]
            for sw in self.color_swatches:
                if sw["name"] == name:
                    return sw["rect"]
        for btn in self.buttons:
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

        for btn in self.buttons:
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
