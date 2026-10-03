/**
 * ReliefChain Live Store (Phase 1 — A1, A2, C1-C5 fix)
 *
 * - Backend is the single source of truth.
 * - This store holds the LAST state received from the backend.
 * - The client has NO simulation logic; it only renders what the server sends.
 * - When disconnected, it shows the last received state with a "Replay" banner.
 * - Time travel = request snapshot at time T from the backend.
 */
import {
  createContext, useContext, useReducer, useCallback,
  useEffect, useRef, useMemo, type ReactNode,
} from 'react';
import type {
  Hospital, Ambulance, Incident, Road, SupplyItem, SupplyRequest,
  AllocationDecision, SimEvent, LedgerBlock, FundFlow, Anomaly, SimStats,
  Action, Role, LedgerEntry
} from '@/types';
import {
  api, createWSClient,
  type WorldStateDTO, type WSEnvelope, type ConnectionStatus,
  type DecisionDTO, type LedgerBlockDTO, type LedgerEntryDTO,
} from './client';
import fallbackReplayState from '@/data/replay_state.json';

// ─── Types ────────────────────────────────────────────────────────────────────

export type { Role };

export interface LiveState {
  world: WorldStateDTO | null;
  /** Null until a verify call completes. */
  ledgerVerification: {
    valid: boolean;
    corruptedBlock: number | null;
    reason: string;
  } | null;
  connectionStatus: ConnectionStatus;
  role: Role;
  theme: 'dark' | 'light';
  pendingAction: string | null;
  error: string | null;
  localAlert: string | null;
}

export type LiveAction =
  | { type: 'SET_STATE'; world: WorldStateDTO }
  | { type: 'APPLY_DELTA'; delta: Partial<WorldStateDTO> }
  | { type: 'SET_CONNECTION'; status: ConnectionStatus }
  | { type: 'SET_ROLE'; role: Role }
  | { type: 'SET_THEME'; theme: 'dark' | 'light' }
  | { type: 'SET_LEDGER_VERIFY'; result: LiveState['ledgerVerification'] }
  | { type: 'SET_PENDING'; action: string | null }
  | { type: 'SET_ERROR'; error: string | null }
  | { type: 'SET_LOCAL_ALERT'; alert: string | null }
  | { type: 'UPDATE_KEYFRAMES'; frames: Array<{ id: string; pos: [number, number]; status?: string }> };

const initialWorldFallback = fallbackReplayState as unknown as WorldStateDTO;

function initialState(): LiveState {
  const savedTheme = localStorage.getItem('rc_theme') as 'dark' | 'light' | null;
  const preferDark = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)').matches : true;
  return {
    world: initialWorldFallback,
    ledgerVerification: null,
    connectionStatus: 'replay',
    role: 'Control Room',
    theme: savedTheme ?? (preferDark ? 'dark' : 'light'),
    pendingAction: null,
    error: null,
    localAlert: null,
  };
}

function reducer(state: LiveState, action: LiveAction): LiveState {
  switch (action.type) {
    case 'SET_STATE':
      return { ...state, world: action.world, error: null };

    case 'APPLY_DELTA':
      if (!state.world) return { ...state, world: action.delta as WorldStateDTO, error: null };
      return { ...state, world: { ...state.world, ...action.delta }, error: null };

    case 'SET_CONNECTION':
      return { ...state, connectionStatus: action.status };

    case 'SET_ROLE':
      return { ...state, role: action.role };

    case 'SET_THEME':
      localStorage.setItem('rc_theme', action.theme);
      return { ...state, theme: action.theme };

    case 'SET_LEDGER_VERIFY':
      return { ...state, ledgerVerification: action.result };

    case 'SET_PENDING':
      return { ...state, pendingAction: action.action };

    case 'SET_ERROR':
      return { ...state, error: action.error };

    case 'SET_LOCAL_ALERT':
      return { ...state, localAlert: action.alert };

    case 'UPDATE_KEYFRAMES': {
      if (!state.world || !state.world.ambulances) return state;
      const frameMap = new Map(action.frames.map(f => [f.id, f]));
      const newAmbulances = state.world.ambulances.map(a => {
        const frame = frameMap.get(a.id);
        if (!frame || !frame.pos) return a;
        return {
          ...a,
          position: { lat: frame.pos[0], lng: frame.pos[1] },
          status: (frame.status as any) || a.status,
        };
      });
      return { ...state, world: { ...state.world, ambulances: newAmbulances } };
    }

    default:
      return state;
  }
}

// ─── Context ──────────────────────────────────────────────────────────────────

export interface StoreContextValue extends LiveState {
  hospitals: Hospital[];
  ambulances: Ambulance[];
  incidents: Incident[];
  roads: Road[];
  supplies: SupplyItem[];
  supplyRequests: SupplyRequest[];
  decisions: AllocationDecision[];
  events: SimEvent[];
  ledger: LedgerBlock[];
  funds: FundFlow[];
  anomalies: Anomaly[];
  stats: SimStats;
  simTime: number;
  startTime: number;
  running: boolean;
  speed: number;
  alert: string | null;
  autopilotActive: boolean;
  autopilotStep: number;

  dispatch: (action: Action | LiveAction) => void;

  play(): Promise<void>;
  pause(): Promise<void>;
  step(): Promise<void>;
  setSpeed(s: number): Promise<void>;
  restart(): Promise<void>;
  seek(time: number): Promise<void>;
  triggerEvent(eventId: number): Promise<void>;
  approveDecision(id: string): Promise<void>;
  overrideDecision(id: string, hospitalId: string, reason: string): Promise<void>;
  chaos(action: string): Promise<void>;
  verifyLedger(): Promise<void>;
  tamperLedger(blockIndex: number): Promise<void>;
  resetLedger(): Promise<void>;
  addLedgerEntries(entries: LedgerEntry[] | LedgerEntryDTO[]): Promise<void>;
  getMerkleProof(blockIndex: number, entryIndex: number): Promise<void>;
}

const Ctx = createContext<StoreContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function LiveStoreProvider({ children }: { children: ReactNode }) {
  const [state, rawDispatch] = useReducer(reducer, undefined, initialState);
  const wsRef = useRef<ReturnType<typeof createWSClient> | null>(null);

  // Apply dark/light theme to document
  useEffect(() => {
    const root = document.documentElement;
    if (state.theme === 'dark') root.classList.add('dark');
    else root.classList.remove('dark');
  }, [state.theme]);

  // ── WebSocket bootstrap ────────────────────────────────────────────────────
  useEffect(() => {
    const client = createWSClient(state.role);
    wsRef.current = client;

    client.onStatusChange((s) => {
      rawDispatch({ type: 'SET_CONNECTION', status: s });

      // When we first connect, fetch a full snapshot to prime the store
      if (s === 'connected') {
        api.state(state.role)
          .then(world => rawDispatch({ type: 'SET_STATE', world }))
          .catch(err => rawDispatch({ type: 'SET_ERROR', error: String(err) }));
      }
    });

    client.onMessage((env: WSEnvelope) => {
      handleWSMessage(env, rawDispatch);
    });

    return () => {
      client.close();
      wsRef.current = null;
    };
  }, [state.role]);

  // ── Command helpers ────────────────────────────────────────────────────────
  const withPending = useCallback(
    async <T,>(label: string, fn: () => Promise<T>): Promise<T> => {
      rawDispatch({ type: 'SET_PENDING', action: label });
      try {
        const result = await fn();
        return result;
      } catch (e) {
        rawDispatch({ type: 'SET_ERROR', error: String(e) });
        throw e;
      } finally {
        rawDispatch({ type: 'SET_PENDING', action: null });
      }
    },
    []
  );

  const applyStateResult = useCallback((world: WorldStateDTO) => {
    rawDispatch({ type: 'SET_STATE', world });
  }, []);

  const play = useCallback(async () => {
    await withPending('play', () => api.play());
    const w = await api.state(state.role);
    applyStateResult(w);
  }, [withPending, applyStateResult, state.role]);

  const pause = useCallback(async () => {
    await withPending('pause', () => api.pause());
    const w = await api.state(state.role);
    applyStateResult(w);
  }, [withPending, applyStateResult, state.role]);

  const step = useCallback(async () => {
    const w = await withPending('step', () => api.step());
    applyStateResult(w);
  }, [withPending, applyStateResult]);

  const setSpeed = useCallback(async (s: number) => {
    await withPending('setSpeed', () => api.setSpeed(s));
  }, [withPending]);

  const restart = useCallback(async () => {
    const w = await withPending('restart', () => api.restart());
    applyStateResult(w);
    rawDispatch({ type: 'SET_LEDGER_VERIFY', result: null });
  }, [withPending, applyStateResult]);

  const seek = useCallback(async (time: number) => {
    const w = await withPending('seek', () => api.seek(time));
    applyStateResult(w);
  }, [withPending, applyStateResult]);

  const triggerEvent = useCallback(async (eventId: number) => {
    const w = await withPending('triggerEvent', () => api.triggerEvent(eventId));
    applyStateResult(w);
  }, [withPending, applyStateResult]);

  const approveDecision = useCallback(async (id: string) => {
    await withPending('approveDecision', () => api.approveDecision(id, state.role));
    const w = await api.state(state.role);
    applyStateResult(w);
  }, [withPending, applyStateResult, state.role]);

  const overrideDecision = useCallback(async (id: string, hospitalId: string, reason: string) => {
    await withPending('overrideDecision', () =>
      api.overrideDecision(id, hospitalId, reason, state.role)
    );
    const w = await api.state(state.role);
    applyStateResult(w);
  }, [withPending, applyStateResult, state.role]);

  const chaos = useCallback(async (action: string) => {
    const w = await withPending('chaos', () => api.chaos(action));
    applyStateResult(w);
  }, [withPending, applyStateResult]);

  const verifyLedger = useCallback(async () => {
    const result = await withPending('verifyLedger', () => api.verifyLedger());
    rawDispatch({ type: 'SET_LEDGER_VERIFY', result });
  }, [withPending]);

  const tamperLedger = useCallback(async (blockIndex: number) => {
    await withPending('tamperLedger', () => api.tamperLedger(blockIndex));
    const w = await api.state(state.role);
    applyStateResult(w);
    const verifyRes = await api.verifyLedger();
    rawDispatch({ type: 'SET_LEDGER_VERIFY', result: verifyRes });
  }, [withPending, applyStateResult, state.role]);

  const resetLedger = useCallback(async () => {
    await withPending('resetLedger', () => api.resetLedger());
    const w = await api.state(state.role);
    applyStateResult(w);
    rawDispatch({ type: 'SET_LEDGER_VERIFY', result: { valid: true, corruptedBlock: null, reason: 'Reset to valid state' } });
  }, [withPending, applyStateResult, state.role]);

  const addLedgerEntries = useCallback(async (_entries: LedgerEntry[] | LedgerEntryDTO[]) => {
    const w = await api.state(state.role);
    applyStateResult(w);
  }, [applyStateResult, state.role]);

  const getMerkleProof = useCallback(async (_blockIndex: number, _entryIndex: number) => {
    // Handled directly via api.getProof()
  }, []);

  // ── Unified Dispatch (Action | LiveAction) ─────────────────────────────────
  const dispatch = useCallback((action: Action | LiveAction) => {
    if (!action || typeof action !== 'object' || !('type' in action)) return;

    switch (action.type) {
      case 'PLAY':
        play().catch(e => console.error(e));
        break;
      case 'PAUSE':
        pause().catch(e => console.error(e));
        break;
      case 'STEP':
        step().catch(e => console.error(e));
        break;
      case 'SET_SPEED':
        setSpeed(action.speed).catch(e => console.error(e));
        break;
      case 'RESTART':
        restart().catch(e => console.error(e));
        break;
      case 'SEEK':
        seek(action.time).catch(e => console.error(e));
        break;
      case 'APPROVE_DECISION':
        approveDecision(action.id).catch(e => console.error(e));
        break;
      case 'OVERRIDE_DECISION': {
        const hospId = (action as any).newHospitalId || (action as any).hospitalId || '';
        overrideDecision(action.id, hospId, (action as any).reason || '').catch(e => console.error(e));
        break;
      }
      case 'TRIGGER_EVENT':
        triggerEvent(action.eventId).catch(e => console.error(e));
        break;
      case 'CHAOS':
        chaos(action.action).catch(e => console.error(e));
        break;
      case 'VERIFY_LEDGER':
        verifyLedger().catch(e => console.error(e));
        break;
      case 'TAMPER':
        tamperLedger(action.blockIndex).catch(e => console.error(e));
        break;
      case 'RESET_LEDGER':
        resetLedger().catch(e => console.error(e));
        break;
      case 'ADD_LEDGER':
        addLedgerEntries((action as any).entries).catch(e => console.error(e));
        break;
      case 'SET_ROLE':
        rawDispatch({ type: 'SET_ROLE', role: action.role as Role });
        break;
      case 'SET_THEME':
        rawDispatch({ type: 'SET_THEME', theme: action.theme });
        break;
      case 'SET_ALERT':
        rawDispatch({ type: 'SET_LOCAL_ALERT', alert: action.alert });
        break;
      case 'AUTOPILOT_START':
      case 'AUTOPILOT_STOP':
      case 'AUTOPILOT_NEXT':
        break;
      default:
        rawDispatch(action as LiveAction);
        break;
    }
  }, [play, pause, step, setSpeed, restart, seek, approveDecision, overrideDecision, triggerEvent, chaos, verifyLedger, tamperLedger, resetLedger, addLedgerEntries]);

  // Derived properties from active world
  const currentWorld = state.world || initialWorldFallback;

  const contextValue: StoreContextValue = useMemo(() => ({
    ...state,
    hospitals: currentWorld.hospitals as unknown as Hospital[],
    ambulances: currentWorld.ambulances as unknown as Ambulance[],
    incidents: currentWorld.incidents as unknown as Incident[],
    roads: currentWorld.roads as unknown as Road[],
    supplies: currentWorld.supplies as unknown as SupplyItem[],
    supplyRequests: currentWorld.supplyRequests as unknown as SupplyRequest[],
    decisions: currentWorld.decisions as unknown as AllocationDecision[],
    events: currentWorld.events as unknown as SimEvent[],
    ledger: currentWorld.ledger as unknown as LedgerBlock[],
    funds: currentWorld.funds as unknown as FundFlow[],
    anomalies: currentWorld.anomalies as unknown as Anomaly[],
    stats: currentWorld.stats as unknown as SimStats,
    simTime: currentWorld.simTime,
    startTime: currentWorld.startTime,
    running: currentWorld.running,
    speed: currentWorld.speed,
    alert: state.localAlert ?? currentWorld.alert,
    autopilotActive: currentWorld.autopilotActive,
    autopilotStep: currentWorld.autopilotStep,

    dispatch,

    play,
    pause,
    step,
    setSpeed,
    restart,
    seek,
    triggerEvent,
    approveDecision,
    overrideDecision,
    chaos,
    verifyLedger,
    tamperLedger,
    resetLedger,
    addLedgerEntries,
    getMerkleProof,
  }), [
    state,
    currentWorld,
    dispatch,
    play,
    pause,
    step,
    setSpeed,
    restart,
    seek,
    triggerEvent,
    approveDecision,
    overrideDecision,
    chaos,
    verifyLedger,
    tamperLedger,
    resetLedger,
    addLedgerEntries,
    getMerkleProof,
  ]);

  return (
    <Ctx.Provider value={contextValue}>
      {children}
    </Ctx.Provider>
  );
}

// ─── WS message handler ───────────────────────────────────────────────────────

function handleWSMessage(
  env: WSEnvelope,
  dispatch: React.Dispatch<LiveAction>
) {
  switch (env.type) {
    case 'snapshot':
      dispatch({ type: 'SET_STATE', world: env.payload as WorldStateDTO });
      break;

    case 'delta':
      dispatch({ type: 'APPLY_DELTA', delta: env.payload as Partial<WorldStateDTO> });
      break;

    case 'tick': {
      const p = env.payload as Partial<WorldStateDTO>;
      dispatch({ type: 'APPLY_DELTA', delta: p });
      break;
    }

    case 'keyframe_batch': {
      if (Array.isArray(env.payload)) {
        dispatch({ type: 'UPDATE_KEYFRAMES', frames: env.payload as any });
      }
      break;
    }

    case 'alert': {
      dispatch({
        type: 'APPLY_DELTA',
        delta: { alert: (env.payload as { message: string }).message },
      });
      break;
    }

    case 'decision': {
      break;
    }

    default:
      break;
  }
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useStore(): StoreContextValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useStore must be used within LiveStoreProvider');
  return ctx;
}

/** Convenience: returns the world state, or null if not yet loaded. */
export function useWorld(): WorldStateDTO | null {
  return useStore().world;
}
