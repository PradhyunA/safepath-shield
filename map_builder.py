import os
import json
import math
import cv2
import numpy as np
from heapq import heappush, heappop
import networkx as nx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FLOOR_IMG_PATH = os.path.join(BASE_DIR, "static", "floorplan.png")

EXIT_ID = "X1"  # True exit


# ---------- A* on occupancy grid ----------

def astar(start, goal, obstacle_grid):
    """
    start, goal: (y, x)
    obstacle_grid: 1 = blocked, 0 = free
    """
    def h(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    hmax, wmax = obstacle_grid.shape
    neighbors = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    open_heap = []
    heappush(open_heap, (0.0, start))

    came_from = {}
    gscore = {start: 0.0}

    while open_heap:
        _, current = heappop(open_heap)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        cy, cx = current
        for dy, dx in neighbors:
            ny, nx = cy + dy, cx + dx
            if ny < 0 or ny >= hmax or nx < 0 or nx >= wmax:
                continue
            if obstacle_grid[ny, nx] == 1:
                continue

            tentative = gscore[current] + 1.0
            if tentative < gscore.get((ny, nx), float("inf")):
                came_from[(ny, nx)] = current
                gscore[(ny, nx)] = tentative
                f = tentative + h((ny, nx), goal)
                heappush(open_heap, (f, (ny, nx)))

    return []


# ---------- Image + rooms ----------

def load_floor_image():
    img = cv2.imread(FLOOR_IMG_PATH, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"Could not load floorplan image at {FLOOR_IMG_PATH}")
    return img


def build_walkable_and_rooms(img):
    # Walls: darker than near-white -> obstacle
    _, binary = cv2.threshold(img, 240, 255, cv2.THRESH_BINARY)
    walkable = (binary == 255).astype(np.uint8)
    obstacle = 1 - walkable

    # All coordinates are tuned for your 1530x1080 PNG.
    # These (x, y) are inside white floor, NOT inside circles/walls.
    rooms = {
        "R2": (271, 380),
        "R3": (748, 380),
        "R4": (748, 760),
        "R5": (1057, 350),
        "R6": (1319, 380),
        "R1": (303, 880),   # big lower-left room
        "X1": (150, 1040),  # exit gap bottom-left
    }

    return obstacle, rooms


def region_box(cx, cy, hw, hh):
    return [
        [cx - hw, cy - hh],
        [cx + hw, cy - hh],
        [cx + hw, cy + hh],
        [cx - hw, cy + hh],
    ]


def build_regions(rooms):
    """Clickable regions as small boxes around each logical point."""
    regions = []
    for rid, (x, y) in rooms.items():
        if rid == EXIT_ID:
            rtype = "EXIT"
            hw, hh = 40, 30
        else:
            rtype = "ROOM"
            hw, hh = 80, 60

        regions.append(
            {
                "id": rid,
                "type": rtype,
                "points": region_box(x, y, hw, hh),
            }
        )
    return regions


def build_edges():
    """
    Simple conceptual edges for the text-only plan.
    (The UI drawing uses pixel-perfect paths_xy instead.)
    """
    edges = []
    for rid in ["R2", "R3", "R4", "R5", "R6", "R1"]:
        edges.append({"from": rid, "to": EXIT_ID})
    return edges


# ---------- Region-level paths (for Live Plan text) ----------

def compute_region_paths_to_exit(regions, edges):
    G = nx.Graph()
    centroids = {}
    node_types = {}

    for r in regions:
        rid = r["id"]
        pts = r["points"]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        centroids[rid] = (cx, cy)
        node_types[rid] = r["type"]
        G.add_node(rid, type=r["type"])

    for e in edges:
        a, b = e["from"], e["to"]
        if a not in centroids or b not in centroids:
            continue
        ax, ay = centroids[a]
        bx, by = centroids[b]
        w = math.hypot(ax - bx, ay - by)
        G.add_edge(a, b, weight=w)

    exits = [nid for nid, t in node_types.items() if t == "EXIT"]
    paths = {}
    if not exits:
        return paths

    for n in G.nodes:
        best_len = float("inf")
        best_path = None
        for ex in exits:
            try:
                p = nx.shortest_path(G, n, ex, weight="weight")
                l = nx.path_weight(G, p, weight="weight")
                if l < best_len:
                    best_len = l
                    best_path = p
            except nx.NetworkXNoPath:
                continue
        if best_path:
            paths[n] = best_path

    return paths


# ---------- Pixel A* paths (for overlay drawing) ----------

def compute_pixel_paths(obstacle_grid, rooms):
    if EXIT_ID not in rooms:
        return {}

    gx, gy = rooms[EXIT_ID]
    goal = (gy, gx)

    paths_xy = {}

    for rid, (x, y) in rooms.items():
        if rid == EXIT_ID:
            continue

        start = (y, x)
        path = astar(start, goal, obstacle_grid)
        if not path:
            paths_xy[rid] = []
            continue

        # store as [x, y] pairs for SVG polyline
        paths_xy[rid] = [[px, py] for (py, px) in path]

    return paths_xy


# ---------- Public API ----------

def build_map(svg_path=None):
    img = load_floor_image()
    obstacle_grid, rooms = build_walkable_and_rooms(img)

    regions = build_regions(rooms)
    edges = build_edges()
    region_paths = compute_region_paths_to_exit(regions, edges)
    pixel_paths = compute_pixel_paths(obstacle_grid, rooms)

    return {
        "regions": regions,
        "edges": edges,
        "paths_to_exit": region_paths,
        "paths_xy": pixel_paths,
        "image_size": [img.shape[1], img.shape[0]],  # [width, height]
    }


def build_map_and_save(svg_path, out_json_path):
    data = build_map(svg_path)
    with open(out_json_path, "w") as f:
        json.dump(data, f, indent=2)
    return data
