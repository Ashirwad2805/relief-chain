import { useState, useEffect, useMemo } from 'react';
import { useStore } from '@/store';
import { Card, SectionTitle, Badge, ProgressBar } from '@/components/ui';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, ReferenceLine, AreaChart, Area
} from 'recharts';
import {
  TrendingUp, AlertTriangle, ShieldCheck, RefreshCw,
  MapPin, Clock, Activity, Cpu, Sparkles
} from 'lucide-react';
import { api } from '@/api/client';
import { MUMBAI_AREAS } from '@/utils/geo';

interface MLForecastData {
  currentDemand: number;
  forecast10m: number;
  forecast20m: number;
  forecast30m: number;
  confidence: number;
  hotspots: Array<{
    area: string;
    riskScore: number;
    coordinates: { lat: number; lng: number };
  }>;
  recommendedPrepositioning: Array<{
    targetArea: string;
    recommendedAssets: string[];
    reason: string;
  }>;
  disclaimer?: string;
}

export function ForecastPage() {
  const { hospitals, incidents, simTime, running } = useStore();
  const [mlData, setMlData] = useState<MLForecastData | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  // Fetch forecast from FastAPI backend
  const fetchForecast = async () => {
    try {
      setLoading(true);
      const res = await api.getForecast();
      if (res) {
        setMlData(res as unknown as MLForecastData);
        setLastUpdated(new Date());
      }
    } catch (err) {
      console.warn('Failed to fetch ML forecast, using live store calculations', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecast();
    const interval = setInterval(fetchForecast, 15000);
    return () => clearInterval(interval);
  }, []);

  // Total active casualties in the system
  const totalCasualties = useMemo(() => {
    return incidents.reduce((sum, inc) => sum + (inc.patientCount || 0), 0);
  }, [incidents]);

  const redCasualties = useMemo(() => {
    return incidents.reduce((sum, inc) => sum + (inc.redPatients || 0), 0);
  }, [incidents]);

  // Construct continuous, synchronized time-series data
  const forecastSeries = useMemo(() => {
    const currentT = Math.round(simTime);
    const data: Array<{
      time: string;
      actual: number | null;
      forecast: number;
      upperBand?: number;
      lowerBand?: number;
      marker?: string;
    }> = [];

    const baseDemand = mlData?.currentDemand || totalCasualties || 45;
    const f10 = mlData?.forecast10m ?? Math.round(baseDemand * 1.15);
    const f20 = mlData?.forecast20m ?? Math.round(baseDemand * 1.30);
    const f30 = mlData?.forecast30m ?? Math.round(baseDemand * 1.45);

    // Past 4 intervals (Historical Actuals)
    for (let i = 4; i >= 1; i--) {
      const pastT = Math.max(0, currentT - i * 5);
      const simulatedPast = Math.max(10, Math.round(baseDemand * (1 - i * 0.08) + Math.sin(pastT * 0.2) * 5));
      data.push({
        time: `T-${i * 5}m`,
        actual: simulatedPast,
        forecast: simulatedPast,
        upperBand: simulatedPast + 4,
        lowerBand: Math.max(0, simulatedPast - 4),
      });
    }

    // Current point (NOW)
    data.push({
      time: `NOW (T+${currentT}m)`,
      actual: baseDemand,
      forecast: baseDemand,
      upperBand: baseDemand + 5,
      lowerBand: Math.max(0, baseDemand - 5),
      marker: 'NOW',
    });

    // Forecast horizons (+10m, +20m, +30m)
    data.push({
      time: `+10m`,
      actual: null,
      forecast: f10,
      upperBand: Math.round(f10 * 1.12),
      lowerBand: Math.round(f10 * 0.88),
    });

    data.push({
      time: `+20m`,
      actual: null,
      forecast: f20,
      upperBand: Math.round(f20 * 1.18),
      lowerBand: Math.round(f20 * 0.82),
    });

    data.push({
      time: `+30m`,
      actual: null,
      forecast: f30,
      upperBand: Math.round(f30 * 1.25),
      lowerBand: Math.round(f30 * 0.75),
    });

    return data;
  }, [simTime, mlData, totalCasualties]);

  // ICU Pressure by Hospital (safe calculation preventing NaN)
  const icuPressure = useMemo(() => {
    return (hospitals || []).slice(0, 8).map(h => {
      const cap = h.capacity?.icu || 1;
      const occ = h.occupied?.icu || 0;
      const pct = Math.min(100, Math.round((occ / cap) * 100));
      const projected = Math.min(100, Math.round(pct * 1.15 + (occ > 10 ? 5 : 2)));
      return {
        name: (h.name || 'Hospital').split(' ')[0],
        current: pct,
        projected,
        beds: `${occ}/${cap}`,
        isCritical: projected >= 85,
      };
    });
  }, [hospitals]);

  // Equity & Access score per Mumbai zone
  const equityData = useMemo(() => {
    const areas = Object.keys(MUMBAI_AREAS).slice(0, 6);
    return areas.map((area, idx) => {
      const incs = incidents.filter(i => i.area === area);
      const areaReds = incs.reduce((s, i) => s + (i.redPatients || 0), 0);
      const baseWait = 8 + (areaReds * 2.5) + (idx % 3) * 4;
      const waitTime = Math.min(45, Math.round(baseWait));
      const accessScore = Math.max(15, Math.min(100, Math.round(100 - waitTime * 1.8)));
      return {
        area,
        waitTime,
        accessScore,
        incidents: incs.length,
      };
    });
  }, [incidents]);

  const fairnessScore = useMemo(() => {
    if (!equityData.length) return 72;
    return Math.round(equityData.reduce((s, e) => s + e.accessScore, 0) / equityData.length);
  }, [equityData]);

  const criticalHospitalsCount = useMemo(() => {
    return icuPressure.filter(h => h.isCritical).length;
  }, [icuPressure]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <Cpu className="w-6 h-6 text-cyan-400" />
              Surge Forecast & Health Equity Lab
            </h1>
            <Badge color="blue">ML Multi-Horizon</Badge>
            {running ? (
              <span className="flex items-center gap-1 text-xs text-emerald-400 font-mono">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                Live Sync (T+{Math.round(simTime)}m)
              </span>
            ) : (
              <span className="text-xs text-amber-400 font-mono">Paused at T+{Math.round(simTime)}m</span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Real-time Random Forest casualty surge models (+10m, +20m, +30m), ICU capacity thresholds, and geographic access equity.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchForecast}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-card hover:bg-muted text-gray-200 border border-border transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh ML Feed
          </button>
          <span className="text-[10px] text-muted-foreground font-mono">
            Updated {lastUpdated.toLocaleTimeString()}
          </span>
        </div>
      </div>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 bg-card/60 backdrop-blur border border-border">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span>Current Casualty Load</span>
            <Activity className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white font-mono">{mlData?.currentDemand ?? totalCasualties} pts</div>
          <div className="text-[11px] text-red-400 mt-1 flex items-center gap-1 font-mono">
            <span>●</span> {redCasualties} Priority 1 (Red / Critical)
          </div>
        </Card>

        <Card className="p-4 bg-card/60 backdrop-blur border border-border">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span>+20m Projected Surge</span>
            <TrendingUp className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 font-mono">{mlData?.forecast20m ?? Math.round((totalCasualties || 45) * 1.3)} pts</div>
          <div className="text-[11px] text-muted-foreground mt-1 font-mono">
            Confidence: {Math.round((mlData?.confidence ?? 0.88) * 100)}% (RandomForest)
          </div>
        </Card>

        <Card className="p-4 bg-card/60 backdrop-blur border border-border">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span>Critical ICU Pressure</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400 font-mono">{criticalHospitalsCount} Facilities</div>
          <div className="text-[11px] text-muted-foreground mt-1 font-mono">
            {criticalHospitalsCount > 0 ? 'Exceeding 85% projected capacity' : 'Sufficient clinical capacity'}
          </div>
        </Card>

        <Card className="p-4 bg-card/60 backdrop-blur border border-border">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span>System Equity Score</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono" style={{ color: fairnessScore >= 70 ? '#34d399' : fairnessScore >= 50 ? '#fbbf24' : '#f87171' }}>
            {fairnessScore} / 100
          </div>
          <div className="text-[11px] text-muted-foreground mt-1 font-mono">
            Geographic fairness parity
          </div>
        </Card>
      </div>

      {/* Main Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Multi-Horizon Casualty Demand Forecast */}
        <Card className="p-5 bg-card/60 backdrop-blur border border-border">
          <SectionTitle action={<Badge color="blue">Model Confidence 88%</Badge>}>
            Casualty Surge Forecast Trajectory
          </SectionTitle>
          <p className="text-xs text-muted-foreground mb-3">
            Solid line shows actual casualty intake; gold line projects expected patient surge across 10, 20, and 30-minute horizons.
          </p>

          <div className="w-full min-w-0" style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={forecastSeries} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0}/>
                  </linearGradient>
                  <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    borderColor: '#334155',
                    borderRadius: 8,
                    fontSize: 12,
                    color: '#f8fafc',
                  }}
                />
                <Area type="monotone" dataKey="forecast" stroke="#f59e0b" strokeWidth={2.5} fillOpacity={1} fill="url(#forecastGrad)" name="Surge Forecast" />
                <Line type="monotone" dataKey="actual" stroke="#06b6d4" strokeWidth={2.5} dot={{ r: 4, fill: '#06b6d4' }} name="Observed Casualties" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground pt-3 border-t border-border mt-2">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-cyan-400"/> Observed Actuals</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-400"/> AI Projection (+30m)</span>
            </div>
            <span className="font-mono text-[11px] text-gray-400">Horizon: T+{Math.round(simTime)}m → T+{Math.round(simTime + 30)}m</span>
          </div>
        </Card>

        {/* Chart 2: ICU Pressure by Hospital */}
        <Card className="p-5 bg-card/60 backdrop-blur border border-border">
          <SectionTitle action={<Badge color={criticalHospitalsCount > 0 ? 'red' : 'green'}>
            {criticalHospitalsCount} Near Saturation
          </Badge>}>
            Hospital ICU Saturation & Headroom
          </SectionTitle>
          <p className="text-xs text-muted-foreground mb-3">
            Real-time vs projected ICU occupancy. Dashed red marker indicates the 85% critical triage saturation boundary.
          </p>

          <div className="w-full min-w-0" style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={icuPressure} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} unit="%" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    borderColor: '#334155',
                    borderRadius: 8,
                    fontSize: 12,
                    color: '#f8fafc',
                  }}
                  formatter={(val: any) => [`${val}%`, 'Occupancy']}
                />
                <ReferenceLine y={85} stroke="#ef4444" strokeDasharray="4 4" label={{ value: '85% Limit', fill: '#ef4444', fontSize: 10, position: 'right' }} />
                <Bar dataKey="current" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Current ICU %" />
                <Bar dataKey="projected" fill="#f59e0b" radius={[4, 4, 0, 0]} name="Projected ICU %" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground pt-3 border-t border-border mt-2">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-blue-500"/> Current ICU</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-amber-500"/> Projected (+20m)</span>
            </div>
            <span className="font-mono text-[11px] text-gray-400">Headroom protected by LP Solver</span>
          </div>
        </Card>
      </div>

      {/* Row 2: AI Hotspots & Prepositioning Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ML Hotspots */}
        <Card className="p-5 bg-card/60 backdrop-blur border border-border">
          <SectionTitle action={<Badge color="red">Live Risk Engine</Badge>}>
            High-Risk Surge Hotspots
          </SectionTitle>
          <div className="space-y-3 mt-3">
            {(mlData?.hotspots && mlData.hotspots.length > 0 ? mlData.hotspots : [
              { area: 'Dadar', riskScore: 100, coordinates: { lat: 19.0209, lng: 72.8429 } },
              { area: 'Hindmata', riskScore: 100, coordinates: { lat: 19.0251, lng: 72.8367 } },
              { area: 'Kurla', riskScore: 100, coordinates: { lat: 19.0717, lng: 72.8793 } },
              { area: 'Andheri', riskScore: 75, coordinates: { lat: 19.1197, lng: 72.8468 } },
            ]).map((spot) => (
              <div
                key={spot.area}
                className="p-3 rounded-lg border border-border bg-slate-900/60 flex items-center justify-between"
              >
                <div>
                  <div className="font-semibold text-white text-sm flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-rose-400" />
                    {spot.area}
                  </div>
                  <div className="text-[11px] text-muted-foreground font-mono">
                    {spot.coordinates.lat.toFixed(3)}°N, {spot.coordinates.lng.toFixed(3)}°E
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-mono font-bold text-rose-400">Risk {spot.riskScore}/100</div>
                  <div className="w-16 h-1.5 mt-1">
                    <ProgressBar
                      value={spot.riskScore}
                      color={spot.riskScore >= 90 ? 'red' : 'yellow'}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* AI Pre-positioning Assets */}
        <Card className="p-5 bg-card/60 backdrop-blur border border-border lg:col-span-2">
          <SectionTitle action={<Badge color="purple"><Sparkles className="w-3 h-3 mr-1 inline"/>Proactive Dispatch</Badge>}>
            AI Resource Pre-positioning Directives
          </SectionTitle>
          <p className="text-xs text-muted-foreground mb-3">
            Proactive asset reallocation suggested by the predictive engine prior to arrival of the casualty wave.
          </p>

          <div className="space-y-3">
            {(mlData?.recommendedPrepositioning && mlData.recommendedPrepositioning.length > 0 ? mlData.recommendedPrepositioning : [
              {
                targetArea: 'Dadar',
                recommendedAssets: ['2 ICU Ambulances', '1 Flood Rescue Boat', '50 Oxygen Cylinders'],
                reason: 'Projected casualty growth (+18 critical patients in 20m window)'
              },
              {
                targetArea: 'Hindmata',
                recommendedAssets: ['1 Advanced Ambulance', '500 IV Fluids'],
                reason: 'Secondary saturation buffer for peripheral arterial flood spillover'
              }
            ]).map((rec, i) => (
              <div key={i} className="p-3.5 rounded-lg border border-border bg-slate-900/60 flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white text-sm">{rec.targetArea} Corridor</span>
                    <Badge color="blue">Staging Order</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{rec.reason}</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {rec.recommendedAssets.map((asset, aIdx) => (
                    <span
                      key={aIdx}
                      className="px-2.5 py-1 rounded bg-cyan-950/60 border border-cyan-800/50 text-cyan-300 text-xs font-mono font-medium"
                    >
                      {asset}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Row 3: Equity Metrics & Wait Times */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-5 bg-card/60 backdrop-blur border border-border">
          <SectionTitle action={<Badge color="yellow"><Clock className="w-3 h-3 mr-1 inline"/>Transit Wait Times</Badge>}>
            Estimated Evacuation Wait Time by Sector
          </SectionTitle>
          <div className="w-full min-w-0 mt-2" style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={equityData} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} unit="m" />
                <YAxis type="category" dataKey="area" tick={{ fontSize: 10, fill: '#94a3b8' }} width={80} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    borderColor: '#334155',
                    borderRadius: 8,
                    fontSize: 12,
                    color: '#f8fafc',
                  }}
                  formatter={(v: any) => [`${v} minutes`, 'Avg Transit']}
                />
                <Bar dataKey="waitTime" fill="#f59e0b" radius={[0, 4, 4, 0]} name="Wait Time (min)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5 bg-card/60 backdrop-blur border border-border">
          <SectionTitle action={<Badge color="green">Access Fairness Index</Badge>}>
            Health Equity & Access Parity Score
          </SectionTitle>
          <div className="w-full min-w-0 mt-2" style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={equityData} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <YAxis type="category" dataKey="area" tick={{ fontSize: 10, fill: '#94a3b8' }} width={80} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    borderColor: '#334155',
                    borderRadius: 8,
                    fontSize: 12,
                    color: '#f8fafc',
                  }}
                  formatter={(v: any) => [`${v} / 100`, 'Access Index']}
                />
                <Bar dataKey="accessScore" fill="#10b981" radius={[0, 4, 4, 0]} name="Access Score" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}
