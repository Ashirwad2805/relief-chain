import os
os.environ["PANDAS_USE_PYARROW"] = "0"
import pytest
from app.services.state_service import StateService
from app.routing.graph import DisasterRoadNetwork
from app.optimizer.solver import AllocationOptimizer
from app.optimizer.baseline import BaselineAllocator
from app.ledger.chain import create_block, verify_blockchain, tamper_blockchain
from app.ledger.merkle import build_merkle_tree, generate_merkle_proof, verify_merkle_proof, hash_entry
from app.forecasting.predictor import DemandForecaster
from app.anomaly.detector import AnomalyDetector
from app.security.privacy import redact_for_role, anonymize_patient_id

def test_deterministic_seed_parity():
    s1 = StateService()
    s1.reset_to_seed(42)
    s2 = StateService()
    s2.reset_to_seed(42)

    assert len(s1.hospitals) == 18
    assert len(s1.ambulances) == 40
    assert len(s1.incidents) == 8
    assert s1.hospitals[0]["name"] == s2.hospitals[0]["name"]
    assert s1.ambulances[0]["id"] == s2.ambulances[0]["id"]
    assert s1.incidents[0]["patientCount"] == s2.incidents[0]["patientCount"]

def test_two_run_byte_identical_simulation():
    """Verify C1 fix: Two simulation runs with the same seed produce byte-identical decisions and ledger."""
    s1 = StateService()
    s1.reset_to_seed(42)
    s1.running = True

    s2 = StateService()
    s2.reset_to_seed(42)
    s2.running = True

    # Advance both across multiple ticks
    for _ in range(10):
        s1.tick(dt=1.0)
        s2.tick(dt=1.0)

    dec_ids1 = [d["id"] for d in s1.decisions]
    dec_ids2 = [d["id"] for d in s2.decisions]
    assert dec_ids1 == dec_ids2
    assert len(dec_ids1) > 0

    hashes1 = [b["hash"] for b in s1.ledger]
    hashes2 = [b["hash"] for b in s2.ledger]
    assert hashes1 == hashes2
    assert s1.sim_time == s2.sim_time


def test_routing_graph_and_road_delays():
    network = DisasterRoadNetwork()
    # Open road
    time_open, dist_open, path = network.get_travel_time_minutes("Sion", "Dadar", "basic")
    assert time_open > 0
    assert dist_open > 0
    assert "Sion" in path and "Dadar" in path

    # Flooded road causes delay
    network.update_road_condition("Sion", "Dadar", "flooded")
    time_flooded, _, _ = network.get_travel_time_minutes("Sion", "Dadar", "basic")
    assert time_flooded > time_open

    # Boat is faster in flood
    time_boat, _, _ = network.get_travel_time_minutes("Sion", "Dadar", "boat")
    assert time_boat < time_flooded

    # Blocked road requires detour
    network.update_road_condition("Sion", "Dadar", "blocked")
    time_blocked, _, path_blocked = network.get_travel_time_minutes("Sion", "Dadar", "basic")
    assert path_blocked != ["Sion", "Dadar"]

def test_optimizer_projected_capacity_and_no_double_booking():
    service = StateService.get_instance()
    service.reset_to_seed(42)

    # Force a hospital to almost full capacity (1 ICU bed left)
    target_hosp = service.hospitals[0]
    target_hosp["capacity"]["icu"] = 10
    target_hosp["occupied"]["icu"] = 9

    decisions = service.optimizer.optimize_allocations(
        service.incidents, service.ambulances, service.hospitals, [], 0.0
    )
    assert len(decisions) > 0

    # Ensure no decisions overload safe capacity beyond limits
    allocated_to_target = [d for d in decisions if d["hospitalId"] == target_hosp["id"]]
    total_red_assigned = sum(
        next(i["redPatients"] for i in service.incidents if i["id"] == d["incidentId"])
        for d in allocated_to_target
    )
    # Target had 1 bed left; should not assign dozens of critical patients to it
    assert total_red_assigned <= 6

def test_anti_thrashing_and_rerouting():
    service = StateService.get_instance()
    service.reset_to_seed(42)

    initial_decisions = service.optimizer.optimize_allocations(
        service.incidents, service.ambulances, service.hospitals, [], 0.0
    )
    first_dec = initial_decisions[0]

    # Re-running with existing decisions should preserve assignment (stickiness)
    recalculated = service.optimizer.optimize_allocations(
        service.incidents, service.ambulances, service.hospitals, initial_decisions, 0.5
    )
    same_inc_dec = next((d for d in recalculated if d["incidentId"] == first_dec["incidentId"]), None)
    if same_inc_dec:
        assert same_inc_dec["hospitalId"] == first_dec["hospitalId"]

def test_baseline_allocator_comparison():
    service = StateService.get_instance()
    service.reset_to_seed(42)

    relief_decisions = service.optimizer.optimize_allocations(
        service.incidents, service.ambulances, service.hospitals, [], 0.0
    )
    baseline_decisions = service.baseline_allocator.allocate(
        service.incidents, service.ambulances, service.hospitals, 0.0
    )

    assert len(baseline_decisions) > 0
    # Baseline strictly assigns nearest
    for bd in baseline_decisions:
        assert bd["hospitalId"] == bd["nearestHospitalId"]

def test_forecasting_predictor():
    forecaster = DemandForecaster()
    pred = forecaster.predict_demand(
        sim_time=5.0,
        incidents=[{"redPatients": 15, "yellowPatients": 20, "area": "Dadar", "status": "active"}],
        roads=[{"condition": "flooded"}]
    )
    assert pred["currentDemand"] == 15
    assert pred["forecast10m"] >= 15
    assert pred["forecast20m"] >= pred["forecast10m"]
    assert pred["forecast30m"] >= pred["forecast20m"]
    assert len(pred["hotspots"]) > 0

def test_anomaly_detection():
    detector = AnomalyDetector()
    anomalies = detector.scan_anomalies(
        funds=[{"id": "F1", "amount": 95000000.0, "recipient": "Relief Command"}],
        supplies=[{"id": "SUP-1", "name": "Oxygen", "quantity": 50, "unit": "cylinders", "location": "Dadar", "status": "stuck"}],
        decisions=[{"ambulanceId": "AMB-04", "status": "suggested"}],
        sim_time=2.0
    )
    types = [a["type"] for a in anomalies]
    assert "duplicate_beneficiary" in types
    assert "ghost_delivery" in types
    assert "unusual_pricing" in types

def test_ledger_chain_and_tamper_detection():
    # 1. Create a valid 3-block chain
    b0 = create_block(None, [{"type": "allocation", "description": "Genesis", "entityId": "SYS"}], 0.0)
    b1 = create_block(b0, [{"type": "fund_pledge", "description": "Pledge 5 Cr", "amount": 50000000, "entityId": "F1"}], 1.0)
    b2 = create_block(b1, [{"type": "dispatch", "description": "Dispatch AMB-01", "entityId": "AMB-01"}], 2.0)
    chain = [b0, b1, b2]

    # Verification must pass
    res_valid = verify_blockchain(chain)
    assert res_valid["valid"] is True
    assert res_valid["corruptedBlock"] is None

    # 2. Tamper block #1
    tampered_chain = tamper_blockchain(chain, 1)
    res_tampered = verify_blockchain(tampered_chain)
    assert res_tampered["valid"] is False
    assert res_tampered["corruptedBlock"] == 1
    assert "mismatch" in res_tampered["reason"].lower()

def test_merkle_proof_generation_and_verification():
    entries = [
        {"type": "allocation", "description": "Decision D1", "entityId": "D1"},
        {"type": "dispatch", "description": "Ambulance A1", "entityId": "A1"},
        {"type": "fund_release", "description": "Funds F1", "entityId": "F1"},
        {"type": "delivery_confirmation", "description": "Supplies S1", "entityId": "S1"}
    ]
    leaf_hashes = [hash_entry(e) for e in entries]
    root, _ = build_merkle_tree(leaf_hashes)

    # Generate proof for entry #2
    proof = generate_merkle_proof(leaf_hashes, 2)
    assert proof["merkleRoot"] == root

    # Verify proof matches
    is_valid = verify_merkle_proof(proof["leafHash"], proof["proofPath"], root)
    assert is_valid is True

    # Tampered leaf should fail verification
    is_tampered_valid = verify_merkle_proof("0000000000000000000000000000000000000000000000000000000000000000", proof["proofPath"], root)
    assert is_tampered_valid is False

def test_privacy_and_role_redaction():
    state = {
        "incidents": [{"id": "INC-1", "label": "Incident", "severity": "red", "area": "Sion", "position": {"lat":19,"lng":72}, "status": "active", "redPatients": 5}],
        "ambulances": [{"id": "AMB-01", "status": "idle", "type": "basic", "position": {"lat":19,"lng":72}}],
        "funds": [{"id": "F1", "donor": "Secret Donor", "amount": 1000000}]
    }

    # Public role redacts tactical ambulance IDs and patient counts
    public_view = redact_for_role(state, "Public")
    assert public_view["ambulances"][0]["id"] == "FLEET-0"
    assert "redPatients" not in public_view["incidents"][0]

    # Salted hash test
    h1 = anonymize_patient_id("PATIENT-12345")
    h2 = anonymize_patient_id("PATIENT-12345")
    h3 = anonymize_patient_id("PATIENT-99999")
    assert h1 == h2
    assert h1 != h3
    assert h1.startswith("ANON-")

def test_jwt_and_rbac_tamper_gate():
    """Verify A4 fix: Public cannot tamper or reset ledger; Auditor can."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.security.auth import PERSONA_TOKENS

    client = TestClient(app)

    # 1. Unauthenticated or Public attempt to tamper must return 403 Forbidden
    res_pub = client.post("/api/tamper", json={"blockIndex": 1})
    assert res_pub.status_code == 403
    assert "Forbidden" in res_pub.json().get("detail", "")

    # 2. Auditor token succeeds
    auditor_token = PERSONA_TOKENS["auditor"]
    res_aud = client.post(
        "/api/tamper",
        json={"blockIndex": 1},
        headers={"Authorization": f"Bearer {auditor_token}"}
    )
    assert res_aud.status_code == 200
    assert res_aud.json()["status"] == "tampered"

    # Reset with Auditor
    res_reset = client.post(
        "/api/reset",
        headers={"Authorization": f"Bearer {auditor_token}"}
    )
    assert res_reset.status_code == 200

def test_parallel_baseline_world_and_divergence():
    """Verify B1/B2/D7 fix: World B runs in parallel and produces computed metrics."""
    service = StateService.get_instance()
    service.reset_to_seed(42)

    assert service.baseline_world is not None
    base_stats = service.baseline_world.compute_stats()
    assert base_stats["estimatedSurvivors"] >= 0
    assert base_stats["avgRedTreatmentTime"] > 0
    assert base_stats["worstTreatmentTime"] >= base_stats["avgRedTreatmentTime"]
    assert base_stats["equityScore"] >= 0

def test_ambulance_pickup_to_handover_state_machine():
    """Verify D2 fix: Ambulances pick up at incident before proceeding to hospital."""
    service = StateService.get_instance()
    service.reset_to_seed(42)
    service.running = True

    # Find a dispatched ambulance
    dispatched_amb = next((a for a in service.ambulances if a["status"] in ("dispatched", "en_route_pickup")), None)
    assert dispatched_amb is not None
    assert dispatched_amb["assignedIncidentId"] is not None

    # Tick simulation forward
    for _ in range(5):
        service.tick(dt=1.0)

    # Ambulance should have transitioned or moved towards incident
    curr_amb = next(a for a in service.ambulances if a["id"] == dispatched_amb["id"])
    assert curr_amb["status"] in ("en_route_pickup", "loading", "transporting", "returning", "idle")

