from flask import Flask, request, jsonify, send_from_directory
from engine import BuildingMap, SafePathEngine
from hardware import HardwareInterface

app = Flask(__name__, static_folder="static")

bm = BuildingMap("map.json")
engine = SafePathEngine(bm)
hw = HardwareInterface()  # safe no-op if no Arduino

current_hazards = set()


@app.route("/api/hazards", methods=["GET", "POST"])
def hazards():
    """
    POST: { "hazards": ["H1", "H2"] } from YOLO or UI
    GET:  returns current hazards + computed plan
    """
    global current_hazards

    if request.method == "POST":
        data = request.get_json(force=True) or {}
        current_hazards = set(data.get("hazards", []))

    # compute plan based on latest hazards
    engine.set_hazards(list(current_hazards))
    plan = engine.compute_plan()

    # push to hardware (if connected)
    try:
        hw.send_plan(plan)
    except Exception as e:
        print("[HW] send_plan error:", e)

    return jsonify({
        "hazards": list(current_hazards),
        "plan": plan
    })


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


if __name__ == "__main__":
    # Flask dev server
    app.run(host="0.0.0.0", port=8000, debug=True)
