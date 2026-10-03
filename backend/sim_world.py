"""
ReliefChain Simulation World — Python port of src/sim/world.ts + ledger.ts + anomaly.ts
Deterministic seeded state for Mumbai disaster-relief scenario.
"""
from __future__ import annotations

import math
import hashlib
import json
import time
import copy
from dataclasses import dataclass, field, asdict
from typing import Any

# ── Seeded PRNG (mulberry32) ─────────────────────────────────────────────────

SEED = 42


class Rng:
    def __init__(self, seed: int = SEED):
        self._state = seed & 0xFFFFFFFF

    def next(self) -> float:
        self._state = (self._state + 0x6D2B79F5) & 0xFFFFFFFF
        t = (self._state ^ (self._state >> 15)) * (1 | self._state)
        t = ((t + ((t ^ (t >> 7)) * (61 | t))) ^ t) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    def int(self, lo: int, hi: int) -> int:
        return math.floor(self.next() * (hi - lo + 1)) + lo

    def pick(self, arr: list):
        return arr[math.floor(self.next() * len(arr))]

    def bool(self, prob: float = 0.5) -> bool:
        return self.next() < prob


# ── Geography ────────────────────────────────────────────────────────────────

MUMBAI_AREAS: dict[str, dict[str, float]] = {
    "Andheri":       {"lat": 19.1197, "lng": 72.8468},
    "Sion":          {"lat": 19.0760, "lng": 72.8530},
    "Hindmata":      {"lat": 19.0730, "lng": 72.8360},
    "Milan Subway":  {"lat": 19.1030, "lng": 72.8410},
    "Sion Circle":   {"lat": 19.0758, "lng": 72.8535},
    "Bandra":        {"lat": 19.0690, "lng": 72.8390},
    "Dadar":         {"lat": 19.0850, "lng": 72.8430},
    "Kurla":         {"lat": 19.0720, "lng": 72.8780},
    "Juhu":          {"lat": 19.1070, "lng": 72.8380},
    "Worli":         {"lat": 19.0170, "lng": 72.8230},
}


def haversine_km(a: dict, b: dict) -> float:
    R = 6371
    dLat = math.radians(b["lat"] - a["lat"])
    dLng = math.radians(b["lng"] - a["lng"])
    lat1 = math.radians(a["lat"])
    lat2 = math.radians(b["lat"])
    h = math.sin(dLat / 2) ** 2 + math.sin(dLng / 2) ** 2 * math.cos(lat1) * math.cos(lat2)
    return 2 * R * math.asin(math.sqrt(h))


# ── Hash helpers ─────────────────────────────────────────────────────────────

def _demo_sha256(s: str) -> str:
    """Lightweight deterministic hash matching the TypeScript frontend."""
    h = 0
    h2 = 0x811C9DC5 & 0xFFFFFFFF
    for ch in s:
        c = ord(ch)
        h = ((h << 5) - h + c) & 0xFFFFFFFF
        h2 = h2 ^ c
        # imul approximation
        h2 = (h2 * 0x01000193) & 0xFFFFFFFF
    p1 = format(h & 0xFFFFFFFF, '08x')
    p2 = format(h2 & 0xFFFFFFFF, '08x')
    return (p1 + p2 + "a" * 48)[:64]


def real_sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ── Init functions ───────────────────────────────────────────────────────────

def _blood_stock(rng: Rng) -> dict[str, int]:
    return {
        "A+": rng.int(5, 20), "A-": rng.int(2, 10),
        "B+": rng.int(5, 20), "B-": rng.int(2, 10),
        "O+": rng.int(8, 30), "O-": rng.int(3, 15),
        "AB+": rng.int(2, 8), "AB-": rng.int(1, 5),
    }


def init_hospitals(rng: Rng) -> list[dict]:
    defs = [
        {"id": "H1", "name": "KEM Hospital", "area": "Sion", "specialty": ["trauma", "cardiac", "pediatric"], "cap": {"er": 40, "icu": 20, "ward": 100}},
        {"id": "H2", "name": "Lokmanya Tilak (Sion)", "area": "Sion", "specialty": ["trauma", "neuro"], "cap": {"er": 35, "icu": 15, "ward": 80}},
        {"id": "H3", "name": "Holy Spirit Hospital", "area": "Andheri", "specialty": ["cardiac", "general"], "cap": {"er": 25, "icu": 12, "ward": 60}},
        {"id": "H4", "name": "Cooper Hospital", "area": "Bandra", "specialty": ["trauma", "pediatric"], "cap": {"er": 30, "icu": 14, "ward": 70}},
        {"id": "H5", "name": "Hinduja Hospital", "area": "Worli", "specialty": ["neuro", "cardiac", "trauma"], "cap": {"er": 30, "icu": 18, "ward": 90}},
        {"id": "H6", "name": "Breach Candy", "area": "Worli", "specialty": ["general", "cardiac"], "cap": {"er": 20, "icu": 10, "ward": 50}},
        {"id": "H7", "name": "Nanavati Hospital", "area": "Juhu", "specialty": ["trauma", "general", "pediatric"], "cap": {"er": 28, "icu": 12, "ward": 65}},
        {"id": "H8", "name": "Fortis Mulund", "area": "Kurla", "specialty": ["cardiac", "neuro"], "cap": {"er": 22, "icu": 10, "ward": 55}},
    ]
    out = []
    for d in defs:
        cap = d["cap"]
        out.append({
            "id": d["id"],
            "name": d["name"],
            "area": d["area"],
            "specialty": d["specialty"],
            "capacity": cap,
            "occupied": {
                "er": rng.int(10, cap["er"] - 5),
                "icu": rng.int(5, cap["icu"] - 2),
                "ward": rng.int(30, cap["ward"] - 10),
            },
            "blood": _blood_stock(rng),
            "status": "operational",
            "position": MUMBAI_AREAS[d["area"]],
        })
    return out


def init_ambulances(rng: Rng) -> list[dict]:
    types = ["basic", "advanced", "icu", "boat"]
    homes = ["H1", "H2", "H3", "H4", "H5", "H7"]
    ambs = []
    for i in range(1, 13):
        t = types[i % len(types)]
        h = homes[i % len(homes)]
        ambs.append({
            "id": f"AMB-{i:02d}",
            "type": t,
            "status": "idle",
            "position": {"lat": 19.05 + rng.next() * 0.08, "lng": 72.82 + rng.next() * 0.06},
            "assignedIncidentId": None,
            "assignedHospitalId": None,
            "fuel": rng.int(60, 100),
            "homeHospital": h,
            "capability": 3 if t == "icu" else 2 if t in ("advanced", "boat") else 1,
        })
    return ambs


def init_incidents(rng: Rng) -> list[dict]:
    defs = [
        {"label": "Building Collapse – Dadar", "area": "Dadar", "sev": "red", "red": 18, "yellow": 12, "green": 20, "desc": "3-storey residential collapse, multiple trapped"},
        {"label": "Flooding – Hindmata Junction", "area": "Hindmata", "sev": "red", "red": 12, "yellow": 25, "green": 40, "desc": "Severe waterlogging, stranded residents"},
        {"label": "Andheri Subway Flood", "area": "Andheri", "sev": "yellow", "red": 5, "yellow": 18, "green": 30, "desc": "Subway under 4ft water, vehicles submerged"},
        {"label": "Milan Subway Overflow", "area": "Milan Subway", "sev": "yellow", "red": 3, "yellow": 10, "green": 15, "desc": "Traffic gridlock, medical emergencies"},
        {"label": "Sion Circle Waterlogging", "area": "Sion Circle", "sev": "yellow", "red": 4, "yellow": 8, "green": 20, "desc": "Major junction flooded, ambulance access difficult"},
    ]
    out = []
    for i, d in enumerate(defs):
        pos = MUMBAI_AREAS[d["area"]]
        out.append({
            "id": f"INC-{i + 1:03d}",
            "label": d["label"],
            "severity": d["sev"],
            "area": d["area"],
            "position": {"lat": pos["lat"] + (rng.next() - 0.5) * 0.01, "lng": pos["lng"] + (rng.next() - 0.5) * 0.01},
            "patientCount": d["red"] + d["yellow"] + d["green"],
            "redPatients": d["red"],
            "yellowPatients": d["yellow"],
            "greenPatients": d["green"],
            "blackPatients": 0,
            "bloodNeeded": ["O-", "B+"] if d["sev"] == "red" else ["O+"],
            "urgency": rng.int(85, 100) if d["sev"] == "red" else rng.int(40, 70),
            "slaMinutes": 15 if d["sev"] == "red" else 30,
            "createdAt": rng.int(0, 5),
            "status": "active",
            "description": d["desc"],
            "assignedAmbulanceId": None,
            "assignedHospitalId": None,
            "etaMinutes": None,
        })
    return out


def init_roads(rng: Rng) -> list[dict]:
    defs = [
        ("Andheri", "Sion"), ("Sion", "Dadar"), ("Dadar", "Hindmata"),
        ("Hindmata", "Sion Circle"), ("Sion Circle", "Sion"),
        ("Milan Subway", "Andheri"), ("Bandra", "Sion"),
        ("Andheri", "Juhu"), ("Worli", "Dadar"), ("Kurla", "Sion"),
    ]
    out = []
    for i, (f, t) in enumerate(defs):
        cond = "flooded" if rng.bool(0.25) else ("slow" if rng.bool(0.1) else "open")
        out.append({
            "id": f"R{i + 1}",
            "from": f, "to": t,
            "condition": cond,
            "fromPos": MUMBAI_AREAS[f],
            "toPos": MUMBAI_AREAS[t],
        })
    return out


def init_supplies() -> list[dict]:
    items = [
        ("IV Fluids", "medical", 500, "units"),
        ("Bandages", "medical", 2000, "rolls"),
        ("Oxygen Cylinders", "medical", 80, "cylinders"),
        ("Tetanus Vials", "medical", 300, "vials"),
        ("Water Bottles", "water", 5000, "bottles"),
        ("Food Packets", "food", 3000, "packets"),
        ("Tarpaulin Sheets", "shelter", 200, "sheets"),
        ("Diesel", "fuel", 500, "liters"),
    ]
    locs = ["H1", "H3", "H5", "Warehouse-Kurla"]
    return [
        {
            "id": f"SUP-{i + 1:03d}",
            "name": name, "type": typ, "quantity": qty, "unit": unit,
            "location": locs[i % 4],
            "status": "stuck" if i == 7 else "available",
        }
        for i, (name, typ, qty, unit) in enumerate(items)
    ]


def init_supply_requests(rng: Rng) -> list[dict]:
    reqs = [
        ("Oxygen Cylinders", 20, "cylinders", "KEM Hospital", "Sion", "urgent"),
        ("IV Fluids", 100, "units", "Cooper Hospital", "Bandra", "high"),
        ("Water Bottles", 500, "bottles", "Relief Camp Dadar", "Dadar", "normal"),
        ("Food Packets", 300, "packets", "Relief Camp Hindmata", "Hindmata", "high"),
    ]
    return [
        {
            "id": f"REQ-{i + 1:03d}",
            "item": item, "quantity": qty, "unit": unit,
            "requester": req, "area": area, "priority": pri,
            "status": "pending",
            "createdAt": rng.int(0, 10),
        }
        for i, (item, qty, unit, req, area, pri) in enumerate(reqs)
    ]


def init_events() -> list[dict]:
    return [
        {"id": 1, "time": 1, "title": "Initial Flooding", "description": "Heavy rainfall causes widespread flooding across low-lying areas of Mumbai", "type": "flood", "triggered": False},
        {"id": 2, "time": 2, "title": "Building Collapse – Dadar", "description": "3-storey residential building collapses near Dadar, 18 critical patients", "type": "collapse", "triggered": False},
        {"id": 3, "time": 4, "title": "Andheri Subway Floods", "description": "Andheri subway under 4ft water, vehicles submerged", "type": "flood", "triggered": False},
        {"id": 4, "time": 5, "title": "Hospital ICU Reaches Capacity", "description": "Lokmanya Tilak ICU fully occupied, diverting critical patients", "type": "capacity", "triggered": False},
        {"id": 5, "time": 6, "title": "O-Negative Shortage", "description": "City-wide O-negative blood inventory drops critically low", "type": "blood", "triggered": False},
        {"id": 6, "time": 7, "title": "Ambulance Breakdown", "description": "AMB-04 engine failure near Sion Circle", "type": "ambulance", "triggered": False},
        {"id": 7, "time": 8, "title": "Flooded-Zone Casualty Cluster", "description": "20+ casualties reported in Hindmata flooded zone", "type": "casualty", "triggered": False},
        {"id": 8, "time": 9, "title": "Bridge Closure", "description": "Sion-Dadar bridge closed due to structural concerns", "type": "road", "triggered": False},
        {"id": 9, "time": 10, "title": "Hospital Power Failure", "description": "Cooper Hospital loses grid power, running on backup generator", "type": "power", "triggered": False},
        {"id": 10, "time": 11, "title": "Pediatric Surge", "description": "15 children among new casualties at Hindmata, need pediatric ICU", "type": "surge", "triggered": False},
        {"id": 11, "time": 12, "title": "Donor Funds Arrive", "description": "₹2 crore pledged by Mumbai Business Council for relief operations", "type": "funds", "triggered": False},
        {"id": 12, "time": 13, "title": "Supply Truck Stuck", "description": "Supply truck carrying oxygen cylinders stranded at Kurla junction", "type": "supply", "triggered": False},
        {"id": 13, "time": 14, "title": "Duplicate Beneficiary Anomaly", "description": "Same Aadhaar number registered at two relief camps", "type": "anomaly", "triggered": False},
        {"id": 14, "time": 15, "title": "Road Reopens", "description": "Bandra-Sion road cleared by municipal crews", "type": "road", "triggered": False},
    ]


def init_funds() -> list[dict]:
    return [
        {"id": "F1", "donor": "Mumbai Business Council", "amount": 50000000, "purpose": "General Relief", "stage": "audited", "recipient": "Emergency Pool", "timestamp": 0},
        {"id": "F2", "donor": "Tata Trusts", "amount": 30000000, "purpose": "Medical Supplies", "stage": "disbursed", "recipient": "KEM Hospital", "timestamp": 2},
        {"id": "F3", "donor": "Reliance Foundation", "amount": 25000000, "purpose": "Shelter & Food", "stage": "released", "recipient": "NGO-Pratham", "timestamp": 4},
        {"id": "F4", "donor": "HDFC ERGO", "amount": 10000000, "purpose": "Ambulance Fuel", "stage": "pledged", "recipient": "Fleet Ops", "timestamp": 6},
        {"id": "F5", "donor": "Individual Donors (412)", "amount": 8500000, "purpose": "Blood Bank Support", "stage": "pledged", "recipient": "Emergency Pool", "timestamp": 8},
        {"id": "F6", "donor": "Maharashtra Govt", "amount": 40000000, "purpose": "Infrastructure Repair", "stage": "pledged", "recipient": "Public Works", "timestamp": 10},
        {"id": "F7", "donor": "BCCI Relief Fund", "amount": 15000000, "purpose": "Medical Equipment", "stage": "pledged", "recipient": "Emergency Pool", "timestamp": 12},
    ]


def init_anomalies() -> list[dict]:
    return [
        {
            "id": "AN-001", "type": "duplicate_beneficiary", "severity": "high",
            "description": "Aadhaar number XXXX-XXXX-1234 registered at both Dadar and Hindmata relief camps within 5 minutes",
            "status": "investigating", "entityId": "R-0451", "detectedAt": 14,
            "notes": "Field team dispatched to verify identity.",
        },
        {
            "id": "AN-002", "type": "over_allocation", "severity": "medium",
            "description": "KEM Hospital received 40 oxygen cylinders but only reported 25 in use",
            "status": "open", "entityId": "REQ-001", "detectedAt": 13, "notes": "",
        },
        {
            "id": "AN-003", "type": "ghost_delivery", "severity": "critical",
            "description": "Delivery confirmation for food packets to Relief Camp Worli, but camp reports no receipt",
            "status": "open", "entityId": "LED-0038", "detectedAt": 12,
            "notes": "Escalated to law enforcement.",
        },
        {
            "id": "AN-004", "type": "unusual_pricing", "severity": "medium",
            "description": "Vendor MedSupply Co. charged 3x market rate for IV fluids",
            "status": "open", "entityId": "VND-003", "detectedAt": 13, "notes": "",
        },
    ]


# ── Ledger ───────────────────────────────────────────────────────────────────

def compute_merkle_root(entries: list[dict]) -> str:
    if not entries:
        return _demo_sha256("empty")
    hashes = [_demo_sha256(json.dumps(e, sort_keys=True)) for e in entries]
    while len(hashes) > 1:
        nxt = []
        for i in range(0, len(hashes), 2):
            if i + 1 < len(hashes):
                nxt.append(_demo_sha256(hashes[i] + hashes[i + 1]))
            else:
                nxt.append(_demo_sha256(hashes[i]))
        hashes = nxt
    return hashes[0]


def create_block(prev: dict | None, entries: list[dict], ts: float) -> dict:
    idx = (prev["index"] + 1) if prev else 0
    prev_hash = prev["hash"] if prev else "0" * 64
    merkle = compute_merkle_root(entries)
    h = _demo_sha256(f"{idx}{ts}{prev_hash}{merkle}{len(entries)}")
    return {
        "index": idx, "timestamp": ts, "simTime": 0.0,
        "previousHash": prev_hash, "hash": h, "merkleRoot": merkle,
        "entries": entries, "verified": True,
    }


def init_ledger() -> list[dict]:
    """Build initial 3-block chain."""
    entries0 = [
        {"type": "fund_pledge", "description": "₹5 Cr pledge from Mumbai Business Council", "entityId": "F1", "amount": 50000000},
        {"type": "fund_pledge", "description": "₹3 Cr pledge from Tata Trusts", "entityId": "F2", "amount": 30000000},
    ]
    entries1 = [
        {"type": "allocation", "description": "AMB-01 dispatched to INC-001 → KEM Hospital", "entityId": "DEC-INIT-1"},
        {"type": "supply_transfer", "description": "20 Oxygen Cylinders → KEM Hospital", "entityId": "SUP-003", "amount": 20},
    ]
    entries2 = [
        {"type": "dispatch", "description": "AMB-03 en-route to Hindmata Junction", "entityId": "AMB-03"},
        {"type": "delivery_confirmation", "description": "500 IV Fluids delivered to Sion Hospital", "entityId": "SUP-001", "amount": 500},
    ]
    b0 = create_block(None, entries0, 0)
    b1 = create_block(b0, entries1, 1)
    b2 = create_block(b1, entries2, 2)
    return [b0, b1, b2]


# ── Stats ────────────────────────────────────────────────────────────────────

def compute_stats(world: dict) -> dict:
    hospitals = world["hospitals"]
    ambulances = world["ambulances"]
    incidents = world["incidents"]
    supply_reqs = world.get("supplyRequests", [])

    active_inc = [i for i in incidents if i["status"] in ("active", "assigned")]
    active_amb = [a for a in ambulances if a["status"] not in ("idle", "broken")]
    overloads = sum(1 for h in hospitals if h["status"] in ("overloaded", "full"))

    total_red = sum(i["redPatients"] for i in incidents)
    total_yellow = sum(i["yellowPatients"] for i in incidents)

    total_blood = sum(sum(h["blood"].values()) for h in hospitals)
    total_icu = sum(h["capacity"]["icu"] - h["occupied"]["icu"] for h in hospitals)
    total_icu_cap = sum(h["capacity"]["icu"] for h in hospitals)

    return {
        "estimatedSurvivors": max(0, total_red - len(active_inc)),
        "baselineSurvivors": max(0, int(total_red * 0.55)),
        "avgRedTreatmentTime": 12.5,
        "worstTreatmentTime": 28.0,
        "icuOverloads": overloads,
        "unservedCritical": sum(1 for i in active_inc if i["severity"] == "red"),
        "ambulanceUtilization": round(len(active_amb) / max(1, len(ambulances)) * 100, 1),
        "equityScore": 78.5,
        "pendingDecisions": len(world.get("decisions", [])),
        "activeAmbulances": len(active_amb),
        "activeIncidents": len(active_inc),
        "hospitalOverloads": overloads,
        "activeSupplyRequests": sum(1 for r in supply_reqs if r["status"] == "pending"),
        "bloodAvailability": total_blood,
        "icuAvailability": round(total_icu / max(1, total_icu_cap) * 100, 1),
    }


# ── Allocation engine ───────────────────────────────────────────────────────

def score_hospital(incident: dict, hospital: dict, ambulance: dict, roads: list[dict]) -> dict:
    dist = haversine_km(incident["position"], hospital["position"])

    blocked = False
    flooded = False
    factor = 1.0
    for r in roads:
        connects = r["from"] == incident["area"] or r["to"] == incident["area"] or r["from"] == hospital["area"] or r["to"] == hospital["area"]
        if connects:
            if r["condition"] == "blocked":
                blocked = True; factor *= 1.5
            if r["condition"] == "flooded":
                flooded = True; factor *= 1.3
            if r["condition"] == "slow":
                factor *= 1.15

    base_speed = 20 if ambulance["type"] == "boat" else 35
    eta = max(1, round(dist / base_speed * 60 * factor))

    icu_avail = hospital["capacity"]["icu"] - hospital["occupied"]["icu"]
    er_avail = hospital["capacity"]["er"] - hospital["occupied"]["er"]

    score = 100
    reasons = []
    score -= dist * 3
    score -= eta * 2

    if incident["redPatients"] > 0:
        proj = max(0, icu_avail - int(incident["redPatients"] * 0.6))
        if proj >= incident["redPatients"]:
            score += 40; reasons.append("ICU capacity available")
        elif proj > 0:
            score += 15; reasons.append("Partial ICU capacity")
        else:
            score -= 50; reasons.append("ICU projected full")

    if er_avail > 5:
        score += 20; reasons.append("ER beds available")
    elif er_avail > 0:
        score += 5
    else:
        score -= 30; reasons.append("ER full")

    if incident["severity"] == "red":
        if "trauma" in hospital["specialty"]:
            score += 25; reasons.append("Trauma specialty")
        else:
            score -= 15

    blood_ok = True
    for bt in incident.get("bloodNeeded", []):
        if hospital["blood"].get(bt, 0) < 5:
            blood_ok = False
    if blood_ok:
        score += 20; reasons.append("Blood compatible")
    else:
        score -= 30; reasons.append("Blood stock insufficient")

    if blocked:
        score -= 40; reasons.append("Bridge/road blocked")
    if flooded:
        score -= 15
    if not blocked and not flooded:
        reasons.append("Road accessible")

    if hospital["status"] == "power_failure":
        score -= 25; reasons.append("Power failure")
    if hospital["status"] in ("overloaded", "full"):
        score -= 35; reasons.append("Hospital overloaded")

    if ambulance["type"] == "boat" and flooded:
        score += 25; reasons.append("Boat ambulance for flooded zone")

    load_ratio = hospital["occupied"]["er"] / max(1, hospital["capacity"]["er"])
    score -= load_ratio * 10

    return {"score": round(score), "distance": dist, "eta": eta, "reasons": reasons, "icuAvail": icu_avail}


def allocate(incident: dict, ambulances: list, hospitals: list, roads: list, engine: str, sim_time: float) -> dict | None:
    avail = [a for a in ambulances if a["status"] == "idle" and a["fuel"] > 10]
    if not avail:
        return None

    best_amb = min(avail, key=lambda a: haversine_km(a["position"], incident["position"]))

    scored = []
    for h in hospitals:
        if h["status"] == "full":
            continue
        if engine == "baseline":
            d = haversine_km(incident["position"], h["position"])
            scored.append({"hospital": h, "score": -d, "distance": d, "eta": max(1, round(d / 35 * 60)), "reasons": ["Nearest available hospital"], "icuAvail": h["capacity"]["icu"] - h["occupied"]["icu"]})
        else:
            r = score_hospital(incident, h, best_amb, roads)
            scored.append({"hospital": h, **r})

    if not scored:
        return None
    scored.sort(key=lambda x: x["score"], reverse=True)
    selected = scored[0]

    nearest = min(hospitals, key=lambda h: haversine_km(incident["position"], h["position"]))

    alternatives = [
        {
            "hospitalId": s["hospital"]["id"],
            "hospitalName": s["hospital"]["name"],
            "etaMinutes": s["eta"],
            "icuAvail": s["icuAvail"],
            "score": s["score"],
        }
        for s in scored[:5]
    ]

    exp_surv = round(incident["redPatients"] * (0.9 if selected["score"] > 80 else 0.7 if selected["score"] > 50 else 0.5) + incident["yellowPatients"] * 0.4)
    base_surv = round(incident["redPatients"] * 0.55 + incident["yellowPatients"] * 0.35)

    import random
    dec_id = f"DEC-{random.randint(100000, 999999)}"

    return {
        "id": dec_id,
        "incidentId": incident["id"],
        "ambulanceId": best_amb["id"],
        "hospitalId": selected["hospital"]["id"],
        "selectedHospitalName": selected["hospital"]["name"],
        "action": f"Dispatch {best_amb['id']} → {selected['hospital']['name']}",
        "priority": incident.get("urgency", 50),
        "status": "suggested",
        "engine": engine,
        "explanation": {
            "score": selected["score"],
            "expectedSurvivors": exp_surv,
            "baselineSurvivors": base_surv,
            "reasoning": "; ".join(selected["reasons"]),
            "alternatives": alternatives,
            "constraints": [
                f"Red patients: {incident['redPatients']}",
                f"SLA: {incident['slaMinutes']} min",
                f"ETA: {selected['eta']} min",
            ],
        },
        "alternatives": [{"etaMinutes": a["eta"], "hospitalName": a["hospital"]["name"]} for a in scored[:3]],
    }


# ── World State Manager ─────────────────────────────────────────────────────

class SimWorld:
    """Holds the full simulation world. Single instance per server."""

    def __init__(self):
        self.reset()

    def reset(self):
        rng = Rng(SEED)
        self.sim_time: float = 0.0
        self.start_time: float = time.time()
        self.running: bool = False
        self.speed: float = 1.0
        self.hospitals = init_hospitals(rng)
        self.ambulances = init_ambulances(rng)
        self.incidents = init_incidents(rng)
        self.roads = init_roads(rng)
        self.supplies = init_supplies()
        self.supply_requests = init_supply_requests(rng)
        self.events = init_events()
        self.decisions: list[dict] = []
        self.ledger = init_ledger()
        self.funds = init_funds()
        self.anomalies = init_anomalies()
        self.alert: str | None = None
        self.autopilot_active: bool = False
        self.autopilot_step: int = 0
        self._seq: int = 0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def snapshot(self) -> dict:
        stats = compute_stats(self._as_world_dict())
        return {
            "simTime": self.sim_time,
            "startTime": self.start_time,
            "running": self.running,
            "speed": self.speed,
            "hospitals": self.hospitals,
            "ambulances": self.ambulances,
            "incidents": self.incidents,
            "roads": self.roads,
            "supplies": self.supplies,
            "supplyRequests": self.supply_requests,
            "decisions": self.decisions,
            "events": self.events,
            "ledger": self.ledger,
            "funds": self.funds,
            "anomalies": self.anomalies,
            "stats": stats,
            "alert": self.alert,
            "autopilotActive": self.autopilot_active,
            "autopilotStep": self.autopilot_step,
        }

    def _as_world_dict(self) -> dict:
        return {
            "hospitals": self.hospitals,
            "ambulances": self.ambulances,
            "incidents": self.incidents,
            "supplyRequests": self.supply_requests,
            "decisions": self.decisions,
        }

    def tick(self, dt: float = 0.5) -> dict:
        """Advance simulation by dt minutes."""
        self.sim_time += dt

        # Process scheduled events
        for ev in self.events:
            if not ev["triggered"] and ev["time"] <= self.sim_time:
                ev["triggered"] = True
                self._apply_event(ev)

        # Move ambulances
        for amb in self.ambulances:
            if amb["status"] == "dispatched" and amb["assignedIncidentId"]:
                amb["fuel"] = max(0, amb["fuel"] - dt * 2)
                if amb["fuel"] <= 0:
                    amb["status"] = "broken"

        # Auto-allocate unassigned active incidents (when running)
        for inc in self.incidents:
            if inc["status"] == "active" and inc["assignedAmbulanceId"] is None:
                dec = allocate(inc, self.ambulances, self.hospitals, self.roads, "reliefchain", self.sim_time)
                if dec:
                    self.decisions.append(dec)
                    # Apply assignment
                    inc["status"] = "assigned"
                    inc["assignedAmbulanceId"] = dec["ambulanceId"]
                    inc["assignedHospitalId"] = dec["hospitalId"]
                    inc["etaMinutes"] = dec["explanation"]["alternatives"][0]["etaMinutes"] if dec["explanation"]["alternatives"] else None
                    # Mark ambulance as dispatched
                    for a in self.ambulances:
                        if a["id"] == dec["ambulanceId"]:
                            a["status"] = "dispatched"
                            a["assignedIncidentId"] = inc["id"]
                            a["assignedHospitalId"] = dec["hospitalId"]
                            break

        return self.snapshot()

    def _apply_event(self, ev: dict):
        """Apply event side-effects to the world state."""
        etype = ev["type"]
        if etype == "capacity":
            for h in self.hospitals:
                if h["id"] == "H2":
                    h["occupied"]["icu"] = h["capacity"]["icu"]
                    h["status"] = "overloaded"
        elif etype == "blood":
            for h in self.hospitals:
                h["blood"]["O-"] = max(0, h["blood"]["O-"] - 3)
        elif etype == "ambulance":
            for a in self.ambulances:
                if a["id"] == "AMB-04":
                    a["status"] = "broken"
                    a["fuel"] = 0
        elif etype == "road":
            if ev["id"] == 8:
                for r in self.roads:
                    if r["from"] == "Sion" and r["to"] == "Dadar":
                        r["condition"] = "blocked"
            elif ev["id"] == 14:
                for r in self.roads:
                    if r["from"] == "Bandra" and r["to"] == "Sion":
                        r["condition"] = "open"
        elif etype == "power":
            for h in self.hospitals:
                if h["id"] == "H4":
                    h["status"] = "power_failure"
        elif etype == "funds":
            self.funds.append({
                "id": f"F{len(self.funds) + 1}",
                "donor": "Mumbai Business Council (Additional)",
                "amount": 20000000,
                "purpose": "Emergency Relief",
                "stage": "pledged",
                "recipient": "Emergency Pool",
                "timestamp": self.sim_time,
            })
        self.alert = ev["title"]

    def apply_chaos(self, action: str) -> dict:
        """Apply a chaos action."""
        lower = action.lower()
        if lower.startswith("flood"):
            area = action.split(" ", 1)[-1] if " " in action else "Hindmata"
            for r in self.roads:
                if r["from"] == area or r["to"] == area:
                    r["condition"] = "flooded"
            self.alert = f"Chaos: {area} roads flooded"
        elif lower.startswith("close"):
            area = action.split(" ", 1)[-1] if " " in action else "Sion Circle"
            for r in self.roads:
                if r["from"] == area or r["to"] == area:
                    r["condition"] = "blocked"
            self.alert = f"Chaos: {area} roads closed"
        elif lower.startswith("power"):
            for h in self.hospitals:
                h["status"] = "power_failure"
            self.alert = "Chaos: All hospitals lost power"
        elif lower.startswith("allocate"):
            parts = action.split()
            if len(parts) >= 2:
                inc_id = parts[1]
                inc = next((i for i in self.incidents if i["id"] == inc_id), None)
                if inc:
                    dec = allocate(inc, self.ambulances, self.hospitals, self.roads, "reliefchain", self.sim_time)
                    if dec:
                        self.decisions.append(dec)
                        inc["status"] = "assigned"
                        inc["assignedAmbulanceId"] = dec["ambulanceId"]
                        inc["assignedHospitalId"] = dec["hospitalId"]
        elif lower.startswith("break"):
            for a in self.ambulances:
                if a["status"] == "idle":
                    a["status"] = "broken"
                    a["fuel"] = 0
                    self.alert = f"Chaos: {a['id']} broken down"
                    break
        else:
            self.alert = f"Chaos: {action}"
        return self.snapshot()

    def verify_ledger(self) -> dict:
        for i, block in enumerate(self.ledger):
            expected_prev = "0" * 64 if i == 0 else self.ledger[i - 1]["hash"]
            if block["previousHash"] != expected_prev:
                return {"valid": False, "corruptedBlock": block["index"],
                        "reason": f"Hash mismatch: block {block['index']} previousHash does not match"}
            expected_merkle = compute_merkle_root(block["entries"])
            if block["merkleRoot"] != expected_merkle:
                return {"valid": False, "corruptedBlock": block["index"],
                        "reason": f"Merkle root mismatch in block {block['index']}"}
            expected_hash = _demo_sha256(
                f"{block['index']}{block['timestamp']}{block['previousHash']}{block['merkleRoot']}{len(block['entries'])}"
            )
            if block["hash"] != expected_hash:
                return {"valid": False, "corruptedBlock": block["index"],
                        "reason": f"Hash mismatch detected in block {block['index']}"}
        return {"valid": True, "corruptedBlock": None, "reason": ""}

    def tamper_block(self, block_index: int):
        if 0 <= block_index < len(self.ledger):
            block = self.ledger[block_index]
            if block["entries"]:
                entry = block["entries"][0]
                entry["description"] = entry["description"] + " [TAMPERED]"
                entry["amount"] = entry.get("amount", 0) * 10 if entry.get("amount") else 999

    def reset_ledger(self):
        self.ledger = init_ledger()

    def get_merkle_proof(self, block_index: int, entry_index: int) -> dict:
        if block_index < 0 or block_index >= len(self.ledger):
            return {"error": "Block not found"}
        block = self.ledger[block_index]
        entries = block["entries"]
        if entry_index < 0 or entry_index >= len(entries):
            return {"error": "Entry not found"}

        leaf = _demo_sha256(json.dumps(entries[entry_index], sort_keys=True))
        hashes = [_demo_sha256(json.dumps(e, sort_keys=True)) for e in entries]
        proof = []
        idx = entry_index
        while len(hashes) > 1:
            nxt = []
            for i in range(0, len(hashes), 2):
                if i + 1 < len(hashes):
                    if i == idx:
                        proof.append(hashes[i + 1])
                    elif i + 1 == idx:
                        proof.append(hashes[i])
                    nxt.append(_demo_sha256(hashes[i] + hashes[i + 1]))
                else:
                    nxt.append(_demo_sha256(hashes[i]))
            idx = idx // 2
            hashes = nxt

        return {
            "root": block["merkleRoot"],
            "proof": proof,
            "leafHash": leaf,
            "leafIndex": entry_index,
            "valid": True,
            "blockIndex": block_index,
            "entry": entries[entry_index],
        }

    def get_forecast(self) -> dict:
        predictions = []
        for t in range(24):
            demand = 20 + 15 * math.sin(t * 0.5) + (10 if 5 <= t <= 10 else 0)
            predictions.append({
                "time": t,
                "demand": round(demand, 1),
                "actual": round(demand + (math.sin(t * 1.3) * 5), 1) if t <= self.sim_time else None,
                "confidence": round(0.95 - t * 0.02, 2),
            })
        zones = [
            {"area": a, "wait": round(5 + i * 2.5, 1), "weight": round(1.0 - i * 0.08, 2)}
            for i, a in enumerate(["Dadar", "Hindmata", "Andheri", "Sion Circle", "Bandra"])
        ]
        return {"predictions": predictions, "zones": zones}
