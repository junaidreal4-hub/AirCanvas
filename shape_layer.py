import copy

import cv2
import numpy as np

from config import HISTORY_LIMIT


class Shape:
    def __init__(self, shape_type, start, color, thickness):
        self.shape_type = shape_type
        self.start      = start
        self.end        = start
        self.color      = color
        self.thickness  = thickness
        self.points     = [start]

    def update_end(self, point):
        self.end = point
        if self.shape_type == "freehand":
            self.points.append(point)

    def get_bbox(self):
        if self.shape_type == "freehand":
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            return min(xs), min(ys), max(xs), max(ys)
        x1, x2 = sorted((self.start[0], self.end[0]))
        y1, y2 = sorted((self.start[1], self.end[1]))
        return x1, y1, x2, y2

    def contains_point(self, pt, margin=20):
        x1, y1, x2, y2 = self.get_bbox()
        return (x1 - margin) <= pt[0] <= (x2 + margin) and \
               (y1 - margin) <= pt[1] <= (y2 + margin)

    def move(self, dx, dy):
        self.start  = (self.start[0] + dx, self.start[1] + dy)
        self.end    = (self.end[0] + dx,   self.end[1] + dy)
        self.points = [(p[0] + dx, p[1] + dy) for p in self.points]

    def scale(self, factor):
        x1, y1, x2, y2 = self.get_bbox()
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        def scale_pt(pt):
            return (int(cx + (pt[0] - cx) * factor),
                    int(cy + (pt[1] - cy) * factor))

        self.start  = scale_pt(self.start)
        self.end    = scale_pt(self.end)
        self.points = [scale_pt(p) for p in self.points]

    def render(self, canvas):
        t, c = self.thickness, self.color

        if self.shape_type == "freehand":
            if len(self.points) > 1:
                pts = np.array(self.points, np.int32)
                cv2.polylines(canvas, [pts], False, c, t, cv2.LINE_AA)

        elif self.shape_type == "rectangle":
            cv2.rectangle(canvas, self.start, self.end, c, t, cv2.LINE_AA)

        elif self.shape_type == "circle":
            cx = (self.start[0] + self.end[0]) // 2
            cy = (self.start[1] + self.end[1]) // 2
            rx = abs(self.end[0] - self.start[0]) // 2
            ry = abs(self.end[1] - self.start[1]) // 2
            cv2.ellipse(canvas, (cx, cy), (max(rx, 1), max(ry, 1)),
                        0, 0, 360, c, t, cv2.LINE_AA)

        elif self.shape_type == "line":
            cv2.line(canvas, self.start, self.end, c, t, cv2.LINE_AA)

        elif self.shape_type == "triangle":
            cx = (self.start[0] + self.end[0]) // 2
            pts = np.array([
                [cx,            self.start[1]],
                [self.start[0], self.end[1]],
                [self.end[0],   self.end[1]],
            ], np.int32)
            cv2.polylines(canvas, [pts], True, c, t, cv2.LINE_AA)


class ShapeLayer:
    """Vector layer: keeps Shape objects and renders them to a transparent
    BGR layer. Committed shapes are cached and only re-rendered when the
    scene changes (dirty flag), so a static drawing costs almost nothing."""

    def __init__(self):
        self.shapes      = []
        self.active      = None
        self.selected    = None
        self.drag_offset = (0, 0)
        self.history     = []
        self.redo_stack  = []
        self._cache      = None
        self._dirty      = True
        self._pending    = False  # lazily snapshot on the first move/scale

    # ── history ─────────────────────────────────────────────────────────────
    def save_snapshot(self):
        self.history.append(copy.deepcopy(self.shapes))
        self.redo_stack.clear()
        if len(self.history) > HISTORY_LIMIT:
            self.history.pop(0)

    def undo(self):
        if self.history:
            self.redo_stack.append(copy.deepcopy(self.shapes))
            self.shapes   = self.history.pop()
            self.selected = self.active = None
            self._dirty   = True

    def redo(self):
        if self.redo_stack:
            self.history.append(copy.deepcopy(self.shapes))
            self.shapes   = self.redo_stack.pop()
            self.selected = self.active = None
            self._dirty   = True

    def clear(self):
        if self.shapes:
            self.save_snapshot()
        self.shapes   = []
        self.selected = self.active = None
        self._dirty   = True

    # ── drawing new shapes ──────────────────────────────────────────────────
    def start_shape(self, shape_type, point, color, thickness):
        self.save_snapshot()
        self.active = Shape(shape_type, point, color, thickness)

    def update_active(self, point):
        if self.active:
            self.active.update_end(point)

    def commit_active(self):
        if self.active:
            self.shapes.append(self.active)
            self.active = None
            self._dirty = True

    def discard_active(self):
        self.active = None

    # ── selection & transforms ───────────────────────────────────────────────
    def pick_shape(self, point):
        for shape in reversed(self.shapes):
            if shape.contains_point(point):
                self.selected    = shape
                self.drag_offset = (point[0] - shape.start[0],
                                    point[1] - shape.start[1])
                self._pending    = True  # snapshot on first actual move
                return True
        return False

    def deselect(self):
        self.selected = None

    def _ensure_snapshot(self):
        """Save one undo snapshot at the start of a transform gesture."""
        if self._pending:
            self.save_snapshot()
            self._pending = False

    def begin_transform(self):
        """Mark that a fresh transform gesture (e.g. resize) is starting."""
        if self.selected:
            self._pending = True

    def drag_selected(self, point):
        if not self.selected:
            return
        self._ensure_snapshot()
        new_x = point[0] - self.drag_offset[0]
        new_y = point[1] - self.drag_offset[1]
        self.selected.move(new_x - self.selected.start[0],
                           new_y - self.selected.start[1])
        self._dirty = True

    def scale_selected(self, delta):
        if self.selected and abs(delta) > 1:
            self._ensure_snapshot()
            self.selected.scale(1 + max(-0.1, min(0.1, delta * 0.01)))
            self._dirty = True

    def recolor_selected(self, color):
        if self.selected and self.selected.color != color:
            self.save_snapshot()
            self.selected.color = color
            self._dirty = True

    def delete_selected(self):
        if self.selected in self.shapes:
            self.save_snapshot()
            self.shapes.remove(self.selected)
            self.selected = None
            self._dirty   = True

    # ── rendering ─────────────────────────────────────────────────────────────
    def render(self, width, height):
        if self._cache is None or self._cache.shape[:2] != (height, width):
            self._cache = np.zeros((height, width, 3), dtype=np.uint8)
            self._dirty = True

        if self._dirty:
            self._cache[:] = 0
            for shape in self.shapes:
                shape.render(self._cache)
            self._dirty = False

        # The selection box and the in-progress shape change every frame, so
        # they are drawn on a throwaway copy rather than baked into the cache.
        layer = self._cache.copy()
        if self.active:
            self.active.render(layer)
        if self.selected:
            x1, y1, x2, y2 = self.selected.get_bbox()
            cv2.rectangle(layer, (x1 - 5, y1 - 5), (x2 + 5, y2 + 5),
                          (0, 255, 255), 1, cv2.LINE_AA)
        return layer
