# AI Air Draw ✋🎨

> Draw in the air with your index finger — no mouse, no tablet, just your hand and a webcam.

---

## Description

AI Air Draw is a real-time computer-vision application that turns your webcam into a digital drawing board.  
It detects your hand using MediaPipe, tracks the index fingertip, and lets you paint on a virtual canvas by simply pointing your finger.

**Raise your index finger → draw.**  
**Lower it → pause.**

---

## Features

- 🖐 Real-time hand tracking via MediaPipe Hands (`mp.solutions.hands`)
- ✏️ Index-finger drawing with smooth, anti-aliased strokes
- 🎨 Four drawing colours: Blue, Green, Red, Yellow
- 🧹 Eraser tool (larger white brush)
- 🗑 One-key canvas clear
- 💾 Save drawing as PNG (timestamped filename inside `drawings/`)
- 📏 Adjustable brush size (`+` / `-`)
- 📊 Live FPS counter
- 🔀 Exponential moving-average coordinate smoothing (reduces shaky lines)
- ⌨️ Full keyboard shortcut support
- 🖱 Toolbar buttons controllable by fingertip hover
- 🦴 Hand skeleton overlay on webcam feed
- 🔵 Fingertip ring indicator (shows drawing/idle state)
- ⚠️ Graceful error handling — webcam unavailable, frame drops, no hand detected

---

## Demo

> _Add a GIF or screenshot here after recording a session._
>
> ![Demo GIF](assets/demo.gif)

---

## How It Works

```
Webcam (cv2.VideoCapture)
  → Flip frame horizontally (mirror effect)
  → Convert BGR → RGB
  → MediaPipe hand detection (mp.solutions.hands)
  → 21 hand landmarks extracted
  → Landmark #8 = index fingertip
  → Gesture check: is index finger raised? (gestures.py)
  → If YES → drawing mode
  → Smooth fingertip coordinates (exponential moving average)
  → Draw line on digital canvas (drawing.py)
  → Blend canvas onto webcam frame (mask non-white pixels)
  → Overlay toolbar + FPS + mode labels
  → Display in OpenCV window
  → Repeat ~30 times per second
```

---

## Technologies

| Library | Version | Purpose |
|---|---|---|
| Python | 3.9+ | Core language |
| OpenCV (`opencv-python`) | ≥ 4.8 | Webcam, image ops, display |
| MediaPipe | 0.10.14 | Hand detection & landmarks |
| NumPy | ≥ 1.24 | Fast array/canvas operations |

> **Note:** MediaPipe is pinned to **0.10.14**. Version 1.x dropped the `mp.solutions` API
> and its replacement (Tasks API) is not yet stable on all Mac configurations.

---

## Installation

### 1 — Clone / download the project

```bash
git clone <your-github-url>
cd "hand drow"
```

### 2 — Quick setup (recommended)

```bash
chmod +x setup.sh
./setup.sh
```

This script automatically:
1. Creates a `.venv` virtual environment
2. Installs all Python dependencies
3. Downloads the MediaPipe hand-landmarker model from Google's official CDN

### 3 — Manual setup (alternative)

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> No model download is required for manual setup — `mp.solutions.hands` bundles everything it needs inside the mediapipe package itself.

---

## Running the Project

```bash
source .venv/bin/activate
python src/main.py
```

A window titled **AI Air Draw** will open showing your webcam feed with a dark toolbar at the top.

---

## Keyboard Controls

| Key | Action |
|---|---|
| `Q` or `ESC` | Quit the application |
| `C` | Clear the canvas |
| `B` | Switch to Blue |
| `G` | Switch to Green |
| `R` | Switch to Red |
| `Y` | Switch to Yellow |
| `E` | Activate Eraser |
| `S` | Save drawing as PNG |
| `+` or `=` | Increase brush size |
| `-` | Decrease brush size |

---

## How Drawing Works

1. **Coordinate conversion:** MediaPipe returns normalised coordinates (0.0–1.0). We multiply by the frame width/height to get pixel positions.  
   Example: `pixel_x = int(landmark.x * frame_width)`

2. **Previous-point tracking:** We store the last fingertip position. Every frame in drawing mode, `cv2.line(canvas, prev_point, current_point, color, thickness)` connects them.

3. **Stroke start/stop:** When drawing begins (finger raised), `prev_point` is `None` — we draw a dot. When drawing ends (finger lowered or hand gone), `prev_point` is reset to `None` to prevent jump lines.

4. **Smoothing:** Exponential moving average:  
   `smooth_x = alpha * raw_x + (1 - alpha) * smooth_x`  
   Alpha = 0.5 means 50/50 blend of new and old position. Reduces shakiness.

---

## How Gesture Detection Works

MediaPipe gives 21 landmarks per hand. Y-coordinates increase **downward** in image space.  
A raised finger has its tip **above** (smaller Y) than its base knuckle.

**Drawing gesture (index finger up):**
```
Landmark 8 (index tip).y  <  Landmark 6 (index PIP knuckle).y
AND
Landmark 12 (middle tip).y  ≥  Landmark 10 (middle PIP).y   ← middle finger NOT up
```

This prevents false triggers when making a peace-sign ✌️.

---

## How Colors Work

OpenCV uses **BGR** (Blue-Green-Red), not RGB.  
All colors are defined centrally in `config.py`:

```python
COLORS = {
    "BLUE":   (255, 100,   0),   # B=255, G=100, R=0
    "GREEN":  (  0, 200,   0),
    "RED":    (  0,   0, 220),
    "YELLOW": (  0, 220, 220),
}
```

The selected color is passed to `cv2.line()` as the line color.

---

## How the Eraser Works

The eraser is simply drawing **white** `(255, 255, 255)` with a larger brush.  
Since the canvas background is white, painting white looks like erasing.  
The eraser radius is controlled by `ERASER_SIZE` in `config.py`.

---

## Project Structure

```
hand drow/
│
├── src/
│   ├── main.py          # Entry point — ties everything together
│   ├── hand_tracker.py  # HandTracker class (MediaPipe mp.solutions.hands wrapper)
│   ├── drawing.py       # DrawingCanvas class (canvas, lines, save, clear, erase)
│   ├── gestures.py      # is_index_finger_raised() and helpers
│   └── config.py        # All configurable values (colours, sizes, paths)
│
├── assets/              # Place for demo GIFs and screenshots
├── drawings/            # Saved PNGs land here (auto-created on first save)
├── models/              # (gitignored) MediaPipe model files
│
├── setup.sh             # One-command setup script
├── requirements.txt     # Python dependencies
├── .gitignore
├── LICENSE
└── README.md
```

### File responsibilities

| File | What it does |
|---|---|
| `config.py` | Centralised constants — colours (BGR), sizes, paths, camera dims |
| `hand_tracker.py` | Wraps MediaPipe: initialise, process frame, get landmark, draw skeleton |
| `gestures.py` | Pure functions: is the index finger raised? is a hand present? |
| `drawing.py` | White canvas, smooth lines, reset-on-idle, erase, clear, save PNG |
| `main.py` | Webcam loop, toolbar UI, keyboard handling, blends canvas onto frame |

---

## Troubleshooting

### Webcam won't open
- Grant **Terminal** camera permission: *System Settings → Privacy & Security → Camera*
- Quit other apps that may have locked the camera (Zoom, FaceTime, Photo Booth)
- Try `VideoCapture(1)` instead of `VideoCapture(0)` in `main.py`

### `No module named 'mediapipe'`
- You forgot to activate the virtual environment: `source .venv/bin/activate`

### Mediapipe warnings about "inference feedback manager"
- These are **harmless** status messages from MediaPipe's internals. The app works normally.

### Very low FPS (< 10)
- Lower `FRAME_WIDTH` / `FRAME_HEIGHT` in `config.py` (e.g. 640×480 instead of 1280×720)
- Close other CPU-heavy apps

### Lines appear when not drawing
- Make sure your **index finger is clearly raised** and **middle finger is down**
- Try increasing the gap — point the index finger more firmly upward

### Drawing doesn't stop when I lower my finger
- Increase `DETECTION_CONFIDENCE` in `config.py` to `0.8` for a stricter gesture detector

### Hand not detected at all
- Improve lighting — face a lamp or sit near a window
- Make sure your hand is within the camera frame

---

## Future Improvements

- ↩️ Undo / Redo support
- 🔷 Shape recognition (circles, rectangles)
- ✍️ Handwriting-to-text (OCR)
- 🤚 Multiple hand support
- 🎨 Custom colour picker (HSV slider)
- 🖼 Semi-transparent overlay mode (separate canvas view)
- 🤖 AI drawing recognition (Google QuickDraw)
- 📹 Screen recording / GIF export

---

## License

MIT — see [LICENSE](LICENSE) for details.
