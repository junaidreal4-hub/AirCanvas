import os
import sys
import time

import cv2
import numpy as np

from config import (
    WINDOW_NAME, FRAME_WIDTH, FRAME_HEIGHT,
    COLORS, BRUSH_TYPES, DEFAULT_BRUSH_TYPE,
    UI_BAR_HEIGHT, DEFAULT_BRUSH, MIN_BRUSH, MAX_BRUSH,
    FIST_CLEAR_SECONDS, PALM_HOLD_SECONDS, CANVAS_FADE_FRAMES,
    WHITE_CANVAS_BG, SAVE_DIR, UI_DANGER, UI_ACCENT_WARM,
)
from ui_theme import (
    FONT, blend, rounded_rect, translucent_panel, text_size,
    ACCENT, PANEL_BG, STROKE, TEXT, TEXT_DIM,
)
from gesture_engine import GestureEngine
from shape_layer    import ShapeLayer
from canvas_layer   import CanvasLayer
from ui_manager     import UIManager
from color_wheel    import ColorWheel

SHAPE_ACTIONS = {"freehand", "rectangle", "circle", "line", "triangle"}
BRUSH_ACTIONS = set(BRUSH_TYPES)


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
    frame, the white sheet, or black when exporting)."""
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
    radius = 7 if is_drawing else 9
    cv2.circle(frame, point, radius, color, -1, cv2.LINE_AA)
    border = ACCENT if is_drawing else (255, 255, 255)
    cv2.circle(frame, point, radius + 3, border, 2 if is_drawing else 1, cv2.LINE_AA)


def draw_size_feedback(frame, point, color, brush, tool):
    """Feature 4 — a semi-transparent preview disc at the fingertip plus a
    vertical fill bar on the left edge, both reflecting the current brush size.
    Shown only while a drawing tool is active."""
    radius = brush * 3 if tool == "eraser" else brush
    if point is not None:
        overlay = frame.copy()
        cv2.circle(overlay, point, max(radius, 2), color, -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.30, frame, 0.70, 0, frame)
        cv2.circle(frame, point, max(radius, 2), color, 1, cv2.LINE_AA)

    # Vertical fill bar on the left edge, kept clear of the HUD card below.
    bx, bw = 22, 14
    top, bot = UI_BAR_HEIGHT + 26, FRAME_HEIGHT - 140
    frac = min(1.0, max(0.0, (brush - MIN_BRUSH) / max(1, MAX_BRUSH - MIN_BRUSH)))
    fill = int((bot - top) * frac)
    rounded_rect(frame, (bx, top), (bx + bw, bot), blend(PANEL_BG, (255, 255, 255), 0.08), 6, -1)
    if fill > 0:
        rounded_rect(frame, (bx, bot - fill), (bx + bw, bot), color, 6, -1)
    rounded_rect(frame, (bx, top), (bx + bw, bot), STROKE, 6, 1)
    txt = f"{brush}px"
    tw, _ = text_size(txt, 0.4)
    cv2.putText(frame, txt, (bx + bw // 2 - tw // 2, top - 9),
                FONT, 0.4, TEXT_DIM, 1, cv2.LINE_AA)


def _progress_ring(frame, center, radius, progress, color, thickness=4):
    """A faint full track with a bright sweep on top — a clean loading ring."""
    cx, cy = center
    cv2.ellipse(frame, (cx, cy), (radius, radius), 0, -90, 270,
                blend(PANEL_BG, color, 0.30), thickness, cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy), (radius, radius), 0, -90, -90 + int(360 * progress),
                color, thickness, cv2.LINE_AA)


def _caption_pill(frame, text, center_x, y, color):
    """A small rounded label used under the progress rings."""
    tw, th = text_size(text, 0.5)
    x1, x2 = center_x - tw // 2 - 12, center_x + tw // 2 + 12
    translucent_panel(frame, (x1, y), (x2, y + th + 14), alpha=0.7, border=color)
    cv2.putText(frame, text, (center_x - tw // 2, y + th + 4),
                FONT, 0.5, color, 1, cv2.LINE_AA)


def draw_fist_progress(frame, progress):
    cx, cy = FRAME_WIDTH // 2, FRAME_HEIGHT // 2
    _progress_ring(frame, (cx, cy), 52, progress, UI_DANGER, 4)
    _caption_pill(frame, "HOLD TO CLEAR", cx, cy + 66, UI_DANGER)


def draw_palm_progress(frame, point, progress):
    """Dwell ring for the open-palm canvas-mode flip."""
    if point is None:
        return
    cx, cy = point
    _progress_ring(frame, (cx, cy), 36, progress, UI_ACCENT_WARM, 3)
    _caption_pill(frame, "FLIP CANVAS", cx, cy - 64, UI_ACCENT_WARM)


def draw_hud(frame, tool, shape, brush_type, color_bgr, brush, mode, fps):
    h, w = frame.shape[:2]
    label = tool if tool != "draw" else f"{shape} / {brush_type}"
    line1 = f"{label.upper()}    brush {brush}px    {mode} canvas    {fps:4.1f} fps"
    line2 = "H help    S save    ESC quit"

    tw1, _ = text_size(line1, 0.5)
    tw2, _ = text_size(line2, 0.42)
    pw = max(tw1, tw2) + 28
    x1, y2 = 14, h - 12
    y1 = y2 - 58
    translucent_panel(frame, (x1, y1), (x1 + pw, y2), border=STROKE)
    cv2.putText(frame, line2, (x1 + 14, y1 + 22), FONT, 0.42, TEXT_DIM, 1, cv2.LINE_AA)
    cv2.putText(frame, line1, (x1 + 14, y1 + 46), FONT, 0.5, TEXT, 1, cv2.LINE_AA)

    # Current-colour chip, bottom-right.
    chip = tuple(int(c) for c in color_bgr)
    cs, cx2, cy2 = 36, w - 16, h - 12
    rounded_rect(frame, (cx2 - cs, cy2 - cs), (cx2, cy2), chip, 9, -1)
    rounded_rect(frame, (cx2 - cs, cy2 - cs), (cx2, cy2), (240, 240, 240), 9, 1)


HELP_LINES = [
    "AirCanvas Pro - gesture controls",
    "",
    "Right hand, index finger only ....... draw / interact",
    "Right hand, hover a button 0.6s ..... click it",
    "Right hand, open palm ............... show colour wheel",
    "Right hand, hold open palm 0.8s ..... flip white <-> air canvas",
    "  (over the wheel) pinch a swatch ... pick that colour",
    "Right hand, hold a fist 2s .......... clear everything",
    "Left hand, pinch distance ........... brush size",
    "Both hands pinch + spread ........... resize selected shape",
    "",
    "Keys:  D draw   E eraser   X select   C recolor   1-5 brush",
    "       M canvas mode   V 3D preview",
    "       Z undo   Y redo   DEL delete   S save   H help   ESC quit",
]


def draw_help(frame):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    # A centred card holds the cheat sheet so it floats above the canvas.
    cw, ch = 760, len(HELP_LINES) * 30 + 60
    cx1 = FRAME_WIDTH // 2 - cw // 2
    cy1 = FRAME_HEIGHT // 2 - ch // 2
    translucent_panel(frame, (cx1, cy1), (cx1 + cw, cy1 + ch),
                      color=PANEL_BG, alpha=0.92, radius=16, border=ACCENT)

    x = cx1 + 40
    y = cy1 + 56
    for i, line in enumerate(HELP_LINES):
        if i == 0:
            cv2.putText(frame, line, (x, y), FONT, 0.85, ACCENT, 1, cv2.LINE_AA)
            cv2.line(frame, (x, y + 12), (cx1 + cw - 40, y + 12), STROKE, 1, cv2.LINE_AA)
            y += 44
        else:
            cv2.putText(frame, line, (x, y), FONT, 0.55, TEXT, 1, cv2.LINE_AA)
            y += 30


def main():
    cap = open_camera()
    if cap is None:
        print("ERROR: could not open a webcam. Plug one in and try again.")
        return

    gestures = GestureEngine()
    canvas   = CanvasLayer()
    shapes   = ShapeLayer()
    ui       = UIManager()
    wheel    = ColorWheel()

    active_color = COLORS["red"]            # BGR tuple, not a name
    active_shape = "freehand"
    active_tool  = "draw"
    active_brush = DEFAULT_BRUSH_TYPE
    brush_size   = DEFAULT_BRUSH

    was_drawing     = False
    shape_started   = False
    dragging        = False
    prev_both_pinch = False
    fist_start_time = None
    palm_start_time = None
    palm_latched    = False
    show_help       = False

    canvas_white = False                    # False = air (camera), True = white sheet
    mode_blend   = 0.0                       # animated 0..1 toward the target mode
    white_full   = np.full((FRAME_HEIGHT, FRAME_WIDTH, 3), WHITE_CANVAS_BG, dtype=np.uint8)

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

        # Overlay state collected during input handling, drawn after compositing
        # (so it survives the white-canvas background swap).
        cursor_pt      = dh.index_tip
        cursor_drawing = dh.drawing
        size_hand_pt   = None
        show_size_fb   = False
        fist_progress  = None
        palm_progress  = None

        # ── Left hand — brush size via pinch distance ─────────────────────
        if sh.index_tip and not gestures.both_pinching:
            dist       = max(5, min(sh.pinch_dist, 150))
            brush_size = int(MIN_BRUSH + (1 - dist / 150) * (MAX_BRUSH - MIN_BRUSH))
            size_hand_pt = sh.index_tip

        # ── Two-hand pinch — resize selected shape ────────────────────────
        if gestures.both_pinching:
            if not prev_both_pinch:
                shapes.begin_transform()
            if shapes.selected:
                shapes.scale_selected(two_hand_delta)
        prev_both_pinch = gestures.both_pinching

        # ── Right hand open palm — show wheel + flip-canvas dwell ──────────
        if dh.index_tip and dh.open_palm:
            wheel.show()
            canvas.reset_stroke()
            if palm_start_time is None:
                palm_start_time = time.time()
            held = time.time() - palm_start_time
            palm_progress = min(held / PALM_HOLD_SECONDS, 1.0)
            if held >= PALM_HOLD_SECONDS and not palm_latched:
                canvas_white = not canvas_white   # start the fade to the other mode
                palm_latched = True
        else:
            palm_start_time = None
            palm_latched    = False

        # ── Fist — hold to clear (suppressed while the wheel is up) ────────
        if dh.fist and not wheel.visible:
            if fist_start_time is None:
                fist_start_time = time.time()
            elapsed = time.time() - fist_start_time
            fist_progress = min(elapsed / FIST_CLEAR_SECONDS, 1.0)
            if elapsed >= FIST_CLEAR_SECONDS:
                canvas.clear()
                shapes.clear()
                fist_start_time = None
        else:
            fist_start_time = None

        # ── Colour wheel interaction (while visible) ──────────────────────
        if wheel.visible:
            was_drawing = shape_started = dragging = False
            canvas.reset_stroke()
            shapes.discard_active()
            wheel.update_hover(dh.index_tip)
            if dh.fist:
                wheel.hide()
            elif dh.pinching and wheel.hovered is not None:
                active_color = wheel.select()
                if active_tool == "select":
                    shapes.recolor_selected(active_color)
                wheel.hide()

        # ── Right hand — main interaction (only when the wheel is hidden) ──
        elif dh.index_tip and not dh.fist and not dh.open_palm:
            cursor = dh.index_tip

            if cursor[1] < UI_BAR_HEIGHT:
                canvas.reset_stroke()
                shapes.discard_active()
                shape_started = was_drawing = False

                action = ui.update_hover(cursor)
                if action:
                    if action.startswith("color_"):
                        active_color = COLORS[action[len("color_"):]]
                        if active_tool == "select":
                            shapes.recolor_selected(active_color)
                    elif action in SHAPE_ACTIONS:
                        active_shape, active_tool = action, "draw"
                    elif action in BRUSH_ACTIONS:
                        active_brush, active_tool = action, "draw"
                    elif action == "extrude3d":
                        canvas.extrude_3d()
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
                            canvas.draw(cursor, active_color, brush_size, active_brush)
                        else:
                            canvas.reset_stroke()
                    else:
                        if started_drawing:
                            shapes.start_shape(active_shape, cursor,
                                               active_color, brush_size)
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
                if active_tool in ("draw", "eraser"):
                    show_size_fb = True
        else:
            canvas.reset_stroke()
            was_drawing = shape_started = False
            shapes.discard_active()

        # ── Animate the canvas-mode cross-fade ────────────────────────────
        target = 1.0 if canvas_white else 0.0
        step   = 1.0 / CANVAS_FADE_FRAMES
        if   mode_blend < target: mode_blend = min(target, mode_blend + step)
        elif mode_blend > target: mode_blend = max(target, mode_blend - step)

        if   mode_blend <= 0.001: background = frame
        elif mode_blend >= 0.999: background = white_full
        else: background = cv2.addWeighted(white_full, mode_blend, frame, 1.0 - mode_blend, 0)

        # ── Compose final frame, then draw overlays on top ────────────────
        output = composite(canvas, shapes, background=background)
        ui.render(output, active_color, active_shape, active_tool, active_brush)
        wheel.render(output, active_color)

        if size_hand_pt is not None:
            draw_cursor(output, size_hand_pt, (150, 150, 150), False)
        if show_size_fb:
            draw_size_feedback(output, cursor_pt, active_color, brush_size, active_tool)
        if cursor_pt is not None:
            cur_color = (255, 255, 255) if wheel.visible else active_color
            draw_cursor(output, cursor_pt, cur_color, cursor_drawing and not wheel.visible)
        if fist_progress is not None:
            draw_fist_progress(output, fist_progress)
        if palm_progress is not None:
            draw_palm_progress(output, cursor_pt, palm_progress)

        mode_label = "white" if canvas_white else "air"
        draw_hud(output, active_tool, active_shape, active_brush,
                 active_color, brush_size, mode_label, fps)
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
            export_bg = white_full if canvas_white else None
            cv2.imwrite(path, composite(canvas, shapes, background=export_bg))
            print(f"Saved {path}")
        elif key == ord('e'):
            active_tool = "eraser"
        elif key == ord('d'):
            active_tool = "draw"
        elif key == ord('x'):
            active_tool = "select"
        elif key == ord('c'):
            shapes.recolor_selected(active_color)
        elif key == ord('m'):
            canvas_white = not canvas_white
        elif key == ord('v'):
            canvas.extrude_3d()
        elif key in (ord('1'), ord('2'), ord('3'), ord('4'), ord('5')):
            active_brush = BRUSH_TYPES[key - ord('1')]
            active_tool  = "draw"
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
