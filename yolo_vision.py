# yolo_vision.py
#
# Multi-camera SafePath Shield vision:
#
# - Fire/Smoke detection:
#     Ultralytics YOLO model from models/best.pt (TommyNgx Fire/Smoke)
#
# - Gun/Firearm detection:
#     Ultralytics YOLO model from Hugging Face:
#       repo: Subh775/Firearm_Detection_Yolov8n
#       file: weights/best.pt
#
# - Rooms:
#     R1, R2, R3, R4, R5, R6 -> each has its own "camera screen"
#     R5 = real webcam (door locking hardware mechanism)
#     others = security camera videos (looped)
#
# - Per-room state:
#     "clear"    : nothing
#     "fire"     : fire/smoke only
#     "gun"      : firearm only
#     "fire_gun" : both detected
#
# - Outputs:
#     - room_states.json (consumed by server/UI)
#     - 2x3 CCTV-style grid window with tinted tiles:
#           green = clear, red = fire/fire_gun, grey = gun
#
# Requirements:
#   pip install ultralytics opencv-python huggingface_hub
#
# IMPORTANT:
#   Update CAM_SOURCES paths to match your actual video files.
#   Ensure models/best.pt exists for fire/smoke.

import os
import cv2
import json
import time
import signal
import sys
import numpy as np
from ultralytics import YOLO
from huggingface_hub import hf_hub_download

# ---------- CONFIG ----------

ROOMS = ["R1", "R2", "R3", "R4", "R5", "R6"]
ROOM_STATES_PATH = "room_states.json"

# Fire/smoke model (local)
FIRE_MODEL_PATH = "models/best.pt"
FIRE_CONF = 0.35

# Gun model (Hugging Face)
GUN_MODEL_REPO = "Subh775/Firearm_Detection_Yolov8n"
GUN_WEIGHT_FILENAME = "weights/best.pt"
GUN_CONF = 0.35

# Camera sources
# Replace the MP4s with your chosen security cam clips.
# R5 is the real webcam for the door hardware.
CAM_SOURCES = {
    "R1": "assets/r1.mp4",
    "R2": "assets/r2.mp4",
    "R3": "assets/r3.mp4",
    "R4": "assets/r4.mp4",
    "R5": 0,                # LIVE WEBCAM (door locking mechanism)
    "R6": "assets/r6.mp4",
}

# Grid layout for CCTV mosaic
GRID_COLS = 3
GRID_ROWS = 2
TILE_W = 320
TILE_H = 240


# ---------- HELPERS ----------

def save_states(states: dict):
    with open(ROOM_STATES_PATH, "w") as f:
        json.dump(states, f)


def init_states() -> dict:
    states = {r: "clear" for r in ROOMS}
    save_states(states)
    return states


def is_fire_or_smoke(label: str) -> bool:
    name = label.lower()
    return ("fire" in name) or ("smoke" in name)


def is_gun_label(label: str) -> bool:
    """
    For the firearm model: class names are typically variants of weapons.
    We still guard on keywords for safety and clarity.
    """
    name = label.lower()
    return any(tok in name for tok in [
        "gun", "pistol", "rifle", "firearm", "weapon", "revolver", "handgun"
    ])


def download_gun_weights(repo_id=GUN_MODEL_REPO, filename=GUN_WEIGHT_FILENAME):
    """
    Download firearm detector weights from HF Hub (cached).
    """
    print(f"Downloading firearm detection weights from {repo_id}/{filename} ...")
    path = hf_hub_download(repo_id=repo_id, filename=filename)
    print(f"Firearm weights at: {path}")
    return path


def build_multicam_view(room_frames, states):
    """
    Build a 2x3 grid mosaic.
      - Each tile shows that room's frame (or black if none)
      - Tinted by state:
          clear    -> green
          fire     -> red
          gun      -> grey
          fire_gun -> red
    """
    canvas_h = GRID_ROWS * TILE_H
    canvas_w = GRID_COLS * TILE_W
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    for idx, rid in enumerate(ROOMS):
        row = idx // GRID_COLS
        col = idx % GRID_COLS
        y0 = row * TILE_H
        x0 = col * TILE_W

        frame = room_frames.get(rid)
        if frame is None:
            tile = np.zeros((TILE_H, TILE_W, 3), dtype=np.uint8)
        else:
            tile = cv2.resize(frame, (TILE_W, TILE_H))

        state = states.get(rid, "clear")

        # Tint color
        if state in ("fire", "fire_gun"):
            tint_color = (0, 0, 255)        # red
            alpha = 0.32
        elif state == "gun":
            tint_color = (255, 0, 0)    # blue
            alpha = 0.28
        else:
            tint_color = (0, 255, 0)        # green
            alpha = 0.12

        overlay = tile.copy()
        cv2.rectangle(overlay, (0, 0), (TILE_W, TILE_H), tint_color, -1)
        cv2.addWeighted(overlay, alpha, tile, 1 - alpha, 0, tile)

        # Room label
        cv2.putText(
            tile,
            rid,
            (10, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        # State label
        if state != "clear":
            cv2.putText(
                tile,
                state,
                (10, TILE_H - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        canvas[y0:y0 + TILE_H, x0:x0 + TILE_W] = tile

    return canvas


# ---------- MAIN ----------

def main():
    # Load fire model
    try:
        fire_model = YOLO(FIRE_MODEL_PATH)
    except Exception as e:
        print(f"❌ Failed to load fire model at '{FIRE_MODEL_PATH}': {e}")
        sys.exit(1)
    print("✅ Fire model classes:", fire_model.names)

    # Load / download gun model
    try:
        gun_weights_path = download_gun_weights()
        gun_model = YOLO(gun_weights_path)
    except Exception as e:
        print(f"❌ Failed to load firearm model: {e}")
        sys.exit(1)
    print("✅ Gun model classes:", gun_model.names)

    # Open camera/video sources
    caps = {}
    for rid, src in CAM_SOURCES.items():
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            print(f"[WARN] Unable to open source {src} for {rid}")
            continue
        caps[rid] = cap

    if not caps:
        print("❌ No camera sources available. Check CAM_SOURCES.")
        sys.exit(1)

    if "R5" not in caps:
        print("⚠️ R5 webcam not available. Check webcam index or permissions.")

    states = init_states()

    def handle_exit(sig, frame):
        print("\nStopping vision loop...")
        for c in caps.values():
            c.release()
        cv2.destroyAllWindows()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)

    print("\n🛡️ SafePath Shield – Multi-Cam Threat View")
    print(" - R5 = live door hardware cam")
    print(" - Others = security footage (from assets/)")
    print(" - Red = fire/smoke, Grey = gun, Green = clear\n")
    print("Press Esc or Ctrl+C to exit.\n")

    while True:
        room_frames = {}

        # 1) Read frames
        for rid, cap in caps.items():
            ret, frame = cap.read()
            if not ret:
                # Loop videos
                src = CAM_SOURCES[rid]
                if isinstance(src, str):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
            if ret:
                room_frames[rid] = frame

        if not room_frames:
            print("[WARN] No frames captured this loop.")
            time.sleep(0.2)
            continue

        fire_rooms = set()
        gun_rooms = set()

        # 2) Run detection per room
        for rid, frame in room_frames.items():
            # --- Fire/Smoke ---
            try:
                fire_results = fire_model(frame, conf=FIRE_CONF, verbose=False)[0]
                for box in fire_results.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = fire_results.names.get(cls_id, str(cls_id))
                    conf = float(box.conf[0])
                    if conf >= FIRE_CONF and is_fire_or_smoke(cls_name):
                        fire_rooms.add(rid)
                        break
            except Exception as e:
                print(f"[WARN] Fire inference failed for {rid}: {e}")

            # --- Gun/Firearm ---
            try:
                gun_results = gun_model(frame, conf=GUN_CONF, verbose=False)[0]
                for box in gun_results.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = gun_results.names.get(cls_id, str(cls_id))
                    conf = float(box.conf[0])
                    if conf >= GUN_CONF and is_gun_label(cls_name):
                        gun_rooms.add(rid)
                        break
            except Exception as e:
                print(f"[WARN] Gun inference failed for {rid}: {e}")

        # 3) Merge states
        new_states = {}
        for r in ROOMS:
            if r in fire_rooms and r in gun_rooms:
                new_states[r] = "fire_gun"
            elif r in fire_rooms:
                new_states[r] = "fire"
            elif r in gun_rooms:
                new_states[r] = "gun"
            else:
                new_states[r] = "clear"

        # 4) Persist if changed
        if new_states != states:
            states = new_states
            save_states(states)
            print("[UPDATE]", states)

        # 5) Build and show mosaic
        grid_view = build_multicam_view(room_frames, states)
        cv2.imshow("SafePath Shield – Multi-Cam Threat View", grid_view)

        if cv2.waitKey(1) & 0xFF == 27:  # Esc
            break

    for c in caps.values():
        c.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
