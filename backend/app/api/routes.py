from fastapi import APIRouter, HTTPException, Query, Depends
from app.services.state_service import StateService
from app.config import settings
from app.security.privacy import redact_for_role
from app.security.auth import get_current_user, require_roles, PERSONAS, PERSONA_TOKENS, create_jwt_token
from app.schemas.schemas import (
    ChaosRequest, OverrideRequest, ApprovalRequest, TamperRequest
)

router = APIRouter(prefix="/api")
service = StateService.get_instance()

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "ReliefChain Backend",
        "version": "2.0.0",
        "simulationSeed": service.seed,
        "simTime": service.sim_time
    }

@router.get("/auth/personas")
def get_personas():
    return {
        "personas": [
            {
                "key": key,
                "role": p["role"],
                "username": p["username"],
                "name": p["name"],
                "token": PERSONA_TOKENS[key]
            }
            for key, p in PERSONAS.items()
        ]
    }

@router.post("/auth/token")
def mint_token(role: str = Query(...)):
    matching = next((p for p in PERSONAS.values() if p["role"].lower() == role.lower()), None)
    if not matching:
        matching = {"username": f"user_{role.lower().replace(' ', '_')}", "role": role, "name": f"{role} User"}
    return {"token": create_jwt_token(matching), "role": matching["role"]}

@router.get("/state")
def get_state(role: str = Query(None), current_user: dict = Depends(get_current_user)):
    effective_role = current_user.get("role") or role or "Control Room"
    raw_state = service.get_world_state()
    return redact_for_role(raw_state, effective_role)

@router.get("/compare")
def get_comparison():
    return {
        "reliefchain": service.stats,
        "baseline": service.baseline_world.stats if hasattr(service, "baseline_world") else None,
        "decisions": service.decisions,
        "baselineDecisions": service.baseline_world.decisions if hasattr(service, "baseline_world") else [],
    }

@router.get("/incidents")
def get_incidents():
    return service.incidents

@router.get("/hospitals")
def get_hospitals():
    return service.hospitals

@router.get("/ambulances")
def get_ambulances():
    return service.ambulances

@router.get("/decisions")
def get_decisions():
    return service.decisions

@router.get("/ledger")
def get_ledger():
    return service.ledger

@router.get("/funds")
def get_funds():
    return service.funds

@router.get("/anomalies")
def get_anomalies():
    return service.anomalies

@router.get("/forecast")
def get_forecast():
    return service.forecaster.predict_demand(
        service.sim_time, service.incidents, service.roads
    )

@router.get("/integrations")
def get_integrations():
    return settings.get_integration_statuses()

@router.post("/simulation/event")
def trigger_event(event_id: int = Query(...)):
    event = next((e for e in service.events if e["id"] == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event["triggered"] = False # allow manual force
    service.sim_time = event["time"]
    service.tick(0.0)
    return {"status": "triggered", "event": event, "state": service.get_world_state()}

@router.post("/sim/play")
def play_sim():
    if service.sim_time >= 90.0:
        service.sim_time = 0.0
        for ev in service.events:
            ev["triggered"] = False
    service.running = True
    return {"running": True, "simTime": service.sim_time}

@router.post("/sim/pause")
def pause_sim():
    service.running = False
    return {"running": False}

@router.post("/sim/step")
def step_sim(dt: float = 0.5):
    state = service.tick(dt)
    return state

@router.post("/sim/speed")
def set_speed(speed: float = Query(...)):
    service.speed = speed
    return {"speed": speed}

@router.post("/sim/restart")
def restart_sim():
    service.reset_to_seed(service.seed)
    return service.get_world_state()

@router.post("/sim/seek")
def seek_sim(time: float = Query(..., description="Sim time in sim-minutes to jump to")):
    """Time travel: jump to a specific sim time.
    Currently snaps the clock (future: restore from event log snapshot)."""
    max_time = 90.0  # 90 sim-minutes per C5 fix
    service.sim_time = max(0.0, min(max_time, float(time)))
    return service.get_world_state()

@router.post("/chaos")
def apply_chaos(req: ChaosRequest):
    return service.handle_chaos(req.action)

@router.post("/override")
def apply_override(req: OverrideRequest):
    res = service.handle_override(req.id, req.newHospitalId, req.reason, req.user)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@router.post("/approval")
def apply_approval(req: ApprovalRequest):
    res = service.handle_approval(req.id, req.user)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@router.post("/verification")
def verify_ledger():
    return service.verify_ledger()

@router.post("/tamper")
def tamper_ledger(
    req: TamperRequest,
    user: dict = Depends(require_roles(["Auditor", "Evaluator", "Control Room", "Judge"]))
):
    return service.tamper_ledger(req.blockIndex)

@router.post("/reset")
def reset_ledger(
    user: dict = Depends(require_roles(["Auditor", "Evaluator", "Control Room", "Judge"]))
):
    return service.reset_ledger()

@router.get("/proof")
def get_proof(block_index: int = 1, entry_index: int = 0):
    try:
        return service.generate_proof_for_entry(block_index, entry_index)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

from app.simulation.stress import generate_stress_scenario, CRISIS_PROFILES

@router.get("/stress/profiles")
def get_stress_profiles():
    return CRISIS_PROFILES

@router.get("/stress/scenario")
def get_stress_scenario(level: str = Query("L2"), seed: int = Query(42)):
    return generate_stress_scenario(level, seed)

@router.post("/stress/apply")
def apply_stress_scenario(level: str = Query("L2"), seed: int = Query(42)):
    data = generate_stress_scenario(level, seed)
    service.ambulances = data["ambulances"]
    service.incidents = data["incidents"]
    service.roads = data["roads"]
    service.road_network.sync_roads(service.roads)
    service.alert = f"Stress Lab: Activated {data['profile']['name']} ({level}) — {len(service.ambulances)} vehicles, {len(service.incidents)} incidents"
    return service.get_world_state()

