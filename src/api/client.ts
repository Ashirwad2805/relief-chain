/**
 * ReliefChain Typed API Client (Phase 1 — A1 fix)
 *
 * All simulation state comes from the FastAPI backend.
 * This module is the ONLY place that makes fetch() or WebSocket calls.
 * The frontend has zero simulation logic of its own.
 */

export const BASE_URL = (
  (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000'
).replace(/\/+$/, '');
const WS_URL = BASE_URL.replace(/^http/, 'ws');

// ─── REST helpers ─────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('rc_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${options.method ?? 'GET'} ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── Health / State ───────────────────────────────────────────────────────────

export const api = {
  chat: (message: string) =>
    apiFetch<{ reply: string }>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
  health: () => apiFetch<{ status: string; simTime: number }>('/api/health'),
  state: (role = 'Control Room') =>
    apiFetch<WorldStateDTO>(`/api/state?role=${encodeURIComponent(role)}`),

  // Sim controls
  play: () => apiFetch<{ running: boolean }>('/api/sim/play', { method: 'POST' }),
  pause: () => apiFetch<{ running: boolean }>('/api/sim/pause', { method: 'POST' }),
  step: (dt = 0.5) =>
    apiFetch<WorldStateDTO>('/api/sim/step', {
      method: 'POST',
      body: JSON.stringify({ dt }),
    }),
  setSpeed: (speed: number) =>
    apiFetch<{ speed: number }>(`/api/sim/speed?speed=${speed}`, { method: 'POST' }),
  restart: () => apiFetch<WorldStateDTO>('/api/sim/restart', { method: 'POST' }),
  seek: (time: number) =>
    apiFetch<WorldStateDTO>(`/api/sim/seek?time=${time}`, { method: 'POST' }),

  // Simulation events
  triggerEvent: (eventId: number) =>
    apiFetch<WorldStateDTO>(`/api/simulation/event?event_id=${eventId}`, { method: 'POST' }),

  // Decisions
  approveDecision: (id: string, user = 'Operator') =>
    apiFetch<{ success: boolean }>('/api/approval', {
      method: 'POST',
      body: JSON.stringify({ id, user }),
    }),
  overrideDecision: (id: string, newHospitalId: string, reason: string, user = 'Operator') =>
    apiFetch<{ success: boolean }>('/api/override', {
      method: 'POST',
      body: JSON.stringify({ id, newHospitalId, reason, user }),
    }),

  // Chaos
  chaos: (action: string) =>
    apiFetch<WorldStateDTO>('/api/chaos', {
      method: 'POST',
      body: JSON.stringify({ action }),
    }),

  // Ledger
  getLedger: () => apiFetch<LedgerBlockDTO[]>('/api/ledger'),
  verifyLedger: () =>
    apiFetch<{ valid: boolean; corruptedBlock: number | null; reason: string }>(
      '/api/verification',
      { method: 'POST' }
    ),
  tamperLedger: (blockIndex: number) =>
    apiFetch<{ status: string }>('/api/tamper', {
      method: 'POST',
      body: JSON.stringify({ blockIndex }),
    }),
  resetLedger: () =>
    apiFetch<{ status: string }>('/api/reset', { method: 'POST' }),
  getProof: (blockIndex: number, entryIndex: number) =>
    apiFetch<MerkleProofDTO>(`/api/proof?block_index=${blockIndex}&entry_index=${entryIndex}`),

  // Forecasts and anomalies
  getForecast: () => apiFetch<ForecastDTO>('/api/forecast'),
  getAnomalies: () => apiFetch<AnomalyDTO[]>('/api/anomalies'),
  getFunds: () => apiFetch<FundFlowDTO[]>('/api/funds'),
  getIntegrations: () => apiFetch<Record<string, unknown>>('/api/integrations'),
};

// ─── WebSocket client ─────────────────────────────────────────────────────────

export type WSEnvelope = {
  seq: number;
  ts: number;
  sim_time: number;
  world: 'A' | 'B';
  type:
    | 'delta'
    | 'snapshot'
    | 'event_fired'
    | 'decision'
    | 'alert'
    | 'tick'
    | 'keyframe_batch';
  correlation_id?: string;
  payload: unknown;
};

export type WSHandler = (env: WSEnvelope) => void;
export type ConnectionStatus = 'connected' | 'disconnected' | 'reconnecting' | 'replay';

export interface WSClient {
  status: ConnectionStatus;
  lastSeq: number;
  send(msg: object): void;
  close(): void;
  onStatusChange: (cb: (s: ConnectionStatus) => void) => void;
  onMessage: (cb: WSHandler) => void;
}

/** Creates and manages a WebSocket connection with auto-reconnect and seq-gap detection. */
export function createWSClient(role = 'Control Room'): WSClient {
  let ws: WebSocket | null = null;
  let lastSeq = -1;
  let status: ConnectionStatus = 'disconnected';
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectDelay = 1000;
  const statusHandlers: Array<(s: ConnectionStatus) => void> = [];
  const messageHandlers: Array<WSHandler> = [];

  function setStatus(s: ConnectionStatus) {
    status = s;
    statusHandlers.forEach(h => h(s));
  }

  function connect() {
    if (ws && ws.readyState < WebSocket.CLOSING) return;
    setStatus('reconnecting');

    try {
      ws = new WebSocket(`${WS_URL}/ws?role=${encodeURIComponent(role)}`);
    } catch {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      setStatus('connected');
      reconnectDelay = 1000; // reset backoff on success
    };

    ws.onmessage = (evt) => {
      let env: WSEnvelope;
      try {
        env = JSON.parse(evt.data as string) as WSEnvelope;
      } catch {
        return;
      }

      // Seq-gap detection: if we missed messages, request a full snapshot
      if (lastSeq >= 0 && env.seq > lastSeq + 1) {
        console.warn(`[WS] seq gap: expected ${lastSeq + 1}, got ${env.seq} — requesting snapshot`);
        send({ type: 'request_snapshot' });
      }
      lastSeq = env.seq;
      messageHandlers.forEach(h => h(env));
    };

    ws.onerror = () => {
      // onclose will handle reconnect
    };

    ws.onclose = () => {
      ws = null;
      setStatus('disconnected');
      scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 1.5, 30_000);
      connect();
    }, reconnectDelay);
  }

  function send(msg: object) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }
  }

  function close() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    ws?.close();
    ws = null;
    setStatus('disconnected');
  }

  // Start connection
  connect();

  return {
    get status() { return status; },
    get lastSeq() { return lastSeq; },
    send,
    close,
    onStatusChange: (cb) => { statusHandlers.push(cb); },
    onMessage: (cb) => { messageHandlers.push(cb); },
  };
}

// ─── DTO types (mirror backend schemas) ──────────────────────────────────────

export interface GeoPointDTO { lat: number; lng: number; }

export interface HospitalDTO {
  id: string;
  name: string;
  area: string;
  specialty: string[];
  capacity: { er: number; icu: number; ward: number };
  occupied: { er: number; icu: number; ward: number };
  blood: Record<string, number>;
  status: 'operational' | 'full' | 'overloaded' | 'power_failure';
  position: GeoPointDTO;
}

export interface AmbulanceDTO {
  id: string;
  type: 'basic' | 'advanced' | 'icu' | 'boat';
  status: 'idle' | 'dispatched' | 'returning' | 'broken' | 'en_route_pickup' | 'loading' | 'transporting' | 'handover';
  position: GeoPointDTO;
  assignedIncidentId: string | null;
  assignedHospitalId: string | null;
  fuel: number;
  homeHospital: string;
  capability: number;
  routePolyline?: Array<[number, number]>;
  tArrive?: number;
}

export interface IncidentDTO {
  id: string;
  label: string;
  severity: 'red' | 'yellow' | 'green' | 'black';
  area: string;
  position: GeoPointDTO;
  patientCount: number;
  redPatients: number;
  yellowPatients: number;
  greenPatients: number;
  blackPatients?: number;
  bloodNeeded: string[];
  urgency: number;
  slaMinutes: number;
  createdAt: number;
  status: 'active' | 'assigned' | 'admitted' | 'resolved';
  description: string;
  assignedAmbulanceId: string | null;
  assignedHospitalId: string | null;
  etaMinutes: number | null;
}

export interface RoadDTO {
  id: string;
  from: string;
  to: string;
  condition: 'open' | 'flooded' | 'blocked' | 'slow';
  fromPos: GeoPointDTO;
  toPos: GeoPointDTO;
}

export interface DecisionDTO {
  id: string;
  incidentId: string;
  ambulanceId: string;
  hospitalId: string;
  selectedHospitalName: string;
  action: string;
  priority: number;
  status: 'suggested' | 'approved' | 'overridden' | 'stale' | 'superseded';
  engine: 'reliefchain' | 'baseline' | 'greedy_fallback';
  pinned?: boolean;
  overrideReason?: string;
  explanation: {
    score: number;
    expectedSurvivors: number;
    baselineSurvivors?: number;
    reasoning: string;
    alternatives: Array<{
      hospitalId: string; hospitalName: string; etaMinutes: number;
      icuAvail: number; score: number; routePolyline?: Array<[number, number]>;
    }>;
    constraints: string[];
    solverStatus?: string;
    solverTimeMs?: number;
  };
  alternatives: Array<{ etaMinutes: number; hospitalName: string }>;
  snapshotHash?: string;
}

export interface LedgerEntryDTO {
  type: string;
  description: string;
  entityId: string;
  amount?: number;
  metadata?: Record<string, unknown>;
}

export interface LedgerBlockDTO {
  index: number;
  timestamp: number;
  simTime: number;
  entries: LedgerEntryDTO[];
  merkleRoot: string;
  previousHash: string;
  hash: string;
}

export interface MerkleProofDTO {
  root: string;
  proof: string[];
  leafHash: string;
  leafIndex: number;
  valid: boolean;
  blockIndex: number;
  entry: LedgerEntryDTO;
}

export interface ForecastDTO {
  predictions: Array<{ time: number; demand: number; actual?: number; confidence?: number }>;
  zones: Array<{ area: string; wait: number; weight: number }>;
}

export interface AnomalyDTO {
  id: string;
  type: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'investigating' | 'resolved' | 'false_positive';
  entityId: string;
  detectedAt: number;
  notes?: string;
}

export interface FundFlowDTO {
  id: string;
  donor: string;
  amount: number;
  purpose: string;
  stage: 'pledged' | 'released' | 'disbursed' | 'audited';
  recipient: string;
  timestamp: number;
}

export interface SimEventDTO {
  id: number;
  time: number;
  title: string;
  description: string;
  type: string;
  triggered: boolean;
}

export interface SimStatsDTO {
  estimatedSurvivors: number;
  baselineSurvivors: number;
  avgRedTreatmentTime: number;
  worstTreatmentTime: number;
  icuOverloads: number;
  unservedCritical: number;
  ambulanceUtilization: number;
  equityScore: number;
  pendingDecisions: number;
  activeAmbulances: number;
  activeIncidents: number;
  hospitalOverloads: number;
  activeSupplyRequests: number;
  bloodAvailability: number;
  icuAvailability: number;
}

export interface WorldStateDTO {
  simTime: number;
  startTime: number;
  running: boolean;
  speed: number;
  hospitals: HospitalDTO[];
  ambulances: AmbulanceDTO[];
  incidents: IncidentDTO[];
  roads: RoadDTO[];
  supplies: SupplyItemDTO[];
  supplyRequests: SupplyRequestDTO[];
  decisions: DecisionDTO[];
  events: SimEventDTO[];
  ledger: LedgerBlockDTO[];
  funds: FundFlowDTO[];
  anomalies: AnomalyDTO[];
  stats: SimStatsDTO;
  baselineStats?: SimStatsDTO;
  baselineDecisions?: DecisionDTO[];
  alert: string | null;
  autopilotActive: boolean;
  autopilotStep: number;
}

export interface SupplyItemDTO {
  id: string; name: string; type: string; quantity: number; unit: string;
  location: string; status: 'available' | 'stuck' | 'depleted';
}

export interface SupplyRequestDTO {
  id: string; item: string; quantity: number; unit: string;
  requester: string; area: string; priority: 'urgent' | 'high' | 'normal';
  status: 'pending' | 'approved' | 'fulfilled';
  createdAt: number;
}
