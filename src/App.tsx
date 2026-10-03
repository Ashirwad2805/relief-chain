import { useState, useCallback } from 'react';
import { HashRouter, Routes, Route } from 'react-router-dom';
import LandingPage from '@/pages/LandingPage';
import { LiveStoreProvider } from '@/api/liveStore';
import { ConnectionBanner } from '@/components/ConnectionBanner';
import { Sidebar } from '@/components/Sidebar';
import { TopBar } from '@/components/TopBar';
import { CommandPalette } from '@/components/CommandPalette';
import { EvaluateModal } from '@/components/EvaluateModal';
import { HomePage } from '@/pages/Home';
import { LiveOpsPage } from '@/pages/LiveOps';
import { IncidentsPage } from '@/pages/Incidents';
import { FleetPage } from '@/pages/Fleet';
import { HospitalsPage } from '@/pages/Hospitals';
import { SuppliesPage } from '@/pages/Supplies';
import { DecisionsPage } from '@/pages/Decisions';
import { PolicyStudioPage } from '@/pages/PolicyStudio';
import { SandboxPage } from '@/pages/Sandbox';
import { ComparePage } from '@/pages/Compare';
import { ForecastPage } from '@/pages/Forecast';
import { FundsPage } from '@/pages/Funds';
import { LedgerPage } from '@/pages/Ledger';
import { ReceiptsPage } from '@/pages/Receipts';
import { AuditPage } from '@/pages/Audit';
import { ScenariosPage } from '@/pages/Scenarios';
import { ReplaysPage } from '@/pages/Replays';
import { CollectionsPage } from '@/pages/Collections';
import { StakeholdersPage } from '@/pages/Stakeholders';
import { IntegrationsPage } from '@/pages/Integrations';
import { ArchitecturePage } from '@/pages/Architecture';
import { SettingsPage } from '@/pages/Settings';
import { StressLabPage } from '@/pages/StressLab';
import { PerfHUD } from '@/components/PerfHUD';

function AppShell() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [evalOpen, setEvalOpen] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);

  const handleHighlight = useCallback((_path: string, elementId: string) => {
    setHighlightId(elementId);
    setTimeout(() => setHighlightId(null), 5000);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
      {/* Phase 1 — A1: shows "Disconnected / Replay Mode" when backend is offline */}
      <ConnectionBanner />
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar onOpenSearch={() => setSearchOpen(true)} onOpenEvaluate={() => setEvalOpen(true)} />
        <main className="flex-1 overflow-hidden relative">
          <Routes>
            <Route path="/control-room" element={<div className="h-full overflow-y-auto"><HomePage highlightId={highlightId} /></div>} />
            <Route path="/live-ops" element={<LiveOpsPage highlightId={highlightId} />} />
            <Route path="/incidents" element={<div className="h-full overflow-y-auto"><IncidentsPage /></div>} />
            <Route path="/fleet" element={<div className="h-full overflow-y-auto"><FleetPage /></div>} />
            <Route path="/hospitals" element={<div className="h-full overflow-y-auto"><HospitalsPage /></div>} />
            <Route path="/supplies" element={<div className="h-full overflow-y-auto"><SuppliesPage /></div>} />
            <Route path="/decisions" element={<div className="h-full overflow-y-auto"><DecisionsPage highlightId={highlightId} /></div>} />
            <Route path="/policy-studio" element={<div className="h-full overflow-y-auto"><PolicyStudioPage /></div>} />
            <Route path="/sandbox" element={<div className="h-full overflow-y-auto"><SandboxPage /></div>} />
            <Route path="/compare" element={<div className="h-full overflow-y-auto"><ComparePage highlightId={highlightId} /></div>} />
            <Route path="/forecast" element={<div className="h-full overflow-y-auto"><ForecastPage /></div>} />
            <Route path="/funds" element={<div className="h-full overflow-y-auto"><FundsPage highlightId={highlightId} /></div>} />
            <Route path="/ledger" element={<div className="h-full overflow-y-auto"><LedgerPage highlightId={highlightId} /></div>} />
            <Route path="/receipts" element={<div className="h-full overflow-y-auto"><ReceiptsPage /></div>} />
            <Route path="/audit" element={<div className="h-full overflow-y-auto"><AuditPage highlightId={highlightId} /></div>} />
            <Route path="/scenarios" element={<div className="h-full overflow-y-auto"><ScenariosPage /></div>} />
            <Route path="/replays" element={<div className="h-full overflow-y-auto"><ReplaysPage /></div>} />
            <Route path="/collections" element={<div className="h-full overflow-y-auto"><CollectionsPage /></div>} />
            <Route path="/stakeholders" element={<div className="h-full overflow-y-auto"><StakeholdersPage /></div>} />
            <Route path="/integrations" element={<div className="h-full overflow-y-auto"><IntegrationsPage /></div>} />
            <Route path="/architecture" element={<div className="h-full overflow-y-auto"><ArchitecturePage highlightId={highlightId} /></div>} />
            <Route path="/settings" element={<div className="h-full overflow-y-auto"><SettingsPage /></div>} />
            <Route path="/stress" element={<StressLabPage />} />
          </Routes>
        </main>
      </div>
      <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
      <EvaluateModal open={evalOpen} onClose={() => setEvalOpen(false)} onHighlight={handleHighlight} />
      <PerfHUD />
    </div>
  );
}

function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route
          path="/*"
          element={
            <LiveStoreProvider>
              <AppShell />
            </LiveStoreProvider>
          }
        />
      </Routes>
    </HashRouter>
  );
}

export default App;
