"""
ReliefChain WebSocket Server (Phase 1 — A1 fix)

Sends seq-numbered envelopes:
  { seq, ts, sim_time, world, type, correlation_id, payload }

- Vehicle positions as keyframe batches (2-5 Hz) — client interpolates at 60fps
- Full snapshot on connect and on seq-gap request
- Delta updates for events, decisions, alerts
- Backpressure: drop intermediate keyframes (never drop events/decisions)
"""
import asyncio
import json
import time
import itertools
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.state_service import StateService

ws_router = APIRouter()
service = StateService.get_instance()

_seq_counter = itertools.count(0)


def next_seq() -> int:
    return next(_seq_counter)


def make_envelope(
    msg_type: str,
    payload: object,
    *,
    world: str = "A",
    correlation_id: str | None = None,
) -> str:
    return json.dumps({
        "seq": next_seq(),
        "ts": time.time(),
        "sim_time": service.sim_time,
        "world": world,
        "type": msg_type,
        "correlation_id": correlation_id,
        "payload": payload,
    }, default=str)


class ConnectionManager:
    """Manages active WebSocket connections with per-client role and backpressure."""

    def __init__(self):
        # Map ws → {"role": str, "queue_depth": int}
        self._clients: dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, role: str = "Control Room"):
        await websocket.accept()
        self._clients[websocket] = {"role": role, "queue_depth": 0}

    def disconnect(self, websocket: WebSocket):
        self._clients.pop(websocket, None)

    @property
    def active(self) -> list[WebSocket]:
        return list(self._clients.keys())

    async def send_snapshot(self, websocket: WebSocket):
        """Send a full state snapshot to one client."""
        payload = service.get_world_state()
        msg = make_envelope("snapshot", payload)
        try:
            await websocket.send_text(msg)
        except Exception:
            self.disconnect(websocket)

    async def broadcast_delta(self, delta: dict):
        """Broadcast a small delta to all clients (events, decisions, alerts)."""
        msg = make_envelope("delta", delta)
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                self.disconnect(ws)

    async def broadcast_keyframes(self):
        """Broadcast ambulance keyframes (position + route) at 2-5 Hz.
        Drops this batch if a client is lagging (backpressure).
        Never drops events or decisions.
        """
        frames = [
            {
                "id": a["id"],
                "pos": [a["position"]["lat"], a["position"]["lng"]],
                "status": a["status"],
                "heading": 0,   # TODO: compute from route vector
                "tArrive": a.get("etaMinutes"),
            }
            for a in service.ambulances
        ]
        msg = make_envelope("keyframe_batch", frames)
        for ws in self.active:
            meta = self._clients.get(ws, {})
            if meta.get("queue_depth", 0) > 3:
                # Client is lagging — skip keyframe, not events
                continue
            try:
                meta["queue_depth"] = meta.get("queue_depth", 0) + 1
                await ws.send_text(msg)
                meta["queue_depth"] = max(0, meta["queue_depth"] - 1)
            except Exception:
                self.disconnect(ws)

    async def broadcast_alert(self, message: str):
        msg = make_envelope("alert", {"message": message})
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                self.disconnect(ws)


manager = ConnectionManager()

# Tick interval in real seconds (250 ms per design spec)
TICK_INTERVAL = 0.25

# Keyframe broadcast every 400 ms (2.5 Hz)
KEYFRAME_INTERVAL = 0.4


@ws_router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    role: str = Query("Control Room"),
):
    await manager.connect(websocket, role)

    # Send full snapshot on connect so the client has something to show immediately
    await manager.send_snapshot(websocket)

    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                payload = json.loads(data_text)
            except json.JSONDecodeError:
                continue

            action_type = payload.get("type", "")

            if action_type == "request_snapshot":
                # Client detected a seq gap — resend full snapshot
                await manager.send_snapshot(websocket)

            elif action_type == "PLAY":
                service.running = True

            elif action_type == "PAUSE":
                service.running = False

            elif action_type == "SET_SPEED":
                service.speed = float(payload.get("speed", 1.0))

            elif action_type == "STEP":
                state = service.tick(float(payload.get("dt", 0.5)))
                msg = make_envelope("snapshot", state, correlation_id=payload.get("correlation_id"))
                await websocket.send_text(msg)

            elif action_type == "CHAOS":
                state = service.handle_chaos(payload.get("action", ""))
                msg = make_envelope("snapshot", state, correlation_id=payload.get("correlation_id"))
                await websocket.send_text(msg)

            elif action_type == "TRIGGER_EVENT":
                event_id = payload.get("eventId")
                event = next((e for e in service.events if e["id"] == event_id), None)
                if event:
                    event["triggered"] = False
                    service.sim_time = event["time"]
                    state = service.tick(0.0)
                    msg = make_envelope("snapshot", state, correlation_id=payload.get("correlation_id"))
                    await websocket.send_text(msg)

            elif action_type == "APPROVE_DECISION":
                service.handle_approval(payload.get("id"), payload.get("user", role))
                await manager.send_snapshot(websocket)

            elif action_type == "OVERRIDE_DECISION":
                service.handle_override(
                    payload.get("id"),
                    payload.get("newHospitalId"),
                    payload.get("reason", "Operator discretion"),
                    payload.get("user", role),
                )
                await manager.send_snapshot(websocket)

            elif action_type == "TAMPER":
                service.tamper_ledger(payload.get("blockIndex", 1))
                await manager.send_snapshot(websocket)

            elif action_type == "VERIFY_LEDGER":
                result = service.verify_ledger()
                msg = make_envelope("delta", {"_ledgerVerify": result})
                await websocket.send_text(msg)

            elif action_type == "RESET_LEDGER":
                service.reset_ledger()
                await manager.send_snapshot(websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


async def simulation_background_loop():
    """Background task: advances the simulation clock and broadcasts updates.

    Design:
    - Ticks at 250 ms real (C5 fix: 1 sim-minute = 6 real seconds at 1x)
    - Keyframe broadcast every 400 ms (client interpolates between frames at 60fps)
    - Full snapshot broadcast every 2 s to keep clients in sync
    - Only ticks when service.running = True
    """
    last_keyframe = time.time()
    last_snapshot = time.time()

    while True:
        await asyncio.sleep(TICK_INTERVAL)
        now = time.time()

        if service.running and manager.active:
            try:
                prev_alert = service.alert
                service.tick(TICK_INTERVAL)

                # Broadcast alert if it changed
                if service.alert and service.alert != prev_alert:
                    await manager.broadcast_alert(service.alert)
            except Exception as e:
                import logging
                logging.exception("Error in simulation tick: %s", e)

        # Keyframe broadcast (vehicle positions) — even when paused, so panned map stays fresh
        if now - last_keyframe >= KEYFRAME_INTERVAL and manager.active:
            await manager.broadcast_keyframes()
            last_keyframe = now

        # Full snapshot sync every 2 s (cheap safety net for any missed delta)
        if now - last_snapshot >= 2.0 and manager.active and service.running:
            delta = {
                "simTime": service.sim_time,
                "running": service.running,
                "speed": service.speed,
                "stats": service.stats,
                "incidents": service.incidents,
                "hospitals": service.hospitals,
                "ambulances": service.ambulances,
                "roads": service.roads,
                "decisions": service.decisions,
            }
            await manager.broadcast_delta(delta)
            last_snapshot = now
