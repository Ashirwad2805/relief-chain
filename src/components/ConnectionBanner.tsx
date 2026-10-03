/**
 * ConnectionBanner — shows when the frontend is disconnected from the backend.
 * Fixes A1: when backend is offline, UI shows "Disconnected / Replay Mode" instead of silently
 * running its own simulation.
 */
import { useStore } from '@/api/liveStore';

const STATUS_CONFIG = {
  connected: null,
  reconnecting: {
    bg: 'rgba(255,181,71,0.15)',
    border: 'rgba(255,181,71,0.4)',
    color: '#FFB547',
    text: 'Reconnecting to backend…',
    icon: '⟳',
  },
  disconnected: {
    bg: 'rgba(255,92,122,0.12)',
    border: 'rgba(255,92,122,0.35)',
    color: '#FF5C7A',
    text: 'Backend offline — Replay Mode (last received state shown)',
    icon: '⚠',
  },
  replay: {
    bg: 'rgba(91,140,255,0.12)',
    border: 'rgba(91,140,255,0.35)',
    color: '#5B8CFF',
    text: 'Replay Mode — recorded data only',
    icon: '▶',
  },
} as const;

export function ConnectionBanner() {
  const { connectionStatus } = useStore();
  const cfg = STATUS_CONFIG[connectionStatus];
  if (!cfg) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        padding: '6px 16px',
        background: cfg.bg,
        borderBottom: `1px solid ${cfg.border}`,
        color: cfg.color,
        fontSize: '13px',
        fontWeight: 500,
        backdropFilter: 'blur(8px)',
        letterSpacing: '0.01em',
      }}
    >
      <span style={{ fontFamily: 'monospace' }}>{cfg.icon}</span>
      {cfg.text}
      {connectionStatus === 'disconnected' && (
        <span style={{ opacity: 0.7, fontSize: '11px' }}>
          &nbsp;— showing last known state
        </span>
      )}
    </div>
  );
}
