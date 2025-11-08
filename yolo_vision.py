import cv2
import time
import requests
from ultralytics import YOLO

API_URL = "http://localhost:8000/api/hazards"

# Load YOLOv8 nano model (downloads yolov8n.pt on first run)
model = YOLO("yolov8n.pt")

# Use the working camera index you found
cap = cv2.VideoCapture(0)

HAZARD_CLASSES = {"person"}      # what we treat as a "threat" for demo
last_sent = None
cooldown = 0.5                   # seconds between POSTs


def get_hazard_nodes(frame, results):
    """Map detected people into logical nodes H1/H2 based on frame halves."""
    active = set()
    h, w, _ = frame.shape

    # Dynamic regions: left half = H1, right half = H2
    regions = {
        "H1": (0, 0, w // 2, h),
        "H2": (w // 2, 0, w, h),
    }

    for r in results:
        boxes = r.boxes
        names = r.names  # dict: id -> class name

        for box in boxes:
            cls_id = int(box.cls)
            cls_name = names[cls_id]

            if cls_name not in HAZARD_CLASSES:
                continue

            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            for node_id, (rx1, ry1, rx2, ry2) in regions.items():
                if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                    active.add(node_id)

    return list(active), regions


while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to read from camera.")
        break

    # Run YOLO (single forward pass)
    results = model(frame, imgsz=640, verbose=False)

    hazards, regions = get_hazard_nodes(frame, results)

    # Throttle POSTs
    now = time.time()
    if last_sent is None or now - last_sent > cooldown:
        try:
            requests.post(API_URL, json={"hazards": hazards})
            print("Sent hazards:", hazards)
            last_sent = now
        except Exception as e:
            print("API error:", e)

    # Draw dynamic regions
    h, w, _ = frame.shape
    for node_id, (rx1, ry1, rx2, ry2) in regions.items():
        color = (0, 0, 255) if node_id in hazards else (0, 255, 0)
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), color, 2)
        cv2.putText(
            frame,
            node_id,
            (rx1 + 10, ry1 + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            color,
            2,
        )

    cv2.imshow("SafePath YOLO View", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC to exit
        break

cap.release()
cv2.destroyAllWindows()
