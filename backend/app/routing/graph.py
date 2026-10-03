"""
backend/app/routing/graph.py
============================
Road network graph for Mumbai, loaded from the pre-built data file.

The data file (backend/data/mumbai_roads.json) is generated once by
  python scripts/build_road_graph.py
and committed to the repo. The backend loads it at startup and keeps it in
memory, adjusting edge conditions as chaos events fire.

Edge schema
-----------
{u, v, length_m, highway, name, maxspeed, oneway, geometry, flood_prone, condition}
condition: "open" | "slow" | "flooded" | "blocked"
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import networkx as nx

from app.adapters.mumbai_geo import MUMBAI_AREAS, haversine

# ── Load pre-built graph data ─────────────────────────────────────────────────

_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "mumbai_roads.json"


def _load_graph_data() -> dict:
    if _DATA_FILE.exists():
        with open(_DATA_FILE) as f:
            return json.load(f)
    # Inline fallback: straight-line connectivity for development without
    # running the build script first
    return {"graph_source": "inline_fallback", "nodes": [], "edges": []}


_RAW = _load_graph_data()
GRAPH_SOURCE: str = _RAW.get("graph_source", "unknown")

# Speed multipliers per vehicle type and edge condition
_SPEED_TABLE: dict[str, dict[str, float]] = {
    #           open   slow  flooded  blocked (∞ → pruned)
    "basic":    {  "open": 1.0, "slow": 0.45, "flooded": 0.18, "blocked": 0.0 },
    "advanced": {  "open": 1.0, "slow": 0.45, "flooded": 0.18, "blocked": 0.0 },
    "icu":      {  "open": 1.0, "slow": 0.40, "flooded": 0.12, "blocked": 0.0 },
    "boat":     {  "open": 0.55, "slow": 0.55, "flooded": 1.0, "blocked": 0.0 },
    "helicopter":{  "open": 1.0, "slow": 1.0, "flooded": 1.0, "blocked": 1.0 },
}

class RoutePath(list):
    """List of node names with an attached polyline attribute for map visualization."""
    def __init__(self, nodes: list, polyline: list = None):
        super().__init__(nodes)
        self.polyline = polyline or []


class DisasterRoadNetwork:
    """
    Mutable road network.  A single shared instance lives in the simulation
    world; chaos events call `update_road_condition` to reflect real-time
    state changes.
    """

    def __init__(self) -> None:
        self._node_pos: dict[str, dict] = {}   # name → {lat, lng}
        self._edges: dict[tuple, dict] = {}    # (u, v) → edge attrs
        self.graph = nx.DiGraph()
        self._build()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        """Populate the NetworkX graph from the pre-built data."""
        nodes: list[dict] = _RAW.get("nodes", [])
        edges: list[dict] = _RAW.get("edges", [])

        if not nodes:
            # Fall through to the area-centroid graph if data file is empty
            self._build_from_areas()
            return

        # Map area names → position from the nodes list
        for n in nodes:
            name = n.get("name")
            if name:
                self._node_pos[name] = {"lat": n["lat"], "lng": n["lng"]}

        # Supplement with MUMBAI_AREAS for any area not in the node list
        for name, pos in MUMBAI_AREAS.items():
            if name not in self._node_pos:
                self._node_pos[name] = pos

        for e in edges:
            u, v = e["u"], e["v"]
            length_m = e.get("length_m", 1000)
            maxspeed = e.get("maxspeed", 35)
            condition = e.get("condition", "open")
            flood_prone = e.get("flood_prone", False)
            geometry = e.get("geometry", [])

            self._edges[(u, v)] = {
                "length_m": length_m,
                "maxspeed": maxspeed,
                "condition": condition,
                "flood_prone": flood_prone,
                "geometry": geometry,
                "highway": e.get("highway", "secondary"),
            }
            self.graph.add_edge(u, v,
                                length_m=length_m,
                                maxspeed=maxspeed,
                                condition=condition,
                                flood_prone=flood_prone)

    def _build_from_areas(self) -> None:
        """Minimal fallback: connect MUMBAI_AREAS by straight lines."""
        EDGES = [
            ("Andheri", "Vile Parle"), ("Vile Parle", "Santacruz"),
            ("Santacruz", "Bandra"), ("Bandra", "Mahim"), ("Mahim", "Dadar"),
            ("Dadar", "Sion"), ("Sion", "Kurla"), ("Kurla", "Ghatkopar"),
            ("Dadar", "Parel"), ("Parel", "Byculla"), ("Byculla", "Colaba"),
            ("Dadar", "Worli"), ("Worli", "Colaba"),
            ("Hindmata", "Sion Circle"), ("Sion Circle", "Sion"),
            ("Sion", "Byculla"), ("Kurla", "Chembur"),
        ]
        for name, pos in MUMBAI_AREAS.items():
            self._node_pos[name] = pos
        for u, v in EDGES:
            pos_u = MUMBAI_AREAS.get(u, {"lat": 19.0, "lng": 72.8})
            pos_v = MUMBAI_AREAS.get(v, {"lat": 19.0, "lng": 72.8})
            dist_km = haversine(pos_u, pos_v)
            length_m = int(dist_km * 1000)
            for fu, fv in [(u, v), (v, u)]:
                self._edges[(fu, fv)] = {
                    "length_m": length_m, "maxspeed": 35, "condition": "open",
                    "flood_prone": False,
                    "geometry": [[pos_u["lat"], pos_u["lng"]], [pos_v["lat"], pos_v["lng"]]],
                    "highway": "secondary",
                }
                self.graph.add_edge(fu, fv, length_m=length_m, maxspeed=35, condition="open")

    # ── Mutation API ───────────────────────────────────────────────────────────

    def update_road_condition(self, from_area: str, to_area: str, condition: str) -> None:
        for u, v in [(from_area, to_area), (to_area, from_area)]:
            if self.graph.has_edge(u, v):
                self.graph[u][v]["condition"] = condition
            if (u, v) in self._edges:
                self._edges[(u, v)]["condition"] = condition

    def sync_roads(self, roads: list[dict]) -> None:
        """Update conditions from the scenario's road state list."""
        for r in roads:
            u = r.get("from", r.get("from_area", ""))
            v = r.get("to", r.get("to_area", ""))
            cond = r.get("condition", "open")
            self.update_road_condition(u, v, cond)

    def roads_as_list(self) -> list[dict]:
        """Return current road state as a list of dicts for the API."""
        seen: set[frozenset] = set()
        result = []
        for (u, v), attrs in self._edges.items():
            key = frozenset([u, v])
            if key in seen:
                continue
            seen.add(key)
            pos_u = self._node_pos.get(u, {"lat": 19.0, "lng": 72.85})
            pos_v = self._node_pos.get(v, {"lat": 19.0, "lng": 72.85})
            # Derive route geometry for the UI
            geom = attrs.get("geometry") or [
                [pos_u["lat"], pos_u["lng"]], [pos_v["lat"], pos_v["lng"]]
            ]
            result.append({
                "id":        f"{u}--{v}",
                "from":      u, "to": v,
                "from_area": u, "to_area": v,
                "fromPos":   pos_u,
                "toPos":     pos_v,
                "condition": attrs["condition"],
                "flood_prone": attrs.get("flood_prone", False),
                "highway":   attrs.get("highway", "secondary"),
                "length_m":  attrs.get("length_m", 1000),
                "geometry":  geom,
            })
        return result

    # ── Routing ───────────────────────────────────────────────────────────────

    def get_travel_time_minutes(
        self,
        start_area: str,
        end_area: str,
        vehicle_type: str = "basic",
    ) -> tuple[float, float, RoutePath]:
        """
        Returns (travel_time_minutes, distance_km, path).
        path is a RoutePath (subclass of list of node names) with a .polyline attribute of [[lat, lng], ...].
        """
        if start_area == end_area:
            pos = self._node_pos.get(start_area, {"lat": 19.05, "lng": 72.84})
            return 2.0, 0.5, RoutePath([start_area], [[pos["lat"], pos["lng"]]])

        # Helicopter ignores roads
        if vehicle_type == "helicopter":
            a = self._node_pos.get(start_area, {"lat": 19.05, "lng": 72.84})
            b = self._node_pos.get(end_area,   {"lat": 19.05, "lng": 72.84})
            dist = haversine(a, b)
            return max(3.0, round((dist / 120.0) * 60, 1)), dist, RoutePath(
                [start_area, end_area],
                [[a["lat"], a["lng"]], [b["lat"], b["lng"]]]
            )

        speed_mult = _SPEED_TABLE.get(vehicle_type, _SPEED_TABLE["basic"])

        # Build a weighted copy with current conditions
        wg = nx.DiGraph()
        for u, v, data in self.graph.edges(data=True):
            cond = data.get("condition", "open")
            mult = speed_mult.get(cond, 0.0)
            if mult <= 0:
                continue  # blocked for this vehicle
            base_speed_ms = data.get("maxspeed", 35) * 1000 / 3600  # m/s
            eff_speed = base_speed_ms * mult
            length_m = data.get("length_m", 1000)
            t_sec = length_m / eff_speed if eff_speed > 0 else 1e9
            wg.add_edge(u, v, weight=t_sec, length_m=length_m)

        if not wg.has_node(start_area) or not wg.has_node(end_area):
            a = self._node_pos.get(start_area, {"lat": 19.05, "lng": 72.84})
            b = self._node_pos.get(end_area,   {"lat": 19.05, "lng": 72.84})
            dist = haversine(a, b)
            return round(dist / 35 * 60, 1), dist, RoutePath(
                [start_area, end_area],
                [[a["lat"], a["lng"]], [b["lat"], b["lng"]]]
            )

        try:
            path_nodes = nx.dijkstra_path(wg, start_area, end_area, weight="weight")
            t_sec_total = nx.dijkstra_path_length(wg, start_area, end_area, weight="weight")
            # Sum real distances and build polyline
            total_dist_m = 0.0
            polyline: list = []
            for i in range(len(path_nodes)):
                name = path_nodes[i]
                if i < len(path_nodes) - 1:
                    u_name, v_name = path_nodes[i], path_nodes[i+1]
                    edge_attrs = self._edges.get((u_name, v_name), {})
                    geom = edge_attrs.get("geometry", [])
                    if geom:
                        polyline.extend(geom if i == 0 else geom[1:])
                    else:
                        pu = self._node_pos.get(u_name, {"lat": 19.05, "lng": 72.84})
                        pv = self._node_pos.get(v_name, {"lat": 19.05, "lng": 72.84})
                        if i == 0:
                            polyline.append([pu["lat"], pu["lng"]])
                        polyline.append([pv["lat"], pv["lng"]])
                    edge_data = self.graph.get_edge_data(u_name, v_name, {})
                    total_dist_m += edge_data.get("length_m", 0)
                else:
                    if not polyline:
                        pos = self._node_pos.get(name, {"lat": 19.05, "lng": 72.84})
                        polyline.append([pos["lat"], pos["lng"]])

            dist_km = round(total_dist_m / 1000, 2)
            return round(t_sec_total / 60, 1), dist_km, RoutePath(path_nodes, polyline)

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            a = self._node_pos.get(start_area, {"lat": 19.05, "lng": 72.84})
            b = self._node_pos.get(end_area,   {"lat": 19.05, "lng": 72.84})
            dist = haversine(a, b)
            return 999.0, round(dist * 2.5, 2), RoutePath([])

    def area_pos(self, name: str) -> dict:
        """Return {lat, lng} for a named area."""
        return self._node_pos.get(name, MUMBAI_AREAS.get(name, {"lat": 19.05, "lng": 72.84}))
