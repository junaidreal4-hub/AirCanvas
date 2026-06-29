import cv2
import numpy as np

from config import FRAME_WIDTH, FRAME_HEIGHT, HISTORY_LIMIT


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

    def draw(self, point, color, size):
        if self.prev_point:
            cv2.line(self.layer, self.prev_point, point, color, size, cv2.LINE_AA)
        else:
            # First sample of a stroke — drop a dot so single taps register.
            cv2.circle(self.layer, point, max(1, size // 2), color, -1, cv2.LINE_AA)
        self.prev_point = point

    def erase(self, point, size):
        cv2.circle(self.layer, point, size * 3, (0, 0, 0), -1)
        self.prev_point = None

    def reset_stroke(self):
        self.prev_point = None

    def clear(self):
        self.layer[:] = 0
        self.prev_point = None

    def get(self):
        return self.layer
