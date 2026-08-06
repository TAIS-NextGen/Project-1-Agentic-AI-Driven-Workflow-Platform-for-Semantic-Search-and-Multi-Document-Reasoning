import { useEffect, useState } from 'react';
import { LandingPage } from './components/LandingPage/LandingPage';
import { Sidebar } from './components/Sidebar/Sidebar';
import { DashboardView } from './components/Dashboard/DashboardView';
import { DocumentsView } from './components/Documents/DocumentsView';
import { WorkflowCanvas } from './components/Canvas/WorkflowCanvas';
import { WorkflowManager } from './components/WorkflowManager/WorkflowManager';
import { ExecutionView } from './components/Execution/ExecutionView';
import { useExecutionStore } from './store/executionStore';
import { useWorkflowStore } from './store/workflowStore';
import type { AppRoute } from './types';
import appStyles from './App.module.css';

type AppView = 'landing' | AppRoute;
export type AppTheme = 'dark' | 'light';

function getInitialTheme(): AppTheme {
  const savedTheme = window.localStorage.getItem('flowdocs-theme');
  if (savedTheme === 'light' || savedTheme === 'dark') return savedTheme;
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function App() {
  const [view, setView] = useState<AppView>('landing');
  const [theme, setTheme] = useState<AppTheme>(getInitialTheme);
  const startExecution = useExecutionStore((state) => state.startExecution);
  const activeWorkflowId = useWorkflowStore((state) => state.activeWorkflowId);
  const setActiveWorkflow = useWorkflowStore((state) => state.setActiveWorkflow);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem('flowdocs-theme', theme);
    const themeMeta = document.querySelector('meta[name="theme-color"]');
    themeMeta?.setAttribute('content', theme === 'light' ? '#f4f7fb' : '#07080e');
  }, [theme]);

  const toggleTheme = () => setTheme((current) => (current === 'dark' ? 'light' : 'dark'));

  const handleNavigate = (route: AppRoute) => {
    setView(route);
  };

  const handleRunWorkflow = async (wfId: string, name: string) => {
    setView('executions');
    await startExecution(wfId, name);
  };

  if (view === 'landing') {
    return <LandingPage onStart={() => setView('dashboard')} theme={theme} onToggleTheme={toggleTheme} />;
  }

  return (
    <div className={appStyles.appShell}>
      <Sidebar
        activeRoute={view as AppRoute}
        onNavigate={handleNavigate}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
      <main className={appStyles.main}>
        {view === 'dashboard' && <DashboardView onNavigate={handleNavigate} />}
        {view === 'documents' && <DocumentsView onNavigate={handleNavigate} />}
        {view === 'workflows' && (
          activeWorkflowId
            ? (
              <WorkflowCanvas
                onRunWorkflow={handleRunWorkflow}
                onBackToWorkflows={() => setActiveWorkflow(null)}
                theme={theme}
                onToggleTheme={toggleTheme}
              />
            )
            : <WorkflowManager />
        )}
        {view === 'executions' && <ExecutionView />}
        {view === 'settings' && <SettingsView theme={theme} onToggleTheme={toggleTheme} />}
      </main>
    </div>
  );
}

function SettingsView({ theme, onToggleTheme }: { theme: AppTheme; onToggleTheme: () => void }) {
  return (
    <div className={appStyles.settingsPage}>
      <header className={appStyles.settingsHeader}>
        <span>WORKSPACE</span>
        <h1>Settings</h1>
        <p>Personalize the interface without changing your workflow data.</p>
      </header>

      <section className={appStyles.settingsCard}>
        <div className={appStyles.settingsIcon} aria-hidden="true">{theme === 'light' ? '☀' : '◐'}</div>
        <div className={appStyles.settingsCopy}>
          <h2>Appearance</h2>
          <p>Choose a clear light workspace or the focused dark workspace. Your choice is saved locally.</p>
        </div>
        <button type="button" className={appStyles.themeChoice} onClick={onToggleTheme}>
          <span>{theme === 'light' ? 'Light mode' : 'Dark mode'}</span>
          <strong>Switch to {theme === 'light' ? 'dark' : 'light'}</strong>
        </button>
      </section>
    </div>
  );
}
