#!/usr/bin/env bash
# Install this repo's models, world and gimbal camera into a local (non-Docker)
# PX4 + Gazebo setup. Safe to run again after changing models/, worlds/ or
# setup_gimbal.py.
#
# Usage: ./setup_local.sh            (PX4 in ~/PX4-Autopilot)
#        PX4_DIR=/path/to/PX4-Autopilot ./setup_local.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PX4_DIR="${PX4_DIR:-$HOME/PX4-Autopilot}"
GZ_MODELS_DIR="$HOME/.gz/models"
PX4_WORLDS_DIR="$PX4_DIR/Tools/simulation/gz/worlds"
DRONE_SDF="$PX4_DIR/Tools/simulation/gz/models/x500_depth/model.sdf"
DRONE_SDF_ORIG="$DRONE_SDF.bak_nogimbal"

if [ ! -f "$DRONE_SDF" ] || [ ! -d "$PX4_WORLDS_DIR" ]; then
    echo "PX4-Autopilot not found at $PX4_DIR" >&2
    echo "Install PX4 first (see README), or set PX4_DIR=/path/to/PX4-Autopilot" >&2
    exit 1
fi

# 1. Gazebo models
mkdir -p "$GZ_MODELS_DIR"
for model in "$REPO_DIR"/models/*/; do
    cp -r "$model" "$GZ_MODELS_DIR/"
done
echo "Copied models to $GZ_MODELS_DIR"

# 2. World
cp "$REPO_DIR/worlds/default.sdf" "$PX4_WORLDS_DIR/default.sdf"
echo "Copied worlds/default.sdf to $PX4_WORLDS_DIR"

# 3. Gimbal: setup_gimbal.py adds joints on every run, so always start from the
#    unmodified drone model, which is backed up on the first run.
if [ ! -f "$DRONE_SDF_ORIG" ]; then
    if grep -q gimbal_yaw_joint "$DRONE_SDF"; then
        echo "$DRONE_SDF already has a gimbal but no backup of the original exists." >&2
        echo "Restore it first: (cd $PX4_DIR && git checkout -- Tools/simulation/gz/models/x500_depth/model.sdf)" >&2
        exit 1
    fi
    cp "$DRONE_SDF" "$DRONE_SDF_ORIG"
    echo "Backed up original drone model to $DRONE_SDF_ORIG"
fi
cp "$DRONE_SDF_ORIG" "$DRONE_SDF"
(cd "$REPO_DIR" && python3 -c "import setup_gimbal; setup_gimbal.MODEL_PATH = '$DRONE_SDF'; setup_gimbal.main()")

# 4. Environment
if ! grep -q "GZ_SIM_RESOURCE_PATH=.*\.gz/models" "$HOME/.bashrc"; then
    echo 'export GZ_SIM_RESOURCE_PATH=$HOME/.gz/models:$GZ_SIM_RESOURCE_PATH' >> "$HOME/.bashrc"
    echo "Added GZ_SIM_RESOURCE_PATH to ~/.bashrc (open a new terminal to use it)"
fi

# 5. Fine-tuned YOLO weights are not stored in git; download them from the release
WEIGHTS="$REPO_DIR/finetune/runs/yolov8m_sim/weights/best.pt"
WEIGHTS_URL="https://github.com/NGUYEN-UY-THUAT/px4-drone-traffic-yolov8/releases/download/v1.0/best.pt"
if [ ! -f "$WEIGHTS" ]; then
    mkdir -p "$(dirname "$WEIGHTS")"
    if curl -fL -o "$WEIGHTS" "$WEIGHTS_URL"; then
        echo "Downloaded fine-tuned weights to $WEIGHTS"
    else
        rm -f "$WEIGHTS"
        echo "Warning: could not download $WEIGHTS_URL; uav_camera_det.py needs it." >&2
        echo "Download it manually or train it with finetune/train.py." >&2
    fi
fi

echo
echo "Done. Restart PX4 to load the changes."
