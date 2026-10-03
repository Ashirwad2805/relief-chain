"""
ReliefChain FastAPI Backend — Full API matching frontend client.ts expectations.
Implements simulation control, ledger, WebSocket, forecasts, chat, and more.
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sim_world import SimWorld
from ai_client import ask_ai

# ── Global Simulation State ─────────────────────────────────────────────────

# Retained as the local simulation implementation alongside the upstream app.
world = SimWorld()

# ── WebSocket Manager ────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        data = json.dumps(message)
        disconnected = []
        for ws in self.active:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()

# ── Simulation Ticker ────────────────────────────────────────────────────────

_tick_task: asyncio.Task | None = None


async def _sim_loop():
    """Background loop that ticks the simulation when running."""
    while True:
        if world.running:
            dt = 0.5 * world.speed
            snapshot = world.tick(dt)
            seq = world.next_seq()
            await manager.broadcast({
                "seq": seq,
                "ts": time.time(),
                "sim_time": world.sim_time,
                "world": "A",
                "type": "tick",
                "payload": {
                    "simTime": snapshot["simTime"],
                    "running": snapshot["running"],
                    "stats": snapshot["stats"],
                    "ambulances": snapshot["ambulances"],
                    "incidents": snapshot["incidents"],
                    "hospitals": snapshot["hospitals"],
                    "roads": snapshot["roads"],
                    "alert": snapshot["alert"],
                    "decisions": snapshot["decisions"],
                },
            })
        await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _tick_task
    _tick_task = asyncio.create_task(_sim_loop())
    yield
    if _tick_task:
        _tick_task.cancel()
        try:
            await _tick_task
        except asyncio.CancelledError:
            pass


# ── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(title="ReliefChain API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Models ─────────────────────────────────────────────────────────

class ChatIn(BaseModel):
    message: str

class StepIn(BaseModel):
    dt: float = 0.5

class ApprovalIn(BaseModel):
    id: str
    user: str = "Operator"

class OverrideIn(BaseModel):
    id: str
    newHospitalId: str
    reason: str
    user: str = "Operator"

class ChaosIn(BaseModel):
    action: str

class TamperIn(BaseModel):
    blockIndex: int


# ── Health / Root ────────────────────────────────────────────────────────────

@app.get("/")
def home():
    return {"status": "ok"}


@app.get("/api/health")
def health():
    return {"status": "ok", "simTime": world.sim_time}


# ── World State ──────────────────────────────────────────────────────────────

@app.get("/api/state")
def get_state(role: str = "Control Room"):
    return world.snapshot()


# ── Simulation Controls ─────────────────────────────────────────────────────

@app.post("/api/sim/play")
def sim_play():
    world.running = True
    return {"running": True}


@app.post("/api/sim/pause")
def sim_pause():
    world.running = False
    return {"running": False}


@app.post("/api/sim/step")
def sim_step(body: StepIn = StepIn()):
    was_running = world.running
    world.running = False
    snapshot = world.tick(body.dt)
    world.running = was_running
    return snapshot


@app.post("/api/sim/speed")
def sim_speed(speed: float = Query(1.0)):
    world.speed = max(0.1, min(speed, 10.0))
    return {"speed": world.speed}


@app.post("/api/sim/restart")
def sim_restart():
    world.reset()
    return world.snapshot()


@app.post("/api/sim/seek")
def sim_seek(time_val: float = Query(0.0, alias="time")):
    world.reset()
    while world.sim_time < time_val:
        world.tick(min(0.5, time_val - world.sim_time))
    return world.snapshot()


# ── Simulation Events ───────────────────────────────────────────────────────

@app.post("/api/simulation/event")
def trigger_event(event_id: int = Query(...)):
    for ev in world.events:
        if ev["id"] == event_id and not ev["triggered"]:
            ev["triggered"] = True
            world._apply_event(ev)
            break
    return world.snapshot()


# ── Decisions ────────────────────────────────────────────────────────────────

@app.post("/api/approval")
def approve_decision(body: ApprovalIn):
    for dec in world.decisions:
        if dec["id"] == body.id:
            dec["status"] = "approved"
            return {"success": True}
    return {"success": False}


@app.post("/api/override")
def override_decision(body: OverrideIn):
    for dec in world.decisions:
        if dec["id"] == body.id:
            dec["status"] = "overridden"
            dec["overrideReason"] = body.reason
            # Re-assign to new hospital
            new_hosp = next((h for h in world.hospitals if h["id"] == body.newHospitalId), None)
            if new_hosp:
                dec["hospitalId"] = new_hosp["id"]
                dec["selectedHospitalName"] = new_hosp["name"]
                # Update incident
                for inc in world.incidents:
                    if inc["id"] == dec["incidentId"]:
                        inc["assignedHospitalId"] = new_hosp["id"]
                        break
            return {"success": True}
    return {"success": False}


# ── Chaos ────────────────────────────────────────────────────────────────────

@app.post("/api/chaos")
def chaos_action(body: ChaosIn):
    return world.apply_chaos(body.action)


# ── Ledger ───────────────────────────────────────────────────────────────────

@app.get("/api/ledger")
def get_ledger():
    return world.ledger


@app.post("/api/verification")
def verify_ledger():
    return world.verify_ledger()


@app.post("/api/tamper")
def tamper_ledger(body: TamperIn):
    world.tamper_block(body.blockIndex)
    return {"status": "tampered"}


@app.post("/api/reset")
def reset_ledger():
    world.reset_ledger()
    return {"status": "reset"}


@app.get("/api/proof")
def get_proof(block_index: int = Query(0), entry_index: int = Query(0)):
    return world.get_merkle_proof(block_index, entry_index)


# ── Forecasts / Anomalies / Funds / Integrations ────────────────────────────

@app.get("/api/forecast")
def get_forecast():
    return world.get_forecast()


@app.get("/api/anomalies")
def get_anomalies():
    return world.anomalies


@app.get("/api/funds")
def get_funds():
    return world.funds


@app.get("/api/integrations")
def get_integrations():
    return {
        "gps_fleet": {"status": "connected", "devices": 12, "lastSync": time.time()},
        "blood_bank_api": {"status": "connected", "provider": "Indian Red Cross", "lastSync": time.time() - 120},
        "weather_api": {"status": "connected", "provider": "IMD", "alerts": 3},
        "aadhaar_verify": {"status": "connected", "verifications": 456},
        "upi_payments": {"status": "connected", "transactions": 89},
    }


# ── Chat (AI) ───────────────────────────────────────────────────────────────

@app.post("/api/chat")
def chat(body: ChatIn):
    try:
        return {"reply": ask_ai(body.message)}
    except Exception as e:
        return {"reply": "AI is currently unavailable. Please try again later.", "error": str(e)}


# ── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, role: str = Query("Control Room")):
    await manager.connect(ws)
    try:
        # Send initial snapshot
        snapshot = world.snapshot()
        seq = world.next_seq()
        await ws.send_text(json.dumps({
            "seq": seq,
            "ts": time.time(),
            "sim_time": world.sim_time,
            "world": "A",
            "type": "snapshot",
            "payload": snapshot,
        }))

        # Listen for client messages
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "request_snapshot":
                seq = world.next_seq()
                await ws.send_text(json.dumps({
                    "seq": seq,
                    "ts": time.time(),
                    "sim_time": world.sim_time,
                    "world": "A",
                    "type": "snapshot",
                    "payload": world.snapshot(),
                }))

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)