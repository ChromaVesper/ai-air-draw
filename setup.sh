#!/usr/bin/env bash
# setup.sh
# ────────
# Creates a virtual environment, installs dependencies, and downloads
# the MediaPipe hand-landmarker model from Google's official CDN.
#
# Run once after cloning:
#   chmod +x setup.sh
#   ./setup.sh

set -e   # Stop immediately if any command fails

echo ""
echo "=== AI Air Draw — Setup ==="
echo ""

# 1. Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "[1/3] Creating virtual environment (.venv)..."
    python3 -m venv .venv
else
    echo "[1/3] Virtual environment already exists — skipping."
fi

# 2. Install Python dependencies
echo "[2/3] Installing Python dependencies..."
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install --no-compile -r requirements.txt --quiet
echo "      Dependencies installed."

# 3. Download the MediaPipe hand-landmarker model
MODEL_DIR="models"
MODEL_FILE="$MODEL_DIR/hand_landmarker.task"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

if [ ! -f "$MODEL_FILE" ]; then
    echo "[3/3] Downloading MediaPipe hand-landmarker model from Google CDN..."
    mkdir -p "$MODEL_DIR"
    curl -L -o "$MODEL_FILE" "$MODEL_URL" --progress-bar
    echo "      Model saved to $MODEL_FILE"
else
    echo "[3/3] Model already downloaded — skipping."
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Activate the environment and run the app:"
echo ""
echo "  source .venv/bin/activate"
echo "  python src/main.py"
echo ""
