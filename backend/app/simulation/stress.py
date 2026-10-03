"""
backend/app/simulation/stress.py
================================
Crisis Stress Lab scenario generator (Section 6.1).
Generates high-load synthetic disaster profiles:
- L1: Normal day (40 vehicles, 8 incidents, 20 casualty groups, 5 road changes)
- L2: Major flood (120 vehicles, 25 incidents, 80 casualty groups, 40 road changes)
- L3: Citywide emergency (300 vehicles, 80 incidents, 250 casualty groups, 150 road changes)
- L4: Catastrophe (600 vehicles, 150 incidents, 600 casualty groups, 400 road changes)
- L5: Break test (1200 vehicles, 300 incidents, 1200 casualty groups, 800 road changes)
"""

import random
from app.adapters.mumbai_geo import MUMBAI_AREAS
from app.simulation.scenario import generate_mumbai_scenario

CRISIS_PROFILES = {
    "L1": {"name": "Normal day",           "vehicles": 40,   "incidents": 8,   "groups": 20,   "road_changes": 5,   "budget_fps": 58, "frame_p95": 20, "solve_p95": 300},
    "L2": {"name": "Major flood",          "vehicles": 120,  "incidents": 25,  "groups": 80,   "road_changes": 40,  "budget_fps": 55, "frame_p95": 24, "solve_p95": 500},
    "L3": {"name": "Citywide emergency",   "vehicles": 300,  "incidents": 80,  "groups": 250,  "road_changes": 150, "budget_fps": 45, "frame_p95": 32, "solve_p95": 500},
    "L4": {"name": "Catastrophe",          "vehicles": 600,  "incidents": 150, "groups": 600,  "road_changes": 400, "budget_fps": 30, "frame_p95": 50, "solve_p95": 800},
    "L5": {"name": "Break test",           "vehicles": 1200, "incidents": 300, "groups": 1200, "road_changes": 800, "budget_fps": 15, "frame_p95": 80, "solve_p95": 1200},
}


def generate_stress_scenario(level: str = "L2", seed: int = 42) -> dict:
    profile = CRISIS_PROFILES.get(level.upper(), CRISIS_PROFILES["L2"])
    rng = random.Random(seed)
    base = generate_mumbai_scenario(seed)

    areas = list(MUMBAI_AREAS.keys())
    types = ["basic", "advanced", "icu", "boat", "helicopter"]

    # 1. Scale ambulances to profile count
    ambulances = list(base["ambulances"])
    start_id = len(ambulances) + 1
    while len(ambulances) < profile["vehicles"]:
        a_type = rng.choice(types)
        area = rng.choice(areas)
        pos = MUMBAI_AREAS[area]
        ambulances.append({
            "id": f"AMB-{start_id:04d}",
            "type": a_type,
            "status": rng.choice(["idle", "dispatched", "transporting"]),
            "position": {
                "lat": pos["lat"] + rng.uniform(-0.02, 0.02),
                "lng": pos["lng"] + rng.uniform(-0.02, 0.02)
            },
            "homeHospital": rng.choice(base["hospitals"])["id"],
            "assignedIncidentId": None,
            "assignedHospitalId": None
        })
        start_id += 1
    ambulances = ambulances[:profile["vehicles"]]

    # 2. Scale casualty incidents to profile count
    incidents = list(base["incidents"])
    inc_id = len(incidents) + 1
    severities = ["red", "yellow", "green"]
    while len(incidents) < profile["incidents"]:
        sev = rng.choices(severities, weights=[0.4, 0.4, 0.2])[0]
        area = rng.choice(areas)
        pos = MUMBAI_AREAS[area]
        red = rng.randint(2, 12) if sev == "red" else rng.randint(0, 3)
        yel = rng.randint(2, 15)
        grn = rng.randint(5, 20)
        incidents.append({
            "id": f"INC-STRESS-{inc_id:04d}",
            "label": f"Crisis Surge {inc_id} — {area}",
            "severity": sev,
            "area": area,
            "position": {
                "lat": pos["lat"] + rng.uniform(-0.02, 0.02),
                "lng": pos["lng"] + rng.uniform(-0.02, 0.02)
            },
            "patientCount": red + yel + grn,
            "redPatients": red,
            "yellowPatients": yel,
            "greenPatients": grn,
            "bloodNeeded": rng.sample(["O+", "A+", "B+", "O-", "AB+"], k=rng.randint(1, 3)),
            "urgency": rng.randint(70, 99) if sev == "red" else rng.randint(40, 75),
            "slaMinutes": 15 if sev == "red" else 45,
            "createdAt": 0.0,
            "status": "active",
            "description": f"Crisis Stress Lab casualty group (Simulated Load {level})"
        })
        inc_id += 1
    incidents = incidents[:profile["incidents"]]

    # 3. Dynamic road conditions
    roads = list(base["roads"])
    for r in roads[:profile["road_changes"]]:
        r["condition"] = rng.choice(["open", "slow", "flooded", "blocked"])

    return {
        "level": level,
        "profile": profile,
        "hospitals": base["hospitals"],
        "ambulances": ambulances,
        "incidents": incidents,
        "roads": roads,
        "supplies": base["supplies"],
        "supplyRequests": base["supplyRequests"],
        "funds": base["funds"],
        "simTime": 0.0
    }
