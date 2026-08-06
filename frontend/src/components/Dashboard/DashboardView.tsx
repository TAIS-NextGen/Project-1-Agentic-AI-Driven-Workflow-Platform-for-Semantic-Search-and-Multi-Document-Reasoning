import { useMemo, useState } from 'react';
import { useFlowStore } from '../../store/flowStore';
import { useWorkflowStore } from '../../store/workflowStore';
import type { AppRoute, Workflow } from '../../types';
import styles from './DashboardView.module.css';

interface DashboardViewProps {
  onNavigate: (route: AppRoute) => void;
}

function relativeDate(value?: string): string {
  if (!value) return 'Never';
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return 'Unknown';
  const seconds = Math.max(0, Math.floor((Date.now() - time) / 1000));
  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
}

export function DashboardView({ onNavigate }: DashboardViewProps) {
  const [search, setSearch] = useState('');
  const workflows = useWorkflowStore((state) => state.workflows);
  const setActiveWorkflow = useWorkflowStore((state) => state.setActiveWorkflow);
  const createWorkflow = useWorkflowStore((state) => state.createWorkflow);
  const resetFlow = useFlowStore((state) => state.resetFlow);

  const handleCreateNew = () => {
    resetFlow();
    createWorkflow();
    onNavigate('workflows');
  };

  const handleSelectWorkflow = (workflow: Workflow) => {
    setActiveWorkflow(workflow.id);
    onNavigate('workflows');
  };

  const filtered = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return workflows
      .filter((workflow) => !normalized || workflow.name.toLowerCase().includes(normalized))
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  }, [search, workflows]);

  const totalNodes = workflows.reduce((sum, workflow) => sum + workflow.nodeCount, 0);
  const totalRuns = workflows.reduce((sum, workflow) => sum + workflow.runCount, 0);
  const lastActivity = workflows
    .map((workflow) => workflow.lastRunAt || workflow.updatedAt)
    .sort()
    .at(-1);

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Dashboard</h1>
          <p className={styles.subtitle}>Your saved workflows and recent local activity.</p>
        </div>
        <div className={styles.searchBar}>
          <svg className={styles.searchIcon} width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M7.33333 12.6667C10.2819 12.6667 12.6667 10.2819 12.6667 7.33333C12.6667 4.38481 10.2819 2 7.33333 2C4.38481 2 2 4.38481 2 7.33333C2 10.2819 4.38481 12.6667 7.33333 12.6667Z" stroke="currentColor" strokeWidth="1.5" />
            <path d="M14 14L11.1 11.1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search saved workflows…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className={styles.searchInput}
          />
        </div>
      </header>

      <section className={styles.statsGrid}>
        <div className="glass-card"><div className={styles.statContent}><div><p className={styles.statLabel}>Saved Workflows</p><h3 className={styles.statVal}>{workflows.length}</h3><span className={styles.statSub}>Persistent in this browser</span></div><div className={`${styles.statIcon} ${styles.purpleGlow}`}>🔗</div></div></div>
        <div className="glass-card"><div className={styles.statContent}><div><p className={styles.statLabel}>Configured Nodes</p><h3 className={styles.statVal}>{totalNodes}</h3><span className={styles.statSub}>Across all workflows</span></div><div className={`${styles.statIcon} ${styles.blueGlow}`}>◫</div></div></div>
        <div className="glass-card"><div className={styles.statContent}><div><p className={styles.statLabel}>Workflow Runs</p><h3 className={styles.statVal}>{totalRuns}</h3><span className={styles.statSub}>Recorded executions</span></div><div className={`${styles.statIcon} ${styles.greenGlow}`}>▶</div></div></div>
        <div className="glass-card"><div className={styles.statContent}><div><p className={styles.statLabel}>Last Activity</p><h3 className={styles.statVal} style={{ fontSize: 18 }}>{relativeDate(lastActivity)}</h3><span className={styles.statSub}>Latest edit or execution</span></div><div className={`${styles.statIcon} ${styles.orangeGlow}`}>◷</div></div></div>
      </section>

      <div className={styles.actionRow}>
        <button onClick={handleCreateNew} className="btn-premium">＋ New empty workflow</button>
        <button onClick={() => onNavigate('documents')} className="btn-secondary">Import Documents</button>
        <button onClick={() => { setActiveWorkflow(null); onNavigate('workflows'); }} className="btn-secondary">View full history</button>
      </div>

      <section className={styles.workflowsSection}>
        <div className={styles.sectionHeader}>
          <h2>Recent workflows</h2>
          <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>{filtered.length} result{filtered.length === 1 ? '' : 's'}</span>
        </div>

        {!filtered.length ? (
          <div className="glass-card" style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 38, marginBottom: 12 }}>⌘</div>
            <h3 style={{ color: 'var(--text-main)', margin: '0 0 8px' }}>{workflows.length ? 'No matching workflow' : 'No workflow yet'}</h3>
            <p style={{ margin: '0 0 18px' }}>{workflows.length ? 'Change the search text.' : 'Create a blank workflow and build it node by node.'}</p>
            {!workflows.length && <button className="btn-premium" onClick={handleCreateNew}>Create workflow</button>}
          </div>
        ) : (
          <div className={styles.workflowsGrid}>
            {filtered.slice(0, 6).map((workflow) => (
              <div key={workflow.id} className={`glass-card ${styles.wfCard}`} onClick={() => handleSelectWorkflow(workflow)}>
                <div className={styles.wfGraphPreview}>
                  <svg className={styles.miniGraph} width="100%" height="80px">
                    {workflow.nodes.slice(0, 5).map((node, index) => (
                      <circle key={node.id} cx={24 + index * 30} cy={40 + (index % 2 ? 12 : -8)} r="5" fill={index % 2 ? 'var(--cat-rag)' : 'var(--cat-preprocessing)'} />
                    ))}
                    {workflow.nodes.length === 0 && <text x="50%" y="50%" textAnchor="middle" fill="rgba(255,255,255,.28)" fontSize="10">EMPTY WORKFLOW</text>}
                  </svg>
                </div>
                <div className={styles.wfMeta}>
                  <div className={styles.wfMetaHeader}>
                    <h3 className={styles.wfName}>{workflow.name}</h3>
                    <span className={`${styles.statusBadge} ${styles.success}`}><span className={styles.pulseDot}></span>Saved</span>
                  </div>
                  <p className={styles.wfDesc}>{workflow.description || 'Custom document workflow'}</p>
                  <div className={styles.wfDetails}>
                    <span>⛓️ {workflow.nodeCount} nodes</span>
                    <span>▶️ {workflow.runCount} runs</span>
                    <span>🕒 {relativeDate(workflow.updatedAt)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
