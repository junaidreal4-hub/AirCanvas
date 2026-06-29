import cv2
import numpy as np

from config import (
    FRAME_WIDTH, FRAME_HEIGHT, HISTORY_LIMIT,
    EXTRUDE_OFFSET, EXTRUDE_DARKEN, EXTRUDE_APPROX_EPS, EXTRUDE_MIN_AREA,
)
from brush_engine import BrushEngine


class CanvasLayer:
    """Raster layer for freehand pixel strokes — the eraser lives here too."""

    def __init__(self):
        self.layer      = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
        self.prev_point = None
        self.history    = []
        self.redo_stack = []

    def save_snapshot(self):
        self.history.append(self.layer.copy())
        self.redo_stack.clear()
        if len(self.history) > HISTORY_LIMIT:
            self.history.pop(0)

    def undo(self):
        if self.history:
            self.redo_stack.append(self.layer.copy())
            self.layer = self.history.pop()

    def redo(self):
        if self.redo_stack:
            self.history.append(self.layer.copy())
            self.layer = self.redo_stack.pop()

    def draw(self, point, color, size, brush="pen"):
        # The brush engine handles the dot-on-first-sample case internally.
        BrushEngine.stroke(self.layer, brush, self.prev_point, point, color, size)
        self.prev_point = point

    def erase(self, point, size):
        cv2.circle(self.layer, point, size * 3, (0, 0, 0), -1)
        self.prev_point = None

    def reset_stroke(self):
        self.prev_point = None

    def clear(self):
        self.layer[:] = 0
        self.prev_point = None

    def extrude_3d(self):
        """Give the raster drawing a pseudo-3D look.

        Trace the painted shapes, push a darker copy of each down-and-right,
        wall in the gap between the original and the offset outline, then lay
        the original artwork back on top. The whole thing is one undoable edit.
        """
        gray = cv2.cvtColor(self.layer, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 8, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [c for c in contours if cv2.contourArea(c) >= EXTRUDE_MIN_AREA]
        if not contours:
            return

        self.save_snapshot()
        original  = self.layer.copy()
        extrusion = np.zeros_like(self.layer)
        h, w      = self.layer.shape[:2]
        d         = EXTRUDE_OFFSET

        for cnt in contours:
            eps    = EXTRUDE_APPROX_EPS * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True).reshape(-1, 2)
            if len(approx) < 2:
                continue

            # Shade = the shape's own colour, darkened. Sample a vertex that
            # actually sits on a painted pixel.
            sample = original[min(approx[0][1], h - 1), min(approx[0][0], w - 1)]
            dark   = tuple(int(c * EXTRUDE_DARKEN) for c in sample.tolist())

            offset = approx + (d, d)
            cv2.fillPoly(extrusion, [offset.astype(np.int32)], dark)   # back face
            for i in range(len(approx)):                               # side walls
                j = (i + 1) % len(approx)
                quad = np.array([approx[i], approx[j], offset[j], offset[i]], np.int32)
                cv2.fillPoly(extrusion, [quad], dark)

        # Original artwork sits on top of its own shadow.
        keep = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY) > 8
        extrusion[keep] = original[keep]
        self.layer = extrusion
        self.prev_point = None

    def get(self):
        return self.layer
