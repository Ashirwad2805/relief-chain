/**
 * src/components/PerfHUD.tsx
 * ==========================
 * Real-time Performance Heads-Up Display (Section 6.3, 6.4, 6.6).
 * Measures live:
 * - FPS (running 60-frame rolling window)
 * - Frame render time (p50 / p95)
 * - Long tasks count (PerformanceObserver)
 * - JS Heap memory (performance.memory)
 * - DOM nodes count
 * - Window.__perf export for headless benchmark runners (Section 6.7)
 *
 * Can be toggled with key 'P' or a floating button on any route.
 */

import { useState, useEffect, useRef } from 'react';
import { Activity, X, Gauge, Cpu, Layers } from 'lucide-react';

export interface PerfMetrics {
  fps: number;
  fpsMin: number;
  frameTimeMs: number;
  frameTimeP95: number;
  longTasks: number;
  domNodes: number;
  heapUsedMb: number | null;
  heapTotalMb: number | null;
  timestamp: number;
}

export function usePerfMetrics(): PerfMetrics {
  const [metrics, setMetrics] = useState<PerfMetrics>({
    fps: 60,
    fpsMin: 60,
    frameTimeMs: 16.6,
    frameTimeP95: 16.6,
    longTasks: 0,
    domNodes: 0,
    heapUsedMb: null,
    heapTotalMb: null,
    timestamp: Date.now(),
  });

  const frameTimesRef = useRef<number[]>([]);
  const lastFrameRef = useRef<number>(performance.now());
  const longTasksCountRef = useRef<number>(0);

  useEffect(() => {
    // 1. Observe long tasks if supported
    try {
      if ('PerformanceObserver' in window) {
        const observer = new PerformanceObserver((list) => {
          longTasksCountRef.current += list.getEntries().length;
        });
        observer.observe({ entryTypes: ['longtask'] });
        return () => observer.disconnect();
      }
    } catch {
      // not supported in all browsers
    }
  }, []);

  useEffect(() => {
    let animId: number;
    let sampleInterval: number;

    const onFrame = (now: number) => {
      const dt = now - lastFrameRef.current;
      lastFrameRef.current = now;
      if (dt > 0 && dt < 200) {
        frameTimesRef.current.push(dt);
        if (frameTimesRef.current.length > 60) {
          frameTimesRef.current.shift();
        }
      }
      animId = requestAnimationFrame(onFrame);
    };

    animId = requestAnimationFrame(onFrame);

    // Sample stats every 500ms
    sampleInterval = window.setInterval(() => {
      const samples = frameTimesRef.current;
      if (samples.length === 0) return;

      const avgDt = samples.reduce((a, b) => a + b, 0) / samples.length;
      const fps = Math.round(1000 / avgDt);
      const sorted = [...samples].sort((a, b) => a - b);
      const p95 = Math.round(sorted[Math.floor(sorted.length * 0.95)] || avgDt);
      const maxDt = Math.max(...samples);
      const fpsMin = Math.round(1000 / maxDt);

      const domNodes = document.getElementsByTagName('*').length;

      // Chrome memory
      const mem = (performance as any).memory;
      const heapUsed = mem ? Math.round(mem.usedJSHeapSize / (1024 * 1024)) : null;
      const heapTotal = mem ? Math.round(mem.totalJSHeapSize / (1024 * 1024)) : null;

      const current = {
        fps: Math.min(120, fps),
        fpsMin: Math.min(120, fpsMin),
        frameTimeMs: Math.round(avgDt * 10) / 10,
        frameTimeP95: p95,
        longTasks: longTasksCountRef.current,
        domNodes,
        heapUsedMb: heapUsed,
        heapTotalMb: heapTotal,
        timestamp: Date.now(),
      };

      setMetrics(current);

      // Export to window.__perf for headless testing (Section 6.7)
      (window as any).__perf = current;
    }, 500);

    return () => {
      cancelAnimationFrame(animId);
      clearInterval(sampleInterval);
    };
  }, []);

  return metrics;
}

export function PerfHUD() {
  const [open, setOpen] = useState(false);
  const metrics = usePerfMetrics();

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'p' || e.key === 'P') {
        // Only toggle if not typing in an input
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
          setOpen(prev => !prev);
        }
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, []);

  const fpsColor =
    metrics.fps >= 55 ? 'text-green-400' :
    metrics.fps >= 35 ? 'text-yellow-400' : 'text-red-400';

  return (
    <>
      {/* Floating Toggle Button */}
      <button
        onClick={() => setOpen(prev => !prev)}
        className="fixed bottom-4 right-4 z-50 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-mono font-medium backdrop-blur-md transition-all shadow-lg border"
        style={{
          background: 'rgba(15, 23, 42, 0.75)',
          borderColor: 'rgba(255, 255, 255, 0.15)',
          color: 'var(--text-primary)',
        }}
        title="Toggle Performance HUD (Press 'P')"
      >
        <Activity size={14} className={fpsColor} />
        <span className={fpsColor}>{metrics.fps} FPS</span>
        <span className="text-[10px] text-gray-400">({metrics.frameTimeP95}ms)</span>
      </button>

      {/* Expanded HUD Overlay */}
      {open && (
        <div
          className="fixed bottom-16 right-4 z-50 w-72 rounded-xl p-4 backdrop-blur-xl shadow-2xl border font-mono text-xs transition-all animate-fadeIn"
          style={{
            background: 'rgba(15, 23, 42, 0.90)',
            borderColor: 'rgba(255, 255, 255, 0.20)',
            color: '#e2e8f0',
          }}
        >
          <div className="flex items-center justify-between pb-2 mb-3 border-b border-white/10">
            <div className="flex items-center gap-2 font-semibold text-white">
              <Gauge size={16} className="text-cyan-400" />
              <span>Performance HUD</span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <X size={14} />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2 mb-3">
            <div className="p-2 rounded bg-white/5 border border-white/5">
              <div className="text-[10px] text-gray-400 uppercase">Frame Rate</div>
              <div className={`text-xl font-bold ${fpsColor}`}>{metrics.fps} <span className="text-xs">FPS</span></div>
              <div className="text-[10px] text-gray-400">Min: {metrics.fpsMin} FPS</div>
            </div>

            <div className="p-2 rounded bg-white/5 border border-white/5">
              <div className="text-[10px] text-gray-400 uppercase">Frame Latency</div>
              <div className="text-xl font-bold text-cyan-300">{metrics.frameTimeP95} <span className="text-xs">ms</span></div>
              <div className="text-[10px] text-gray-400">Avg: {metrics.frameTimeMs} ms</div>
            </div>
          </div>

          <div className="space-y-1.5 text-[11px]">
            <div className="flex items-center justify-between py-0.5">
              <span className="flex items-center gap-1.5 text-gray-400">
                <Layers size={12} /> DOM Elements
              </span>
              <span className="font-semibold text-white">{metrics.domNodes}</span>
            </div>

            <div className="flex items-center justify-between py-0.5">
              <span className="flex items-center gap-1.5 text-gray-400">
                <Cpu size={12} /> Long Tasks (&gt;50ms)
              </span>
              <span className={metrics.longTasks > 0 ? 'text-amber-400' : 'text-green-400'}>
                {metrics.longTasks}
              </span>
            </div>

            {metrics.heapUsedMb !== null && (
              <div className="flex items-center justify-between py-0.5">
                <span className="flex items-center gap-1.5 text-gray-400">
                  <Activity size={12} /> JS Heap Memory
                </span>
                <span className="font-semibold text-white">
                  {metrics.heapUsedMb} / {metrics.heapTotalMb} MB
                </span>
              </div>
            )}
          </div>

          <div className="mt-3 pt-2 border-t border-white/10 text-[9px] text-gray-400 flex justify-between">
            <span>Budget: &ge;55 FPS, &le;24ms</span>
            <span className="text-cyan-400">window.__perf ready</span>
          </div>
        </div>
      )}
    </>
  );
}
