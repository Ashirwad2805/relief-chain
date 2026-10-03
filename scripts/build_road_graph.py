#!/usr/bin/env python3
"""
scripts/build_road_graph.py - Run once to build Mumbai road data.
Outputs:
  backend/data/mumbai_roads.json   - NetworkX routing graph
  public/geo/roads.geojson         - Leaflet offline basemap
  backend/data/flood_zones.geojson - Synthetic flood polygons

MODES:
  REAL     - if osmnx installed + internet available, downloads real OSM data
  SYNTHETIC- deterministic fallback from MUMBAI_AREAS centroids (offline)
"""

from __future__ import annotations
import json, math, os, sys, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
BACKEND_DATA = ROOT / "backend" / "data"
PUBLIC_GEO   = ROOT / "public" / "geo"
BACKEND_DATA.mkdir(parents=True, exist_ok=True)
PUBLIC_GEO.mkdir(parents=True, exist_ok=True)

OUT_ROADS_JSON    = BACKEND_DATA / "mumbai_roads.json"
OUT_ROADS_GEOJSON = PUBLIC_GEO   / "roads.geojson"
OUT_FLOOD_GEOJSON = BACKEND_DATA / "flood_zones.geojson"

BBOX = {"south": 18.88, "north": 19.26, "west": 72.77, "east": 72.95}
MAX_SNAP_M = 150

def haversine_m(a: dict, b: dict) -> float:
    lat1, lon1 = math.radians(a["lat"]), math.radians(a["lng"])
    lat2, lon2 = math.radians(b["lat"]), math.radians(b["lng"])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6_371_000 * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))

try:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.adapters.mumbai_geo import MUMBAI_AREAS, FLOOD_PRONE_AREAS
except ImportError:
    MUMBAI_AREAS = {
        'Andheri':      {'lat': 19.1197, 'lng': 72.8468},
        'Vile Parle':   {'lat': 19.0990, 'lng': 72.8439},
        'Santacruz':    {'lat': 19.0824, 'lng': 72.8432},
        'Juhu':         {'lat': 19.1070, 'lng': 72.8270},
        'Milan Subway': {'lat': 19.1034, 'lng': 72.8493},
        'Bandra':       {'lat': 19.0544, 'lng': 72.8402},
        'Kurla':        {'lat': 19.0717, 'lng': 72.8793},
        'Chembur':      {'lat': 19.0614, 'lng': 72.8996},
        'Ghatkopar':    {'lat': 19.0860, 'lng': 72.9073},
        'Dadar':        {'lat': 19.0209, 'lng': 72.8429},
        'Mahim':        {'lat': 19.0407, 'lng': 72.8406},
        'Sion':         {'lat': 19.0389, 'lng': 72.8619},
        'Sion Circle':  {'lat': 19.0399, 'lng': 72.8618},
        'Hindmata':     {'lat': 19.0251, 'lng': 72.8367},
        'Worli':        {'lat': 19.0176, 'lng': 72.8193},
        'Parel':        {'lat': 19.0040, 'lng': 72.8357},
        'Byculla':      {'lat': 18.9779, 'lng': 72.8340},
        'Colaba':       {'lat': 18.9067, 'lng': 72.8147},
        'Mulund':       {'lat': 19.1724, 'lng': 72.9559},
        'Vikhroli':     {'lat': 19.1070, 'lng': 72.9267},
        'Powai':        {'lat': 19.1176, 'lng': 72.9060},
        'Goregaon':     {'lat': 19.1529, 'lng': 72.8485},
        'Malad':        {'lat': 19.1872, 'lng': 72.8485},
        'Borivali':     {'lat': 19.2294, 'lng': 72.8566},
    }
    FLOOD_PRONE_AREAS = ['Hindmata', 'Milan Subway', 'Sion', 'Sion Circle', 'Kurla', 'Byculla', 'Dadar']


def build_synthetic_graph() -> dict:
    print("Building SYNTHETIC graph from MUMBAI_AREAS centroids...")
    nodes = []
    node_ids: dict[str, int] = {}
    for i, (name, pos) in enumerate(MUMBAI_AREAS.items()):
        node_ids[name] = i
        nodes.append({"id": i, "lat": pos["lat"], "lng": pos["lng"], "name": name})

    CONNECTIONS: list[tuple] = [
        ("Andheri",     "Vile Parle",  "primary",   50),
        ("Andheri",     "Juhu",        "secondary", 40),
        ("Andheri",     "Milan Subway","secondary", 35),
        ("Andheri",     "Goregaon",    "primary",   60),
        ("Vile Parle",  "Santacruz",   "primary",   50),
        ("Santacruz",   "Bandra",      "primary",   50),
        ("Bandra",      "Mahim",       "primary",   50),
        ("Bandra",      "Worli",       "secondary", 45),
        ("Mahim",       "Dadar",       "primary",   40),
        ("Mahim",       "Hindmata",    "secondary", 35),
        ("Dadar",       "Hindmata",    "secondary", 35),
        ("Dadar",       "Sion",        "primary",   45),
        ("Dadar",       "Parel",       "primary",   40),
        ("Dadar",       "Worli",       "secondary", 40),
        ("Hindmata",    "Sion Circle", "secondary", 30),
        ("Sion",        "Sion Circle", "secondary", 30),
        ("Sion",        "Kurla",       "primary",   50),
        ("Sion",        "Byculla",     "primary",   45),
        ("Sion Circle", "Kurla",       "secondary", 35),
        ("Kurla",       "Chembur",     "secondary", 40),
        ("Kurla",       "Ghatkopar",   "primary",   50),
        ("Kurla",       "Vikhroli",    "secondary", 40),
        ("Chembur",     "Ghatkopar",   "secondary", 40),
        ("Ghatkopar",   "Vikhroli",    "primary",   50),
        ("Vikhroli",    "Powai",       "secondary", 40),
        ("Parel",       "Byculla",     "primary",   45),
        ("Parel",       "Worli",       "secondary", 40),
        ("Byculla",     "Colaba",      "primary",   45),
        ("Worli",       "Colaba",      "secondary", 40),
        ("Milan Subway","Andheri",     "secondary", 35),
        ("Goregaon",    "Malad",       "primary",   60),
        ("Malad",       "Borivali",    "primary",   60),
        ("Ghatkopar",   "Mulund",      "primary",   60),
        ("Mulund",      "Borivali",    "secondary", 50),
        ("Powai",       "Mulund",      "secondary", 45),
    ]

    edges = []
    eid = 0
    for from_name, to_name, hw, speed in CONNECTIONS:
        if from_name not in MUMBAI_AREAS or to_name not in MUMBAI_AREAS:
            continue
        a, b = MUMBAI_AREAS[from_name], MUMBAI_AREAS[to_name]
        length_m = int(haversine_m(a, b))
        geom = [[a["lat"], a["lng"]], [b["lat"], b["lng"]]]
        flood = from_name in FLOOD_PRONE_AREAS or to_name in FLOOD_PRONE_AREAS
        for u, v in [(from_name, to_name), (to_name, from_name)]:
            edges.append({
                "id": eid, "u": u, "v": v,
                "length_m": length_m, "highway": hw,
                "name": f"{u}-{v}", "maxspeed": speed,
                "oneway": False, "geometry": geom,
                "flood_prone": flood, "condition": "open",
            })
            eid += 1

    return {
        "graph_source": "synthetic",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bbox": BBOX,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


def snap_report(graph_data: dict) -> None:
    if graph_data["graph_source"] == "synthetic":
        print("\nSnap report: SYNTHETIC - nodes are the area centroids (0 m snap)  OK")
        return
    nodes = graph_data["nodes"]
    print("\nSnap distances:")
    worst_name, worst_dist = "", 0.0
    for name, pos in sorted(MUMBAI_AREAS.items()):
        best_d = min(haversine_m(pos, {"lat": n["lat"], "lng": n["lng"]}) for n in nodes)
        tag = "OK" if best_d < MAX_SNAP_M else "FAIL"
        print(f"  {name:20s}  {best_d:7.1f} m  {tag}")
        if best_d > worst_dist:
            worst_dist, worst_name = best_d, name
    if worst_dist > MAX_SNAP_M:
        print(f"\nBUILD FAILED: {worst_name} snaps to {worst_dist:.1f} m (limit {MAX_SNAP_M} m)")
        sys.exit(1)
    print(f"\nAll areas OK. Worst: {worst_name} @ {worst_dist:.1f} m")


def export_geojson(graph_data: dict) -> None:
    features = []
    for e in graph_data["edges"]:
        if e["id"] % 2 != 0:
            continue
        coords = [[pt[1], pt[0]] for pt in e["geometry"]]
        features.append({
            "type": "Feature",
            "properties": {
                "highway": e["highway"], "name": e.get("name", ""),
                "maxspeed": e.get("maxspeed", 40),
                "flood_prone": e.get("flood_prone", False),
                "condition": e.get("condition", "open"),
            },
            "geometry": {"type": "LineString", "coordinates": coords},
        })
    geojson = {
        "type": "FeatureCollection",
        "source": graph_data["graph_source"],
        "generated_at": graph_data["generated_at"],
        "features": features,
    }
    with open(OUT_ROADS_GEOJSON, "w") as f:
        json.dump(geojson, f, separators=(",", ":"))
    print(f"GeoJSON: {OUT_ROADS_GEOJSON}  ({len(features)} features)")


def export_flood_zones() -> None:
    features = []
    R = 0.004
    for name in FLOOD_PRONE_AREAS:
        if name not in MUMBAI_AREAS:
            continue
        c = MUMBAI_AREAS[name]
        lat, lng = c["lat"], c["lng"]
        coords = [[[lng-R,lat-R],[lng+R,lat-R],[lng+R,lat+R],[lng-R,lat+R],[lng-R,lat-R]]]
        features.append({
            "type": "Feature",
            "properties": {"name": name, "synthetic": True},
            "geometry": {"type": "Polygon", "coordinates": coords},
        })
    geojson = {
        "type": "FeatureCollection",
        "name": "mumbai_flood_zones_synthetic",
        "disclaimer": "SYNTHETIC DATA - Not official MCGM data",
        "features": features,
    }
    with open(OUT_FLOOD_GEOJSON, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"Flood zones: {OUT_FLOOD_GEOJSON}  ({len(features)} zones)")


def main() -> None:
    t0 = time.time()
    try:
        import osmnx as ox  # noqa
        print("osmnx found - attempting OSM download...")
        try:
            from build_road_graph_osmnx import build_osmnx_graph
            graph_data = build_osmnx_graph()
        except Exception as exc:
            print(f"OSM download failed ({exc}); using synthetic fallback")
            graph_data = build_synthetic_graph()
    except ImportError:
        print("osmnx not installed - using synthetic fallback")
        print("  Install: pip install osmnx  (re-run for real OSM data)")
        graph_data = build_synthetic_graph()

    snap_report(graph_data)

    with open(OUT_ROADS_JSON, "w") as f:
        json.dump(graph_data, f, separators=(",", ":"))
    size_kb = os.path.getsize(OUT_ROADS_JSON) / 1024
    print(f"\nRoad graph: {OUT_ROADS_JSON}")
    print(f"  {graph_data['node_count']} nodes, {graph_data['edge_count']} edges, {size_kb:.1f} KB")
    print(f"  Source: {graph_data['graph_source']}")

    export_geojson(graph_data)
    export_flood_zones()
    print(f"\nDone in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
