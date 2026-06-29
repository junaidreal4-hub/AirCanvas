import os
import sys
import time

import cv2
import numpy as np

from config import (
    WINDOW_NAME, FRAME_WIDTH, FRAME_HEIGHT,
    COLORS, UI_BAR_HEIGHT, DEFAULT_BRUSH, MIN_BRUSH, MAX_BRUSH,
    FIST_CLEAR_SECONDS, SAVE_DIR,
)
from gesture_engine import GestureEngine
from shape_layer    import ShapeLayer
from canvas_layer   import CanvasLayer
from ui_manager     import UIManager

SHAPE_ACTIONS = {"freehand", "rectangle", "circle", "line", "triangle"}


def open_camera():
    """Open the default webcam, preferring the DirectShow backend on Windows
    (much faster to initialise). Returns an opened VideoCapture or None."""
    backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if sys.platform == "win32" else [cv2.CAP_ANY]
    for backend in backends:
        cap = cv2.VideoCapture(0, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            return cap
        cap.release()
    return None


def composite(canvas, shapes, background=None):
    """Stack the raster canvas and vector layer onto a background (the webcam
    frame, or black when exporting)."""
    if background is None:
        result = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    else:
        result = background.copy()

    for layer in (canvas.get(), shapes.render(FRAME_WIDTH, FRAME_HEIGHT)):
        mask = layer.any(axis=2)            # any non-black pixel belongs to the layer
        result[mask] = layer[mask]
    return result


def draw_cursor(frame, point, color, is_drawing):
    if point is None:
        return
    radius = 8 if is_drawing else 10
    cv2.circle(frame, point, radius, color, -1)
    border = (0, 255, 100) if is_drawing else (255, 255, 255)
    cv2.circle(frame, point, radius + 2, border, 1, cv2.LINE_AA)


def draw_brush_preview(frame, point, color, brush):
    """Ring showing the current brush diameter next to the cursor."""
    if point is None:
        return
    cv2.circle(frame, point, max(brush, 2), color, 1, cv2.LINE_AA)


def draw_fist_progress(frame, progress):
    cx, cy = FRAME_WIDTH // 2, FRAME_HEIGHT // 2
    cv2.ellipse(frame, (cx, cy), (50, 50), -90, 0, int(360 * progress), (0, 80, 255), 4)
    cv2.putText(frame, "HOLD TO CLEAR", (cx - 80, cy + 80),
                cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 80, 255), 1, cv2.LINE_AA)


def draw_hud(frame, tool, shape, color_name, brush, fps):
    h, w = frame.shape[:2]
    label = tool if tool != "draw" else f"draw ({shape})"
    info  = f"Tool: {label}   Brush: {brush}   FPS: {fps:4.1f}"
    cv2.putText(frame, info, (20, h - 15),
                cv2.FONT_HERSHEY_DUPLEX, 0.55, (160, 160, 160), 1, cv2.LINE_AA)
    cv2.putText(frame, "H: help   S: save   ESC: quit", (20, h - 40),
                cv2.FONT_HERSHEY_DUPLEX, 0.45, (110, 110, 110), 1, cv2.LINE_AA)
    cv2.circle(frame, (w - 40, h - 20), 12, COLORS[color_name], -1)
    cv2.circle(frame, (w - 40, h - 20), 14, (255, 255, 255), 1)


HELP_LINES = [
    "AirCanvas Pro - gesture controls",
    "",
    "Right hand, index finger only ....... draw / interact",
    "Right hand, hover a button 0.6s ..... click it",
    "Right hand, hold a fist 2s .......... clear everything",
    "Left hand, pinch distance ........... brush size",
    "Both hands pinch + spread ........... resize selected shape",
    "",
    "Keys:  D draw   E eraser   X select   C recolor selection",
    "       Z undo   Y redo   DEL delete   S save   H help   ESC quit",
]


def draw_help(frame):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    y = FRAME_HEIGHT // 2 - len(HELP_LINES) * 16
    for i, line in enumerate(HELP_LINES):
        scale = 0.85 if i == 0 else 0.6
        color = (0, 220, 180) if i == 0 else (230, 230, 230)
        cv2.putText(frame, line, (FRAME_WIDTH // 2 - 360, y),
                    cv2.FONT_HERSHEY_DUPLEX, scale, color, 1, cv2.LINE_AA)
        y += 36 if i == 0 else 30


def main():
    cap = open_camera()
    if cap is None:
        print("ERROR: could not open a webcam. Plug one in and try again.")
        return

    gestures = GestureEngine()
    canvas   = CanvasLayer()
    shapes   = ShapeLayer()
    ui       = UIManager()

    active_color = "red"
    active_shape = "freehand"
    active_tool  = "draw"
    brush_size   = DEFAULT_BRUSH

    was_drawing     = False
    shape_started   = False
    dragging        = False
    prev_both_pinch = False
    fist_start_time = None
    show_help       = False

    fps, last_t = 0.0, time.perf_counter()

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, FRAME_WIDTH, FRAME_HEIGHT)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: lost the camera feed.")
            break

        frame = cv2.flip(frame, 1)
        if frame.shape[1] != FRAME_WIDTH or frame.shape[0] != FRAME_HEIGHT:
            frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        two_hand_delta = gestures.process(rgb)
        dh = gestures.draw_hand   # user's right hand on screen
        sh = gestures.size_hand   # user's left hand on screen

        # ── Left hand — brush size via pinch distance ─────────────────────
        if sh.index_tip and not gestures.both_pinching:
            dist       = max(5, min(sh.pinch_dist, 150))
            brush_size = int(MIN_BRUSH + (1 - dist / 150) * (MAX_BRUSH - MIN_BRUSH))
            draw_cursor(frame, sh.index_tip, (150, 150, 150), False)

        # ── Two-hand pinch — resize selected shape ────────────────────────
        if gestures.both_pinching:
            if not prev_both_pinch:
                shapes.begin_transform()
            if shapes.selected:
                shapes.scale_selected(two_hand_delta)
        prev_both_pinch = gestures.both_pinching

        # ── Right hand fist — hold to clear ───────────────────────────────
        if dh.fist:
            if fist_start_time is None:
                fist_start_time = time.time()
            elapsed = time.time() - fist_start_time
            draw_fist_progress(frame, min(elapsed / FIST_CLEAR_SECONDS, 1.0))
            if elapsed >= FIST_CLEAR_SECONDS:
                canvas.clear()
                shapes.clear()
                fist_start_time = None
        else:
            fist_start_time = None

        # ── Right hand — main interaction ─────────────────────────────────
        if dh.index_tip and not dh.fist:
            cursor = dh.index_tip

            if cursor[1] < UI_BAR_HEIGHT:
                canvas.reset_stroke()
                shapes.discard_active()
                shape_started = was_drawing = False

                action = ui.update_hover(cursor)
                if action:
                    if action.startswith("color_"):
                        active_color = action[len("color_"):]
                        if active_tool == "select":
                            shapes.recolor_selected(COLORS[active_color])
                    elif action in SHAPE_ACTIONS:
                        active_shape, active_tool = action, "draw"
                    elif action == "select":
                        active_tool = "select"
                    elif action == "eraser":
                        active_tool = "eraser"
                    elif action == "clear":
                        canvas.clear()
                        shapes.clear()
                    elif action == "undo":
                        canvas.undo()
                        shapes.undo()
                    elif action == "redo":
                        canvas.redo()
                        shapes.redo()
            else:
                ui.update_hover((-1, -1))
                currently_drawing = dh.drawing
                started_drawing   = currently_drawing and not was_drawing
                stopped_drawing   = not currently_drawing and was_drawing

                if active_tool == "eraser":
                    if currently_drawing:
                        canvas.erase(cursor, brush_size)
                    else:
                        canvas.reset_stroke()

                elif active_tool == "draw":
                    if active_shape == "freehand":
                        if currently_drawing:
                            if started_drawing:
                                canvas.save_snapshot()
                            canvas.draw(cursor, COLORS[active_color], brush_size)
                        else:
                            canvas.reset_stroke()
                    else:
                        if started_drawing:
                            shapes.start_shape(active_shape, cursor,
                                               COLORS[active_color], brush_size)
                            shape_started = True
                        elif currently_drawing and shape_started:
                            shapes.update_active(cursor)
                        elif stopped_drawing and shape_started:
                            shapes.commit_active()
                            shape_started = False

                elif active_tool == "select":
                    if started_drawing:
                        dragging = shapes.pick_shape(cursor)
                        if not dragging:
                            shapes.deselect()
                    elif currently_drawing and dragging:
                        shapes.drag_selected(cursor)
                    elif stopped_drawing:
                        dragging = False

                was_drawing = currently_drawing

            draw_cursor(frame, cursor, COLORS[active_color], dh.drawing)
            if active_tool in ("draw", "eraser") and cursor[1] >= UI_BAR_HEIGHT:
                preview = brush_size * 3 if active_tool == "eraser" else brush_size
                draw_brush_preview(frame, cursor, COLORS[active_color], preview)
        else:
            canvas.reset_stroke()
            was_drawing = shape_started = False
            shapes.discard_active()

        # ── Compose final frame ───────────────────────────────────────────
        output = composite(canvas, shapes, background=frame)
        ui.render(output, active_color, active_shape, active_tool)
        draw_hud(output, active_tool, active_shape, active_color, brush_size, fps)
        if show_help:
            draw_help(output)

        # Smoothed FPS
        now = time.perf_counter()
        dt  = now - last_t
        last_t = now
        if dt > 0:
            fps = 0.9 * fps + 0.1 * (1.0 / dt)

        cv2.imshow(WINDOW_NAME, output)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:                       # ESC
            break
        elif key == ord('s'):
            os.makedirs(SAVE_DIR, exist_ok=True)
            path = os.path.join(SAVE_DIR, time.strftime("drawing_%Y%m%d_%H%M%S.png"))
            cv2.imwrite(path, composite(canvas, shapes))
            print(f"Saved {path}")
        elif key == ord('e'):
            active_tool = "eraser"
        elif key == ord('d'):
            active_tool = "draw"
        elif key == ord('x'):
            active_tool = "select"
        elif key == ord('c'):
            shapes.recolor_selected(COLORS[active_color])
        elif key in (8, 127):               # Backspace / Delete
            shapes.delete_selected()
        elif key == ord('z'):
            canvas.undo()
            shapes.undo()
        elif key == ord('y'):
            canvas.redo()
            shapes.redo()
        elif key == ord('h'):
            show_help = not show_help

    cap.release()
    gestures.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
