import { useState } from 'react';
import { LandingPage } from './components/LandingPage/LandingPage';
import { Sidebar } from './components/Sidebar/Sidebar';
import { DashboardView } from './components/Dashboard/DashboardView';
import { DocumentsView } from './components/Documents/DocumentsView';
import { WorkflowCanvas } from './components/Canvas/WorkflowCanvas';
import { ExecutionView } from './components/Execution/ExecutionView';
import { useExecutionStore } from './store/executionStore';
import type { AppRoute } from './types';
import appStyles from './App.module.css';

type AppView = 'landing' | AppRoute;

export function App() {
  const [view, setView] = useState<AppView>('landing');
  const startExecution = useExecutionStore((state) => state.startExecution);

  const handleNavigate = (route: AppRoute) => {
    setView(route);
  };

  const handleRunWorkflow = async (wfId: string, name: string) => {
    setView('executions');
    await startExecution(wfId, name);
  };

  // Show landing page
  if (view === 'landing') {
    return <LandingPage onStart={() => setView('dashboard')} />;
  }

  return (
    <div className={appStyles.appShell}>
      <Sidebar activeRoute={view as AppRoute} onNavigate={handleNavigate} />
      <main className={appStyles.main}>
        {view === 'dashboard' && (
          <DashboardView onNavigate={handleNavigate} />
        )}
        {view === 'documents' && (
          <DocumentsView onNavigate={handleNavigate} />
        )}
        {view === 'workflows' && (
          <WorkflowCanvas onRunWorkflow={handleRunWorkflow} />
        )}
        {view === 'executions' && (
          <ExecutionView />
        )}
        {view === 'settings' && (
          <SettingsView />
        )}
      </main>
    </div>
  );
}

// Inline minimal Settings placeholder
function SettingsView() {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexDirection: 'column',
      gap: 16,
      color: 'var(--text-muted)',
    }}>
      <span style={{ fontSize: 48 }}>⚙️</span>
      <h2 style={{ margin: 0 }}>Settings</h2>
      <p style={{ margin: 0, fontSize: 13 }}>Application settings coming soon.</p>
    </div>
  );
}