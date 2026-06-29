# AirCanvas Pro — Handoff

## Stack
- Python 3.11 (strict), MediaPipe 0.10.30+ (Tasks API only, NO mp.solutions), OpenCV, NumPy
- Model file: `hand_landmarker.task` in project root

## Structure
```
├── main.py           # entry point, main loop, state, hotkeys, HUD
├── config.py         # all constants
├── gesture_engine.py # MediaPipe VIDEO-mode detection, pinch, finger states
├── shape_layer.py    # Shape objects + ShapeLayer (cached render, transforms, undo)
├── canvas_layer.py   # raster freehand canvas + eraser + undo
├── ui_manager.py     # toolbar, color swatches, dwell-to-click buttons
├── hand_landmarker.task
├── README.md / requirements.txt / .gitignore / LICENSE
```

## Key Logic
- Camera flipped (cv2.flip): MediaPipe "Left" = user's RIGHT hand = draw_hand
- MediaPipe "Right" = user's LEFT hand = size_hand
- Detection runs in VIDEO running mode via `detect_for_video(img, timestamp_ms)`
- Pinch hysteresis: ON <40px, OFF >60px (prevents flicker)
- EMA smoothing on all cursor positions (SMOOTHING=0.35)
- Two render layers: CanvasLayer (raster) + ShapeLayer (vector, cached); composited
  each frame with a single-pass `layer.any(axis=2)` mask
- ShapeLayer caches committed shapes and only re-renders on a dirty flag;
  selection box + active shape drawn on a per-frame copy

## Gestures
| Gesture | Action |
|---|---|
| Right hand index finger only | Draw / interact |
| Right hand fist held 2s | Clear canvas |
| Left hand pinch distance | Brush size (wide=big) |
| Both hands pinch + spread | Resize selected shape |
| Hover UI button ~0.6s | Trigger click |

## Keyboard
ESC quit, S save, D draw, E eraser, X select, C recolor selection,
DEL/Backspace delete selection, Z undo, Y redo, H help overlay

## Done
- Freehand + 5 shape types (rect, circle, line, triangle, freehand)
- 10 colors, eraser, brush size, undo/redo (both layers independent)
- Drag shapes, two-hand resize, fist-clear with countdown arc
- Hover-click UI, save canvas without webcam bg
- MediaPipe VIDEO running mode (temporal tracking, timestamped frames)
- Cached vector layer (dirty flag) + single-pass mask compositing
- Select button in UI bar; recolor + delete selected shape
- Brush-size ring near cursor; in-app help overlay; live FPS
- Robust camera init (DirectShow on Windows, graceful failure)
- Lazy undo snapshots for drag/resize; ShapeLayer history capped (HISTORY_LIMIT)
- Timestamped PNG exports into exports/

## TODO (nice-to-have)
- [ ] Glow trail effect on freehand strokes
- [ ] Fill/outline toggle for shapes
- [ ] Timelapse export (cv2.VideoWriter)

## Gotchas for Claude
- Never use mp.solutions — broken on Python 3.12+
- Use results.handedness[i][0].display_name for hand label
- VIDEO mode needs a monotonically increasing timestamp_ms
- Always copy.deepcopy for ShapeLayer history snapshots
- Set ShapeLayer._dirty = True after any change to committed shapes
- Both undo stacks (canvas + shapes) must always be called together

## Setup
```
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```
