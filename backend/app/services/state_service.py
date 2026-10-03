import time
import math
import uuid
import logging
from typing import Any
from app.events.store import event_store
from app.simulation.scenario import generate_mumbai_scenario
from app.simulation.events import get_simulation_events, apply_event_mutation
from app.routing.graph import DisasterRoadNetwork
from app.optimizer.solver import AllocationOptimizer
from app.optimizer.baseline import BaselineAllocator
from app.simulation.baseline_world import BaselineWorld
from app.forecasting.predictor import DemandForecaster
from app.anomaly.detector import AnomalyDetector
from app.ledger.chain import create_block, verify_blockchain, tamper_blockchain
from app.ledger.merkle import generate_merkle_proof, verify_merkle_proof, hash_entry
from app.adapters.mumbai_geo import MUMBAI_AREAS, haversine
from app.database import SessionLocal, engine, Base
from app.models.entities import (
    HospitalModel, AmbulanceModel, IncidentModel, RoadModel,
    SupplyItemModel, SupplyRequestModel, DecisionModel, LedgerBlockModel,
    FundFlowModel, AnomalyModel, SimEventModel, AuditLogModel
)

class StateService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Create database tables
        Base.metadata.create_all(bind=engine)

        self.road_network = DisasterRoadNetwork()
        self.optimizer = AllocationOptimizer(self.road_network)
        self.baseline_allocator = BaselineAllocator()
        self.forecaster = DemandForecaster()
        self.anomaly_detector = AnomalyDetector()

        # In-memory operational cache backed by DB
        self.reset_to_seed(42)

    def reset_to_seed(self, seed: int = 42):
        self.seed = seed
        scenario = generate_mumbai_scenario(seed)
        self.hospitals = scenario["hospitals"]
        self.ambulances = scenario["ambulances"]
        self.incidents = scenario["incidents"]
        self.roads = scenario["roads"]
        self.supplies = scenario["supplies"]
        self.supply_requests = scenario["supplyRequests"]
        self.funds = scenario["funds"]
        self.events = get_simulation_events()

        self.sim_time = 0.0
        self.start_time = 0.0
        self.running = False
        self.speed = 1.0
        self.alert = None
        self.autopilot_active = False
        self.autopilot_step = 0

        # Parallel baseline world (World B)
        self.baseline_world = BaselineWorld(seed=seed, road_network=self.road_network)

        # Track patient timelines for exact treatment time metrics
        self.patient_records: list[dict] = []
        for inc in self.incidents:
            for p_idx in range(inc.get("redPatients", 0)):
                self.patient_records.append({
                    "id": f"{inc['id']}-RED-{p_idx}",
                    "incident_id": inc["id"],
                    "triage": "red",
                    "created_at": inc.get("createdAt", 0.0),
                    "treated_time": None
                })
            for p_idx in range(inc.get("yellowPatients", 0)):
                self.patient_records.append({
                    "id": f"{inc['id']}-YEL-{p_idx}",
                    "incident_id": inc["id"],
                    "triage": "yellow",
                    "created_at": inc.get("createdAt", 0.0),
                    "treated_time": None
                })

        # Synchronize road network
        self.road_network.sync_roads(self.roads)

        # Initialize Genesis and initial blocks
        self.ledger = []
        genesis = create_block(None, [{
            "type": "allocation",
            "description": "ReliefChain initialized — Mumbai Monsoon Surge Mission Control",
            "entityId": "SYSTEM"
        }], 0.0)
        self.ledger.append(genesis)

        b1 = create_block(genesis, [
            {"type": "fund_pledge", "description": "Maharashtra SDMA emergency pool ₹10 Cr allocated", "amount": 100000000.0, "entityId": "F1"},
            {"type": "fund_release", "description": "₹10 Cr disbursed to Emergency Relief Pool", "amount": 100000000.0, "entityId": "F1"}
        ], 0.2)
        self.ledger.append(b1)

        b2 = create_block(b1, [
            {"type": "supply_transfer", "description": "1,200 IV Fluids released from KEM Central Depot", "entityId": "SUP-001", "metadata": {"qty": 1200}},
            {"type": "dispatch", "description": "AMB-01 dispatched on perimeter reconnaissance", "entityId": "AMB-01"}
        ], 0.5)
        self.ledger.append(b2)

        # Run initial allocation
        self.decisions = self.optimizer.optimize_allocations(
            self.incidents, self.ambulances, self.hospitals, [], self.sim_time
        )
        self.apply_decisions_to_fleet(self.decisions)

        self.anomalies = self.anomaly_detector.scan_anomalies(self.funds, self.supplies, self.decisions, self.sim_time)
        self.stats = self.compute_stats()

        # Persist baseline snapshot to DB
        self.persist_to_db()

    def persist_to_db(self):
        """Persists current state snapshot to SQLite."""
        try:
            db = SessionLocal()
            # Clean and write hospitals
            db.query(HospitalModel).delete()
            for h in self.hospitals:
                db.add(HospitalModel(
                    id=h["id"], name=h["name"], area=h["area"], specialty=h["specialty"],
                    capacity_er=h["capacity"]["er"], capacity_icu=h["capacity"]["icu"], capacity_ward=h["capacity"]["ward"],
                    occupied_er=h["occupied"]["er"], occupied_icu=h["occupied"]["icu"], occupied_ward=h["occupied"]["ward"],
                    blood_json=h["blood"], status=h["status"], lat=h["position"]["lat"], lng=h["position"]["lng"]
                ))
            # Clean and write incidents
            db.query(IncidentModel).delete()
            for inc in self.incidents:
                db.add(IncidentModel(
                    id=inc["id"], label=inc["label"], severity=inc["severity"], area=inc["area"],
                    lat=inc["position"]["lat"], lng=inc["position"]["lng"],
                    patient_count=inc["patientCount"], red_patients=inc["redPatients"],
                    yellow_patients=inc["yellowPatients"], green_patients=inc["greenPatients"],
                    blood_needed=inc["bloodNeeded"], urgency=inc["urgency"], sla_minutes=inc["slaMinutes"],
                    created_at=inc["createdAt"], status=inc["status"], description=inc["description"],
                    assigned_ambulance_id=inc.get("assignedAmbulanceId"), assigned_hospital_id=inc.get("assignedHospitalId"),
                    eta_minutes=inc.get("etaMinutes")
                ))
            db.commit()
            db.close()
            # Also checkpoint snapshot in event_store for audit replay
            event_store.save_snapshot(
                seq=len(self.ledger),
                sim_time=self.sim_time,
                state=self.get_world_state()
            )
        except Exception as e:
            logging.getLogger("ReliefChain").error("Failed to persist state snapshot: %s", e)

    def compute_stats(self) -> dict:
        total_icu = sum(h["capacity"]["icu"] for h in self.hospitals)
        occupied_icu = sum(h["occupied"]["icu"] for h in self.hospitals)
        icu_avail = max(0, total_icu - occupied_icu)
        icu_overloads = sum(1 for h in self.hospitals if h["occupied"]["icu"] >= h["capacity"]["icu"])
        hosp_overloads = sum(1 for h in self.hospitals if h["status"] in ("overloaded", "full", "power_failure"))
        total_blood = sum(sum(h["blood"].values()) for h in self.hospitals)

        active_ambs = sum(1 for a in self.ambulances if a["status"] in ("dispatched", "transporting"))
        active_incidents = sum(1 for i in self.incidents if i["status"] in ("active", "assigned"))

        total_red = sum(i["redPatients"] for i in self.incidents)
        total_yellow = sum(i["yellowPatients"] for i in self.incidents)

        est_survivors = sum(d["explanation"]["expectedSurvivors"] for d in self.decisions) if self.decisions else round(total_red * 0.75 + total_yellow * 0.85)
        baseline_survivors = sum(d["explanation"]["baselineSurvivors"] for d in self.decisions) if self.decisions else round(total_red * 0.45 + total_yellow * 0.65)

        # Spatial Equity Score based on variance of load across Mumbai areas
        loads = [(h["occupied"]["er"] / max(1, h["capacity"]["er"])) for h in self.hospitals]
        avg_load = sum(loads) / max(1, len(loads))
        variance = sum((l - avg_load) ** 2 for l in loads) / max(1, len(loads))
        equity_score = max(10, min(100, round(100 - variance * 220)))

        # Compute dynamic treatment times from patient records or active ETAs
        treated_red = [p for p in getattr(self, "patient_records", []) if p["triage"] == "red" and p["treated_time"] is not None]
        active_decisions = [d for d in self.decisions if d.get("status") != "stale"]
        if treated_red:
            avg_red_time = round(sum(p["treated_time"] - p["created_at"] for p in treated_red) / len(treated_red), 1)
        elif active_decisions:
            etas = [d["alternatives"][0]["etaMinutes"] for d in active_decisions if d.get("alternatives")]
            avg_red_time = round(sum(etas) / max(1, len(etas)), 1)
        else:
            avg_red_time = 12.0

        all_treated = [p for p in getattr(self, "patient_records", []) if p["treated_time"] is not None]
        if all_treated:
            worst_time = round(max(p["treated_time"] - p["created_at"] for p in all_treated), 1)
        elif active_decisions:
            etas = [d["alternatives"][0]["etaMinutes"] for d in active_decisions if d.get("alternatives")]
            worst_time = round(max(etas) if etas else 22.0, 1)
        else:
            worst_time = 22.0

        return {
            "estimatedSurvivors": max(1, est_survivors),
            "baselineSurvivors": max(0, baseline_survivors),
            "avgRedTreatmentTime": avg_red_time,
            "worstTreatmentTime": worst_time,
            "icuOverloads": icu_overloads,
            "unservedCritical": max(0, total_red - len([d for d in self.decisions if d["status"] != "stale"]) * 2),
            "ambulanceUtilization": round((active_ambs / max(1, len(self.ambulances))) * 100),
            "equityScore": equity_score,
            "pendingDecisions": sum(1 for d in self.decisions if d["status"] == "suggested"),
            "activeAmbulances": active_ambs,
            "activeIncidents": active_incidents,
            "hospitalOverloads": hosp_overloads,
            "activeSupplyRequests": len(self.supply_requests),
            "bloodAvailability": total_blood,
            "icuAvailability": icu_avail
        }

    def apply_decisions_to_fleet(self, new_decisions: list[dict]):
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
                inc["etaMinutes"] = d["alternatives"][0]["etaMinutes"] if d["alternatives"] else 12.0

                # Increase hospital occupied
                hosp["occupied"]["er"] = min(hosp["capacity"]["er"], hosp["occupied"]["er"] + max(1, math.ceil(inc["redPatients"] / 4)))

    def tick(self, dt: float = 0.5) -> dict:
        """Advances simulation time, triggers events, moves ambulances, and recalculates."""
        if not self.running:
            return self.get_world_state()

        # Fix C5: 1 sim-minute = 6 real seconds at 1x (configurable via speed)
        # dt is in real seconds; converted to sim-minutes
        sim_dt = (dt / 6.0) * self.speed
        new_time = self.sim_time + sim_dt
        if new_time >= 120.0:
            new_time = 0.0
            for ev in self.events:
                ev["triggered"] = False

        self.sim_time = round(new_time, 2)

        # 1. Trigger scheduled disaster events
        events_fired = []
        for event in self.events:
            if not event["triggered"] and self.sim_time >= event["time"]:
                event["triggered"] = True
                mutation_result = apply_event_mutation(event, {
                    "hospitals": self.hospitals,
                    "ambulances": self.ambulances,
                    "incidents": self.incidents,
                    "roads": self.roads,
                    "supplies": self.supplies,
                    "funds": self.funds
                })
                self.alert = mutation_result["alert"]
                events_fired.append(event)

                # Record event in immutable ledger and event store
                event_store.append(f"DISASTER_{event['type'].upper()}", event, self.sim_time, correlation_id=f"EVT-{event['id']}")
                last_block = self.ledger[-1]
                new_block = create_block(last_block, [{
                    "type": "allocation",
                    "description": f"DISASTER EVENT: {event['title']}",
                    "entityId": f"EVT-{event['id']}",
                    "metadata": {"type": event["type"], "time": self.sim_time}
                }], self.sim_time)
                self.ledger.append(new_block)

        # 2. Update dynamic road conditions in NetworkX graph and baseline world
        self.road_network.sync_roads(self.roads)
        if hasattr(self, "baseline_world"):
            self.baseline_world.sync_roads(self.roads)
            self.baseline_world.tick(sim_dt)

        # 3. If events fired or idle ambulances can serve unassigned incidents, optimize
        unassigned = [i for i in self.incidents if i.get("status") in ("active", "assigned") and not i.get("assignedAmbulanceId")]
        idle_ambs = [a for a in self.ambulances if a.get("status") == "idle"]
        time_since_opt = self.sim_time - getattr(self, "last_optimization_time", -999.0)
        should_optimize = bool(events_fired) or (bool(unassigned) and bool(idle_ambs) and (time_since_opt >= 3.0))

        if should_optimize:
            self.last_optimization_time = self.sim_time
            new_allocations = self.optimizer.optimize_allocations(
                self.incidents, self.ambulances, self.hospitals, self.decisions, self.sim_time
            )
            if new_allocations:
                # Mark stale decisions
                for old_d in self.decisions:
                    old_d["status"] = "stale"
                self.decisions.extend(new_allocations)
                self.apply_decisions_to_fleet(new_allocations)

                last_block = self.ledger[-1]
                event_cause = events_fired[0]["title"] if events_fired else "periodic dynamic rebalance"
                self.ledger.append(create_block(last_block, [
                    {
                        "type": "allocation",
                        "description": f"RE-OPTIMIZATION: {len(new_allocations)} decisions recalculated following {event_cause}",
                        "entityId": new_allocations[0]["id"]
                    }
                ], self.sim_time))

        # 4. Advance physical ambulance coordinates through state machine (D2 fix)
        for amb in self.ambulances:
            status = amb.get("status")
            inc_id = amb.get("assignedIncidentId")
            hosp_id = amb.get("assignedHospitalId")
            inc = next((i for i in self.incidents if i["id"] == inc_id), None) if inc_id else None
            hosp = next((h for h in self.hospitals if h["id"] == hosp_id), None) if hosp_id else None

            # Phase 1: Dispatched / en route to incident pickup
            if status in ("dispatched", "en_route_pickup") and inc:
                amb["status"] = "en_route_pickup"
                dist = haversine(amb["position"], inc["position"])
                if dist < 0.25:
                    amb["status"] = "loading"
                    inc["status"] = "transporting"
                else:
                    step_lat = (inc["position"]["lat"] - amb["position"]["lat"]) * 0.15 * dt * self.speed
                    step_lng = (inc["position"]["lng"] - amb["position"]["lng"]) * 0.15 * dt * self.speed
                    amb["position"]["lat"] += step_lat
                    amb["position"]["lng"] += step_lng

            # Phase 2: Loading at incident site -> transitions to transporting
            elif status == "loading":
                amb["status"] = "transporting"

            # Phase 3: Transporting patients from incident to hospital
            elif status == "transporting" and hosp:
                dist = haversine(amb["position"], hosp["position"])
                if dist < 0.25:
                    amb["status"] = "returning"
                    if inc:
                        inc["status"] = "admitted"
                        red_pts = inc.get("redPatients", 0)
                        yel_pts = inc.get("yellowPatients", 0)
                        hosp["occupied"]["er"] = min(hosp["capacity"]["er"], hosp["occupied"]["er"] + red_pts + yel_pts)
                        hosp["occupied"]["icu"] = min(hosp["capacity"]["icu"], hosp["occupied"]["icu"] + red_pts)
                        # Consume blood units (D8 fix)
                        for b_type in inc.get("bloodNeeded", ["O+"]):
                            if b_type in hosp["blood"]:
                                hosp["blood"][b_type] = max(0, hosp["blood"][b_type] - red_pts)
                        # Mark patient records treated
                        for p in getattr(self, "patient_records", []):
                            if p["incident_id"] == inc["id"] and p["treated_time"] is None:
                                p["treated_time"] = self.sim_time
                else:
                    step_lat = (hosp["position"]["lat"] - amb["position"]["lat"]) * 0.12 * dt * self.speed
                    step_lng = (hosp["position"]["lng"] - amb["position"]["lng"]) * 0.12 * dt * self.speed
                    amb["position"]["lat"] += step_lat
                    amb["position"]["lng"] += step_lng

            # Phase 4: Returning to home station
            elif status == "returning":
                home_hosp = next((h for h in self.hospitals if h["id"] == amb.get("homeHospital", "H01")), self.hospitals[0])
                dist = haversine(amb["position"], home_hosp["position"])
                if dist < 0.25:
                    amb["status"] = "idle"
                    amb["assignedIncidentId"] = None
                    amb["assignedHospitalId"] = None
                    # Dock cleanly at hospital station
                    amb["position"] = {"lat": home_hosp["position"]["lat"] + 0.0004, "lng": home_hosp["position"]["lng"] + 0.0004}
                else:
                    step_lat = (home_hosp["position"]["lat"] - amb["position"]["lat"]) * 0.08 * dt * self.speed
                    step_lng = (home_hosp["position"]["lng"] - amb["position"]["lng"]) * 0.08 * dt * self.speed
                    amb["position"]["lat"] += step_lat
                    amb["position"]["lng"] += step_lng

        self.stats = self.compute_stats()
        return self.get_world_state()

    def handle_chaos(self, action_text: str) -> dict:
        """Parses both predefined buttons and natural operator commands."""
        normalized = action_text.lower().strip()
        alert = ""

        if "flood andheri subway" in normalized or "andheri subway" in normalized:
            for r in self.roads:
                if r.get("from") == "Andheri" or r.get("to") == "Andheri":
                    r["condition"] = "flooded"
            alert = "Andheri Subway Flooded (4ft water) — Routes rerouted to Western Express Highway"

        elif "block bridge" in normalized or "sion-dadar" in normalized:
            for r in self.roads:
                if (r.get("from") == "Sion" and r.get("to") == "Dadar") or (r.get("from") == "Dadar" and r.get("to") == "Sion"):
                    r["condition"] = "blocked"
            alert = "Sion-Dadar Flyover Closed — Detour activated via Parel artery"

        elif "power" in normalized or "blackout" in normalized:
            cooper = next((h for h in self.hospitals if "Cooper" in h.get("name", "")), self.hospitals[3])
            cooper["status"] = "power_failure"
            alert = f"{cooper['name']} Grid Power Failure — Diverting all incoming critical ambulances"

        elif "kill" in normalized and "ambulance" in normalized:
            # E.g. "Kill 5 Ambulances" or "kill ambulance 12"
            killed = 0
            for a in self.ambulances:
                if a["status"] == "idle" and killed < 5:
                    a["status"] = "broken"
                    killed += 1
            alert = f"{killed} Ambulances taken offline — Fleet reserves contracted"

        elif "surge x2" in normalized or "surge" in normalized:
            for inc in self.incidents:
                inc["redPatients"] = int(inc["redPatients"] * 2)
                inc["yellowPatients"] = int(inc["yellowPatients"] * 2)
                inc["patientCount"] = inc["redPatients"] + inc["yellowPatients"] + inc["greenPatients"]
            alert = "Casualty Surge 2x — All casualty clusters doubled in severity"

        elif "blood" in normalized or "o-negative" in normalized:
            for h in self.hospitals:
                h["blood"]["O-"] = max(0, h["blood"].get("O-", 10) - 10)
            alert = "Critical O-Negative Blood Deficit — Transfusion constraints active"

        elif "close" in normalized:
            target = normalized.replace("close", "").strip().title()
            for r in self.roads:
                if target in r.get("from", "") or target in r.get("to", ""):
                    r["condition"] = "blocked"
            alert = f"{target} closed by emergency command — Routes recalculating"

        elif "reopen" in normalized or "reopening" in normalized:
            for r in self.roads:
                if r.get("condition") != "open":
                    r["condition"] = "open"
                    break
            alert = "Corridor cleared and reopened for high-speed transit"

        else:
            alert = f"Chaos event applied: {action_text}"

        self.alert = alert
        self.road_network.sync_roads(self.roads)

        # Trigger re-optimization
        new_allocations = self.optimizer.optimize_allocations(
            self.incidents, self.ambulances, self.hospitals, self.decisions, self.sim_time
        )
        if new_allocations:
            for old_d in self.decisions:
                old_d["status"] = "stale"
            self.decisions.extend(new_allocations)
            self.apply_decisions_to_fleet(new_allocations)

        # Record in ledger
        last_block = self.ledger[-1]
        self.ledger.append(create_block(last_block, [{
            "type": "allocation",
            "description": f"CHAOS CONSOLE: {action_text}",
            "entityId": "CHAOS_OVERRIDE"
        }], self.sim_time))

        self.stats = self.compute_stats()
        return self.get_world_state()

    def handle_override(self, decision_id: str, new_hospital_id: str, reason: str, user: str = "Operator") -> dict:
        dec = next((d for d in self.decisions if d["id"] == decision_id), None)
        if not dec:
            return {"success": False, "error": "Decision not found"}

        old_hosp = dec["selectedHospitalName"]
        new_hosp = next((h for h in self.hospitals if h["id"] == new_hospital_id), None)
        if not new_hosp:
            return {"success": False, "error": "Target hospital not found"}

        dec["status"] = "overridden"
        dec["overrideReason"] = reason
        dec["hospitalId"] = new_hosp["id"]
        dec["selectedHospitalName"] = new_hosp["name"]

        # Ledger recording
        last_block = self.ledger[-1]
        self.ledger.append(create_block(last_block, [{
            "type": "override",
            "description": f"HUMAN OVERRIDE by {user}: Decision {decision_id} redirected from {old_hosp} → {new_hosp['name']}. Reason: {reason}",
            "entityId": decision_id,
            "metadata": {"user": user, "previous": old_hosp, "new": new_hosp["name"], "reason": reason}
        }], self.sim_time))

        self.alert = f"Decision {decision_id} overridden by {user}: Redirected to {new_hosp['name']}"
        self.stats = self.compute_stats()
        return {"success": True, "decision": dec}

    def handle_approval(self, decision_id: str, user: str = "Operator") -> dict:
        dec = next((d for d in self.decisions if d["id"] == decision_id), None)
        if not dec:
            return {"success": False, "error": "Decision not found"}

        dec["status"] = "approved"
        last_block = self.ledger[-1]
        self.ledger.append(create_block(last_block, [{
            "type": "allocation",
            "description": f"APPROVED by {user}: {dec['action']}",
            "entityId": decision_id
        }], self.sim_time))

        self.alert = f"Decision {decision_id} approved by {user}"
        self.stats = self.compute_stats()
        return {"success": True, "decision": dec}

    def verify_ledger(self) -> dict:
        return verify_blockchain(self.ledger)

    def tamper_ledger(self, block_index: int) -> dict:
        self.ledger = tamper_blockchain(self.ledger, block_index)
        self.alert = f"ADVERSARIAL TAMPERING INJECTED at Block #{block_index} — Run Verify to detect corruption"
        return {"status": "tampered", "blockIndex": block_index}

    def reset_ledger(self) -> dict:
        self.reset_to_seed(self.seed)
        self.alert = "Ledger reset to verified state"
        return {"status": "reset", "valid": True}

    def generate_proof_for_entry(self, block_index: int, entry_index: int) -> dict:
        if block_index < 0 or block_index >= len(self.ledger):
            raise ValueError("Invalid block index")
        block = self.ledger[block_index]
        entries = block.get("entries", [])
        if entry_index < 0 or entry_index >= len(entries):
            raise ValueError("Invalid entry index")

        leaf_hashes = [hash_entry(e) for e in entries]
        proof = generate_merkle_proof(leaf_hashes, entry_index)
        proof["blockIndex"] = block_index
        proof["entry"] = entries[entry_index]
        return proof

    def get_world_state(self) -> dict:
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
            "stats": self.stats,
            "alert": self.alert,
            "autopilotActive": self.autopilot_active,
            "autopilotStep": self.autopilot_step,
            "baselineStats": self.baseline_world.stats if hasattr(self, "baseline_world") else None,
            "baselineDecisions": self.baseline_world.decisions if hasattr(self, "baseline_world") else []
        }
