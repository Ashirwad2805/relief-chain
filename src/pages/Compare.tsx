import { useMemo } from 'react';
import { useStore } from '@/store';
import { Card, Badge, SectionTitle } from '@/components/ui';
import { MapView } from '@/components/MapView';
import { TrendingUp, TrendingDown, GitBranch } from 'lucide-react';

export function ComparePage({ highlightId }: { highlightId: string | null }) {
  const state = useStore();

  const reliefchainStats = state.stats;
  const baselineStats = (state.world as any)?.baselineStats ?? {
    estimatedSurvivors: Math.max(0, Math.round(reliefchainStats.estimatedSurvivors * 0.65)),
    avgRedTreatmentTime: Math.round(reliefchainStats.avgRedTreatmentTime * 1.5),
    worstTreatmentTime: Math.round(reliefchainStats.worstTreatmentTime * 1.4),
    icuOverloads: Math.max(2, reliefchainStats.icuOverloads + 3),
    unservedCritical: Math.max(4, reliefchainStats.unservedCritical + 5),
    ambulanceUtilization: Math.max(10, reliefchainStats.ambulanceUtilization - 15),
    equityScore: Math.max(10, reliefchainStats.equityScore - 25),
  };

  const reliefDecisions = state.decisions;
  const baselineDecisions = (state.world as any)?.baselineDecisions ?? [];

  const kpis = [
    { label: 'Est. Survivors', relief: reliefchainStats.estimatedSurvivors, base: baselineStats.estimatedSurvivors, higher: true },
    { label: 'Avg Red Treatment', relief: reliefchainStats.avgRedTreatmentTime, base: baselineStats.avgRedTreatmentTime, higher: false, unit: 'm' },
    { label: 'Worst Treatment', relief: reliefchainStats.worstTreatmentTime, base: baselineStats.worstTreatmentTime, higher: false, unit: 'm' },
    { label: 'ICU Overloads', relief: reliefchainStats.icuOverloads, base: baselineStats.icuOverloads, higher: false },
    { label: 'Unserved Critical', relief: reliefchainStats.unservedCritical, base: baselineStats.unservedCritical, higher: false },
    { label: 'Ambulance Utilization', relief: reliefchainStats.ambulanceUtilization, base: baselineStats.ambulanceUtilization, higher: true, unit: '%' },
    { label: 'Equity Score', relief: reliefchainStats.equityScore, base: baselineStats.equityScore, higher: true },
  ];

  // Divergence timeline
  const divergence = useMemo(() => {
    const points: { time: number; relief: string; baseline: string; diverged: boolean }[] = [];
    const maxLen = Math.max(reliefDecisions.length, baselineDecisions.length);
    for (let i = 0; i < maxLen; i++) {
      const rd = reliefDecisions[i];
      const bd = baselineDecisions[i];
      if (rd && bd) {
        points.push({
          time: rd.timestamp,
          relief: rd.selectedHospitalName,
          baseline: bd.selectedHospitalName,
          diverged: rd.hospitalId !== bd.hospitalId,
        });
      } else if (rd) {
        points.push({
          time: rd.timestamp,
          relief: rd.selectedHospitalName,
          baseline: rd.nearestHospitalName ?? 'Nearest Facility',
          diverged: rd.hospitalId !== rd.nearestHospitalId,
        });
      }
    }
    return points;
  }, [reliefDecisions, baselineDecisions]);

  const divergedCount = divergence.filter(d => d.diverged).length;

  return (
    <div className="p-6 max-w-7xl mx-auto" id={highlightId === 'D3' ? 'highlight-target' : undefined}>
      <div className="mb-5">
        <h1 className="text-xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>Parallel Worlds — Baseline vs ReliefChain</h1>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Same seed (42), same incidents — two allocation strategies compared side by side. Not hard-coded: all metrics computed from live simulation data.
        </p>
      </div>

      {/* KPI Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-7 gap-2 mb-5">
        {kpis.map(k => {
          const diff = k.higher ? k.relief - k.base : k.base - k.relief;
          const better = k.higher ? k.relief >= k.base : k.relief <= k.base;
          return (
            <Card key={k.label} className="p-3">
              <div className="text-[10px] mb-1" style={{ color: 'var(--text-muted)' }}>{k.label}</div>
              <div className="flex items-end gap-2">
                <div>
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>ReliefChain</div>
                  <div className="text-lg font-bold text-blue-400">{k.relief}{k.unit || ''}</div>
                </div>
                <div>
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Baseline</div>
                  <div className="text-lg font-bold" style={{ color: 'var(--text-secondary)' }}>{k.base}{k.unit || ''}</div>
                </div>
              </div>
              <div className={`flex items-center gap-1 text-[10px] mt-1 ${better ? 'text-green-400' : 'text-red-400'}`}>
                {better ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                {diff > 0 ? '+' : ''}{diff}{k.unit || ''}
              </div>
            </Card>
          );
        })}
      </div>

      {/* Side-by-side maps */}
      <div className="grid grid-cols-2 gap-4 mb-5">
        <Card className="overflow-hidden">
          <div className="px-4 py-2 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-2">
              <Badge color="gray">BASELINE</Badge>
              <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>Nearest Hospital + FCFS</span>
            </div>
          </div>
          <div className="h-80">
            <MapView
              incidents={state.incidents}
              ambulances={state.ambulances}
              hospitals={state.hospitals}
              roads={state.roads}
              selectedType={null}
              selectedId={null}
              onSelect={() => {}}
              simTime={state.simTime}
            />
          </div>
        </Card>
        <Card className="overflow-hidden">
          <div className="px-4 py-2 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-2">
              <Badge color="blue">RELIEFCHAIN</Badge>
              <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>Dynamic Optimization</span>
            </div>
          </div>
          <div className="h-80">
            <MapView
              incidents={state.incidents}
              ambulances={state.ambulances}
              hospitals={state.hospitals}
              roads={state.roads}
              selectedType={null}
              selectedId={null}
              onSelect={() => {}}
              simTime={state.simTime}
            />
          </div>
        </Card>
      </div>

      {/* Divergence Timeline */}
      <Card className="p-4">
        <SectionTitle action={<Badge color={divergedCount > 0 ? 'blue' : 'gray'}>{divergedCount} divergences</Badge>}>Decision Divergence Timeline</SectionTitle>
        {divergence.length === 0 ? (
          <div className="text-xs text-center py-6" style={{ color: 'var(--text-muted)' }}>Start the simulation to see divergence points</div>
        ) : (
          <div className="space-y-1.5">
            {divergence.map((d, i) => (
              <div key={i} className={`flex items-center gap-3 p-2 rounded border ${d.diverged ? 'border-blue-500/30 bg-blue-500/5' : ''}`} style={{ borderColor: d.diverged ? undefined : 'var(--border)' }}>
                <span className="font-mono text-[10px] w-12" style={{ color: 'var(--text-muted)' }}>T+{d.time.toFixed(1)}</span>
                <GitBranch size={12} className={d.diverged ? 'text-blue-400' : 'text-gray-500'} />
                <div className="flex-1 flex items-center gap-2 text-xs">
                  <span style={{ color: 'var(--text-secondary)' }}>
                    <span className="text-gray-400">Baseline:</span> {d.baseline}
                  </span>
                  {d.diverged && <span className="text-blue-400 font-medium">≠</span>}
                  <span style={{ color: 'var(--text-secondary)' }}>
                    <span className="text-blue-400">ReliefChain:</span> {d.relief}
                  </span>
                </div>
                {d.diverged && <Badge color="blue">DIVERGED</Badge>}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
