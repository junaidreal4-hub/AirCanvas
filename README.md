# 🎨 AirCanvas Pro

> Draw in the air. A real-time, two-handed gesture drawing studio powered by computer-vision hand tracking — no mouse, no touchscreen, no stylus.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-Tasks_API-00897B)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

AirCanvas Pro turns your webcam into a canvas. Your **right hand** is the pen,
your **left hand** is a dial for brush size, and **both hands together** resize
whatever you've selected. A floating gesture-driven toolbar lets you pick
colours, shapes, and tools without ever touching the keyboard.

---

## ✨ Features

- **21-point hand tracking** via MediaPipe's modern Tasks API in `VIDEO` mode
  (temporal tracking → smoother, lower-jitter cursors than per-frame detection).
- **Two independent render layers** — a raster layer for freehand strokes and an
  eraser, plus a vector layer of editable `Shape` objects (move / resize / recolour / delete).
- **5 drawing primitives:** freehand, rectangle, circle, line, triangle.
- **5-brush engine:** pen, marker (translucent), spray airbrush, calligraphy
  (a rotated nib that follows the stroke), and glowing neon — see `brush_engine.py`.
- **Canvas mode toggle:** flip between a clean **white sheet** and the **live
  camera** by holding an open palm for 0.8 s, with a smooth 15-frame cross-fade.
- **Circular HSV colour wheel:** an open palm pops up a 36-hue ring plus a
  greyscale inner ring; hover a swatch and pinch to pick. Arbitrary BGR colours,
  not just the 10 presets.
- **Live brush-size feedback:** a translucent preview disc at the fingertip and a
  vertical fill bar on the left edge, shown while a drawing tool is active.
- **Pseudo-3D extrusion:** the *3D Preview* button traces the raster artwork and
  gives every shape a darker extruded "shadow" body — one undoable edit.
- **10-colour quick palette**, adjustable brush (3–50 px) controlled by your other hand.
- **Gesture-driven UI:** dwell-to-click toolbar with a progress ring, no clicks needed.
- **Two-handed resize:** pinch with both hands and spread/squeeze to scale a shape.
- **Hold-to-clear:** make a fist for 2 seconds; a countdown arc confirms the action.
- **Independent undo/redo** for both layers (capped history), including transforms and 3D.
- **PNG export** — saves your art on a black (air) or white (sheet) background, webcam removed.
- **Live FPS read-out** and an in-app help overlay (press `H`).

## 🖐️ Gesture & key reference

| Gesture | Action |
|---|---|
| Right hand, **index finger only** | Draw / interact with the canvas |
| Right hand, **hover a toolbar button ~0.6 s** | Trigger that button |
| Right hand, **open palm** | Show the circular colour wheel |
| Right hand, **hold an open palm 0.8 s** | Flip canvas mode (white sheet ⇄ air) |
| Over the wheel, **pinch a swatch** | Pick that colour (fist dismisses the wheel) |
| Right hand, **hold a fist 2 s** | Clear the whole canvas (countdown arc) |
| Left hand, **pinch distance** | Brush size (wide pinch = thicker) |
| **Both hands pinch + spread/squeeze** | Resize the selected shape |

> The open palm both *shows* the wheel and, if you keep holding it, *flips* the
> canvas — a dwell ring counts down the 0.8 s so the flip is never a surprise.

| Key | Action | Key | Action |
|---|---|---|---|
| `D` | Draw tool | `Z` | Undo |
| `E` | Eraser | `Y` | Redo |
| `X` | Select tool | `C` | Recolour selected shape |
| `1`–`5` | Brush: pen / marker / spray / calligraphy / neon | `M` | Toggle canvas mode |
| `V` | 3D extrusion preview | `Del`/`Backspace` | Delete selected shape |
| `S` | Save PNG → `exports/` | `Esc` | Quit |
| `H` | Toggle help overlay | | |

> **Tip:** the camera image is mirrored, so movements feel natural — moving your
> hand right moves the cursor right.

## 🚀 Quick start

```powershell
# Python 3.11 recommended (MediaPipe Tasks supports 3.9–3.12)
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1          # Windows
# source venv/bin/activate            # macOS / Linux

pip install -r requirements.txt
python main.py
```

The `hand_landmarker.task` model ships in the repo root, so the app runs out of
the box. Press `H` once it launches for the in-app cheat sheet.

## 🏗️ Architecture

```
main.py            Entry point — camera loop, gesture→action routing, HUD, hotkeys
config.py          All tunable constants (palette, thresholds, limits, brush/wheel/3D)
gesture_engine.py  MediaPipe HandLandmarker wrapper; pinch hysteresis + EMA smoothing
brush_engine.py    5 stroke styles (pen/marker/spray/calligraphy/neon) as pure functions
canvas_layer.py    Raster layer: brush strokes, eraser, 3D extrusion, undo/redo
shape_layer.py     Vector layer: Shape objects, selection, transforms, cached render
ui_manager.py      Dwell-to-click toolbar, colour swatches, hover progress rings
ui_theme.py        Shared theme palette + rounded-panel / button drawing helpers
color_wheel.py     Open-palm circular HSV palette (hover + pinch to pick)
hand_landmarker.task   Pre-trained MediaPipe hand-landmark model (~7.8 MB)
```

**Design notes worth calling out:**

- **Hand mapping.** The frame is mirrored before detection, so MediaPipe's
  `"Left"` label is the user's on-screen *right* hand (the pen). The label flip
  lives in one place: `GestureEngine.process`.
- **Pinch hysteresis.** Pinch turns *on* below 40 px and *off* above 60 px, with
  a dead zone between — this stops the flag flickering at the boundary.
- **Cached vector layer.** Committed shapes render into a cached buffer that's
  only rebuilt when the scene changes (a dirty flag). The selection box and the
  in-progress shape are drawn on a per-frame copy, so a static drawing of N
  shapes costs one buffer copy per frame instead of N redraws.
- **Lazy undo snapshots.** A drag or resize only pushes an undo state on the
  *first* actual movement, so selecting a shape without moving it doesn't
  pollute the history.
- **Overlays drawn after compositing.** Cursors, rings and the colour wheel are
  painted onto the *final* frame, not the camera frame — so they stay visible
  when the background fades to the white sheet instead of being painted over.
- **One gesture, two outcomes.** An open palm latches the colour wheel open, and
  *continuing* to hold it for 0.8 s flips the canvas mode. A dwell ring makes the
  second action discoverable, and the wheel only hides on a fist or a pick — so
  pinching a swatch never makes it vanish mid-gesture.
- **Localised neon glow.** The neon brush blurs a small ROI around each segment
  rather than the whole frame, keeping the gaussian-blur halo cheap at 720p.
- **Hand-rolled UI kit.** OpenCV only draws square rectangles, so `ui_theme.py`
  composes rounded panels/buttons from rects + circles and centres labels with
  `getTextSize`. One accent colour drives every hover, active and progress state,
  and overlays are blended as translucent cards so they stay legible on any
  background.

## 🔧 Tuning

Everything you'd want to tweak lives in [`config.py`](config.py):
brush range, pinch thresholds, cursor smoothing (`SMOOTHING`), the fist-clear
duration, the toolbar dwell time, and the undo history cap.

## 🧰 Troubleshooting

- **Black window / "could not open a webcam":** another app may hold the camera,
  or index `0` isn't your webcam. Close other apps; on Windows the app already
  prefers the faster DirectShow backend.
- **Cursor feels laggy:** lower `SMOOTHING` in `config.py` (less smoothing,
  more responsiveness).
- **Gestures misfire in low light:** hand tracking needs reasonable lighting;
  raise `min_hand_detection_confidence` in `gesture_engine.py` if you get false
  positives.

## 📦 Tech stack

Python · MediaPipe (Tasks API) · OpenCV · NumPy

## 📄 License

MIT — see [`LICENSE`](LICENSE).
