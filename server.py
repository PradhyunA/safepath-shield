# server.py
#
# SafePath Shield server:
# - Serves login + upload + live map UI
# - Accepts floorplan PNG upload (saved as static/floorplan.png)
# - Accepts optional 3D layout upload (saved as static/building3d.png)
# - Exposes /api/room_states read from room_states.json (written by yolo_vision.py)

import os
import json
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app)

ROOMS = ["R1", "R2", "R3", "R4", "R5", "R6"]
ROOM_STATES_PATH = "room_states.json"
FLOORPLAN_PATH = os.path.join("static", "floorplan.png")
THREED_PATH = os.path.join("static", "building3d.png")


def load_room_states():
    if os.path.exists(ROOM_STATES_PATH):
        try:
            with open(ROOM_STATES_PATH) as f:
                data = json.load(f)
            for r in ROOMS:
                data.setdefault(r, "clear")
            return data
        except Exception:
            pass
    return {r: "clear" for r in ROOMS}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/app.js")
def app_js():
    return send_from_directory("static", "app.js")


@app.route("/floorplan.png")
def floorplan():
    return send_from_directory("static", "floorplan.png")


@app.route("/building3d.png")
def building3d():
    # Only shown if uploaded; frontend handles fallback nicely.
    return send_from_directory("static", "building3d.png")


@app.route("/api/room_states", methods=["GET"])
def api_room_states():
    return jsonify(load_room_states())


@app.route("/api/upload_floorplan", methods=["POST"])
def upload_floorplan():
    """
    Accepts a PNG/JPEG floorplan and stores it as static/floorplan.png.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = os.path.splitext(f.filename.lower())[1]
    if ext not in [".png", ".jpg", ".jpeg"]:
        return jsonify({"error": "Please upload a PNG or JPG image"}), 400

    os.makedirs("static", exist_ok=True)
    f.save(FLOORPLAN_PATH)

    return jsonify({"ok": True, "message": "Floorplan updated"}), 200


@app.route("/api/upload_3d", methods=["POST"])
def upload_3d():
    """
    Accepts a PNG/JPEG 3D layout render and stores it as static/building3d.png.
    Purely visual; no mapping logic.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = os.path.splitext(f.filename.lower())[1]
    if ext not in [".png", ".jpg", ".jpeg"]:
        return jsonify({"error": "Please upload a PNG or JPG image"}), 400

    os.makedirs("static", exist_ok=True)
    f.save(THREED_PATH)

    return jsonify({"ok": True, "message": "3D layout updated"}), 200


@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory("static", path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
