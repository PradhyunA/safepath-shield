import json
from collections import defaultdict, deque


class BuildingMap:
    def __init__(self, path: str = "map.json"):
        with open(path, "r") as f:
            data = json.load(f)

        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = data["edges"]

        # adjacency: node_id -> list[(neighbor_id, weight, edge_obj)]
        self.adj = defaultdict(list)
        for e in self.edges:
            a, b = e["from"], e["to"]
            w = e.get("weight", 1)
            # treat edges as undirected for now
            self.adj[a].append((b, w, e))
            self.adj[b].append((a, w, e))

        self.exits = [n["id"] for n in data["nodes"] if n.get("type") == "exit"]
        self.rooms = [n["id"] for n in data["nodes"] if n.get("type") == "room"]


class SafePathEngine:
    def __init__(self, building: BuildingMap):
        self.b = building
        self.hazards = set()        # node ids that are hazardous
        self.locked_doors = set()   # door_ids manually forced locked (if needed)

    def set_hazards(self, hazard_nodes):
        """Set current hazardous nodes."""
        self.hazards = set(hazard_nodes or [])

    def bfs_to_exit(self, start: str):
        """Find a safe path from start node to any exit, avoiding hazards/locked."""
        if start in self.hazards:
            return None

        q = deque()
        q.append((start, []))
        visited = {start}

        while q:
            node, path = q.popleft()

            if node in self.b.exits:
                return path  # list of (from, to, edge)

            for nei, _w, edge in self.b.adj[node]:
                if nei in visited:
                    continue
                if nei in self.hazards:
                    continue

                door_id = edge.get("door_id")
                if door_id and door_id in self.locked_doors:
                    continue

                visited.add(nei)
                q.append((nei, path + [(node, nei, edge)]))

        return None

    def compute_plan(self):
        """Compute per-room EVAC/LOCKDOWN and per-door states."""
        room_plans = {}
        doors_state = defaultdict(lambda: "UNLOCK")
        used_by_any = set()

        # 1) Plan for each room
        for r in self.b.rooms:
            path = self.bfs_to_exit(r)
            if path is None:
                room_plans[r] = {"mode": "LOCKDOWN"}
            else:
                exit_node = path[-1][1]
                used_edges = [e for (_a, _b, e) in path]
                door_ids = [e.get("door_id") for e in used_edges if e.get("door_id")]

                room_plans[r] = {
                    "mode": "EVAC",
                    "exit": exit_node,
                    "path_edges": door_ids,
                }

                for d in door_ids:
                    used_by_any.add(d)

        # 2) Door behavior based on hazards + paths
        for e in self.b.edges:
            d = e.get("door_id")
            if not d:
                continue

            a, b = e["from"], e["to"]

            if a in self.hazards or b in self.hazards:
                doors_state[d] = "LOCK_BLOCK_THREAT"
            elif d in used_by_any:
                doors_state[d] = "UNLOCK"
            else:
                # default idle state: locked but not as hard as threat-lock
                if doors_state[d] != "LOCK_BLOCK_THREAT":
                    doors_state[d] = "LOCK_IDLE"

        return {
            "rooms": room_plans,
            "doors": dict(doors_state),
        }


if __name__ == "__main__":
    bm = BuildingMap()
    eng = SafePathEngine(bm)
    eng.set_hazards(["H1"])
    plan = eng.compute_plan()

    print(json.dumps(plan, indent=2))
