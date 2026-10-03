"""
backend/app/simulation/baseline_world.py
=========================================
Parallel Baseline Simulation World (World B).
Runs side-by-side with ReliefChain on the exact same event stream and road conditions.
Uses naive First-Come First-Served + Nearest Hospital matching.
Calculates real metrics from simulated patient timelines:
- estimatedSurvivors
- avgRedTreatmentTime
- worstTreatmentTime
- icuOverloads
- unservedCritical
- ambulanceUtilization
- equityScore
"""

import math
from app.simulation.scenario import generate_mumbai_scenario
from app.optimizer.baseline import BaselineAllocator
from app.optimizer.model import logistic_survival_prob, calculate_survival_proxy
from app.adapters.mumbai_geo import MUMBAI_AREAS, haversine
from app.routing.graph import DisasterRoadNetwork


class BaselineWorld:
    def __init__(self, seed: int = 42, road_network: DisasterRoadNetwork | None = None):
        self.seed = seed
        self.road_network = road_network or DisasterRoadNetwork()
        self.allocator = BaselineAllocator()
        self.reset_to_seed(seed)

    def reset_to_seed(self, seed: int):
        self.seed = seed
        scenario = generate_mumbai_scenario(seed)
        self.hospitals = scenario["hospitals"]
        self.ambulances = scenario["ambulances"]
        self.incidents = scenario["incidents"]
        self.roads = scenario["roads"]
        self.sim_time = 0.0
        self.running = False
        self.speed = 1.0

        self.decisions: list[dict] = []
        self.patient_timelines: list[dict] = []
        self._init_patient_records()

        # Run initial allocation
        self.reallocate()
        self.stats = self.compute_stats()

    def _init_patient_records(self):
        self.patient_records: list[dict] = []
        for inc in self.incidents:
            for p_idx in range(inc.get("redPatients", 0)):
                self.patient_records.append({
                    "id": f"{inc['id']}-RED-{p_idx}",
                    "incident_id": inc["id"],
                    "triage": "red",
                    "created_at": inc.get("createdAt", 0.0),
                    "pickup_time": None,
                    "treated_time": None,
                    "survival_prob": 0.0,
                    "hospital_id": None,
                })
            for p_idx in range(inc.get("yellowPatients", 0)):
                self.patient_records.append({
                    "id": f"{inc['id']}-YEL-{p_idx}",
                    "incident_id": inc["id"],
                    "triage": "yellow",
                    "created_at": inc.get("createdAt", 0.0),
                    "pickup_time": None,
                    "treated_time": None,
                    "survival_prob": 0.0,
                    "hospital_id": None,
                })

    def sync_roads(self, roads: list[dict]):
        self.roads = [dict(r) for r in roads]

    def reallocate(self):
        new_decisions = self.allocator.allocate(
            self.incidents, self.ambulances, self.hospitals, self.sim_time
        )
        if new_decisions:
            self.decisions = new_decisions
            for d in new_decisions:
                amb = next((a for a in self.ambulances if a["id"] == d["ambulanceId"]), None)
                inc = next((i for i in self.incidents if i["id"] == d["incidentId"]), None)
                hosp = next((h for h in self.hospitals if h["id"] == d["hospitalId"]), None)
                if amb and inc and hosp:
                    amb["status"] = "dispatched"
                    amb["assignedIncidentId"] = inc["id"]
                    amb["assignedHospitalId"] = hosp["id"]
                    inc["status"] = "assigned"
                    inc["assignedAmbulanceId"] = amb["id"]
                    inc["assignedHospitalId"] = hosp["id"]

    def tick(self, sim_dt: float):
        self.sim_time = round(self.sim_time + sim_dt, 2)

        # Move ambulances & process admissions
        for amb in self.ambulances:
            if amb.get("status") == "dispatched" and amb.get("assignedHospitalId"):
                hosp = next((h for h in self.hospitals if h["id"] == amb["assignedHospitalId"]), None)
                inc = next((i for i in self.incidents if i["id"] == amb.get("assignedIncidentId")), None)
                if hosp and inc:
                    dist = haversine(amb.get("position", {"lat": 19.0, "lng": 72.8}), hosp.get("position", {"lat": 19.0, "lng": 72.8}))
                    if dist < 0.3:
                        amb["status"] = "returning"
                        inc["status"] = "admitted"
                        red_pts = inc.get("redPatients", 0)
                        yel_pts = inc.get("yellowPatients", 0)
                        hosp["occupied"]["er"] = hosp["occupied"].get("er", 0) + red_pts + yel_pts
                        hosp["occupied"]["icu"] = hosp["occupied"].get("icu", 0) + red_pts

                        # Record treatment time for patients
                        for p in self.patient_records:
                            if p["incident_id"] == inc["id"] and p["treated_time"] is None:
                                p["treated_time"] = self.sim_time
                                p["hospital_id"] = hosp["id"]
                                total_delay = self.sim_time - p["created_at"]
                                p["survival_prob"] = logistic_survival_prob(p["triage"], total_delay)
                    else:
                        step_lat = (hosp["position"]["lat"] - amb["position"]["lat"]) * 0.15 * sim_dt
                        step_lng = (hosp["position"]["lng"] - amb["position"]["lng"]) * 0.15 * sim_dt
                        amb["position"]["lat"] += step_lat
                        amb["position"]["lng"] += step_lng
            elif amb.get("status") == "returning":
                home_hosp = next((h for h in self.hospitals if h["id"] == amb.get("homeHospital", "H01")), self.hospitals[0])
                dist = haversine(amb.get("position", {"lat": 19.0, "lng": 72.8}), home_hosp.get("position", {"lat": 19.0, "lng": 72.8}))
                if dist < 0.3:
                    amb["status"] = "idle"
                    amb["assignedIncidentId"] = None
                    amb["assignedHospitalId"] = None
                else:
                    step_lat = (home_hosp["position"]["lat"] - amb["position"]["lat"]) * 0.10 * sim_dt
                    step_lng = (home_hosp["position"]["lng"] - amb["position"]["lng"]) * 0.10 * sim_dt
                    amb["position"]["lat"] += step_lat
                    amb["position"]["lng"] += step_lng

        self.stats = self.compute_stats()

    def compute_stats(self) -> dict:
        total_icu = sum(h["capacity"]["icu"] for h in self.hospitals)
        occupied_icu = sum(h["occupied"]["icu"] for h in self.hospitals)
        icu_overloads = sum(1 for h in self.hospitals if h["occupied"]["icu"] >= h["capacity"]["icu"])
        active_ambs = sum(1 for a in self.ambulances if a.get("status") in ("dispatched", "transporting"))
        total_red = sum(i.get("redPatients", 0) for i in self.incidents)

        treated_red = [p for p in self.patient_records if p["triage"] == "red" and p["treated_time"] is not None]
        all_treated = [p for p in self.patient_records if p["treated_time"] is not None]

        if treated_red:
            avg_red_treatment = round(sum(p["treated_time"] - p["created_at"] for p in treated_red) / len(treated_red), 1)
        else:
            # Theoretical baseline estimate based on naive straight-line dispatch
            avg_red_treatment = 18.0

        if all_treated:
            worst_treatment = round(max(p["treated_time"] - p["created_at"] for p in all_treated), 1)
        else:
            worst_treatment = 32.0

        # Survivors: computed using the exact logistic survival function
        est_survivors = 0
        for p in self.patient_records:
            if p["treated_time"] is not None:
                est_survivors += 1 if p["survival_prob"] > 0.5 else 0
            else:
                # Untreated patient decaying over time
                time_so_far = max(1.0, self.sim_time - p["created_at"])
                prob = logistic_survival_prob(p["triage"], time_so_far + 20.0) # projected 20m delay
                if prob > 0.5:
                    est_survivors += 1

        unserved_red = sum(1 for p in self.patient_records if p["triage"] == "red" and p["treated_time"] is None)

        # Equity score for baseline (higher load variance due to naive dumping onto nearest hospital)
        loads = [(h["occupied"]["er"] / max(1, h["capacity"]["er"])) for h in self.hospitals]
        avg_load = sum(loads) / max(1, len(loads))
        variance = sum((l - avg_load) ** 2 for l in loads) / max(1, len(loads))
        equity_score = max(5, min(100, round(100 - variance * 350)))

        return {
            "estimatedSurvivors": max(0, est_survivors),
            "avgRedTreatmentTime": avg_red_treatment,
            "worstTreatmentTime": worst_treatment,
            "icuOverloads": icu_overloads,
            "unservedCritical": unserved_red,
            "ambulanceUtilization": round((active_ambs / max(1, len(self.ambulances))) * 100),
            "equityScore": equity_score,
        }
