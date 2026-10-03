import uuid
import hashlib
from app.adapters.mumbai_geo import MUMBAI_AREAS, haversine

class BaselineAllocator:
    """
    Standard naive allocator: Nearest Hospital + First-Come First-Served (FCFS).
    Does NOT check projected ICU double-booking, blood stock, or specialized capabilities.
    """
    def __init__(self):
        pass

    def allocate(
        self,
        incidents: list[dict],
        ambulances: list[dict],
        hospitals: list[dict],
        sim_time: float = 0.0
    ) -> list[dict]:
        active_incidents = sorted(
            [i for i in incidents if i.get("status") in ("active", "assigned")],
            key=lambda x: x.get("createdAt", 0.0)
        )
        avail_ambulances = [a for a in ambulances if a.get("status") in ("idle", "dispatched", "transporting")]

        decisions = []
        occupied_hospitals = {h["id"]: dict(h.get("occupied", {})) for h in hospitals}

        amb_idx = 0
        for inc in active_incidents:
            if amb_idx >= len(avail_ambulances):
                break
            amb = avail_ambulances[amb_idx]
            amb_idx += 1

            inc_pos = inc.get("position", MUMBAI_AREAS.get(inc.get("area", "Sion"), {"lat":19.0,"lng":72.8}))

            # Sort hospitals strictly by straight-line distance
            nearest_hosp = min(
                hospitals,
                key=lambda h: haversine(inc_pos, h.get("position", {"lat":19.0,"lng":72.8}))
            )

            dist_km = haversine(inc_pos, nearest_hosp.get("position", {"lat":19.0,"lng":72.8}))
            naive_eta = round((dist_km / 30.0) * 60 + 5.0, 1)

            red_pts = inc.get("redPatients", 0)
            yellow_pts = inc.get("yellowPatients", 0)

            # Baseline naive survivors: significantly lower due to unmanaged capacity bottlenecks
            est_survivors = max(0, round(red_pts * 0.45 + yellow_pts * 0.65))

            tick_num = int(round(sim_time * 10))
            sig = f"{sim_time:.2f}:{inc['id']}:{amb['id']}:{nearest_hosp['id']}"
            hash_hex = hashlib.sha256(sig.encode()).hexdigest()[:6].upper()
            decisions.append({
                "id": f"BASE-{tick_num}-{hash_hex}",
                "timestamp": sim_time,
                "incidentId": inc["id"],
                "incidentLabel": inc.get("label", inc["id"]),
                "ambulanceId": amb["id"],
                "hospitalId": nearest_hosp["id"],
                "selectedHospitalName": nearest_hosp["name"],
                "nearestHospitalId": nearest_hosp["id"],
                "nearestHospitalName": nearest_hosp["name"],
                "action": f"Baseline dispatch {amb['id']} to nearest {nearest_hosp['name']}",
                "score": round(max(10.0, 100.0 - dist_km * 5), 1),
                "alternatives": [
                    {
                        "hospitalId": nearest_hosp["id"],
                        "hospitalName": nearest_hosp["name"],
                        "score": 80.0,
                        "distance": dist_km,
                        "etaMinutes": naive_eta,
                        "accepted": True,
                        "reasons": ["Nearest facility (FCFS baseline)"]
                    }
                ],
                "constraints": ["Distance Only", "No Projected Capacity Check"],
                "explanation": {
                    "selectedReasons": ["Selected strictly because it is geographically closest"],
                    "nearestRejectedReasons": ["N/A (Nearest chosen)"],
                    "expectedSurvivors": est_survivors,
                    "baselineSurvivors": est_survivors
                },
                "status": "suggested",
                "pinned": False,
                "engine": "baseline"
            })

        return decisions
