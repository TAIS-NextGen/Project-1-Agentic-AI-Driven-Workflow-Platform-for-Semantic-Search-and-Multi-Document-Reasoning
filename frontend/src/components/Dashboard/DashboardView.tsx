import { useState } from 'react';
import { useWorkflowStore } from '../../store/workflowStore';
import type { AppRoute, Workflow } from '../../types';
import styles from './DashboardView.module.css';

interface DashboardViewProps {
  onNavigate: (route: AppRoute) => void;
}

const mockWorkflows: Workflow[] = [
  {
    id: 'wf-1',
    name: 'Invoice Processing Pipeline',
    description: 'Process invoices with EasyOCR, categorize, and extract details with LLM model.',
    nodeCount: 9,
    runCount: 142,
    lastRunAt: '2 hours ago',
    createdAt: '2026-06-15T12:00:00Z',
    updatedAt: '2026-07-13T16:00:00Z',
  },
  {
    id: 'wf-2',
    name: 'Contract Classifier',
    description: 'Ingest PDF agreements and classify clause sections for legal assessment.',
    nodeCount: 6,
    runCount: 38,
    lastRunAt: 'Running now',
    createdAt: '2026-06-20T10:00:00Z',
    updatedAt: '2026-07-13T17:30:00Z',
  },
  {
    id: 'wf-3',
    name: 'Medical Records OCR',
    description: 'Scan patient records, denoise images, and perform handwriting recognition.',
    nodeCount: 11,
    runCount: 67,
    lastRunAt: '1 day ago',
    createdAt: '2026-06-22T08:00:00Z',
    updatedAt: '2026-07-12T18:00:00Z',
  },
  {
    id: 'wf-4',
    name: 'Legal Doc Extractor',
    description: 'Parse multi-document PDFs, index chunks into vector database.',
    nodeCount: 8,
    runCount: 91,
    lastRunAt: '3 days ago',
    createdAt: '2026-06-01T09:00:00Z',
    updatedAt: '2026-07-10T14:00:00Z',
  },
  {
    id: 'wf-5',
    name: 'Financial Reports RAG',
    description: 'Execute semantic queries over uploaded financial spreadsheets.',
    nodeCount: 7,
    runCount: 24,
    lastRunAt: '5 days ago',
    createdAt: '2026-07-01T15:00:00Z',
    updatedAt: '2026-07-08T10:00:00Z',
  },
  {
    id: 'wf-6',
    name: 'HR Document Parser',
    description: 'Process resumes and load results into database structure.',
    nodeCount: 5,
    runCount: 55,
    lastRunAt: '1 week ago',
    createdAt: '2026-05-20T11:00:00Z',
    updatedAt: '2026-07-06T09:00:00Z',
  },
];

export function DashboardView({ onNavigate }: DashboardViewProps) {
  const [search, setSearch] = useState('');
  const setActiveWorkflow = useWorkflowStore((state) => state.setActiveWorkflow);
  const createWorkflow = useWorkflowStore((state) => state.createWorkflow);

  const handleCreateNew = () => {
    createWorkflow();
    onNavigate('workflows');
  };

  const handleSelectWorkflow = (wf: Workflow) => {
    setActiveWorkflow(wf.id);
    if (wf.lastRunAt === 'Running now') {
      onNavigate('executions');
    } else {
      onNavigate('workflows');
    }
  };

  const filtered = mockWorkflows.filter((w) =>
    w.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Dashboard</h1>
          <p className={styles.subtitle}>Welcome back, Alex. Monitor and manage your agentic pipelines.</p>
        </div>
        <div className={styles.searchBar}>
          <svg className={styles.searchIcon} width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M7.33333 12.6667C10.2819 12.6667 12.6667 10.2819 12.6667 7.33333C12.6667 4.38481 10.2819 2 7.33333 2C4.38481 2 2 4.38481 2 7.33333C2 10.2819 4.38481 12.6667 7.33333 12.6667Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M14 14L11.1 11.1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <input
            type="text"
            placeholder="Search workflows, logs, files... (⌘K)"
            className={styles.searchInput}
          />
        </div>
      </header>

      {/* Grid for Statistics */}
      <section className={styles.statsGrid}>
        <div className="glass-card">
          <div className={styles.statContent}>
            <div>
              <p className={styles.statLabel}>Documents Processed</p>
              <h3 className={styles.statVal}>12,489</h3>
              <span className={`${styles.trend} ${styles.trendUp}`}>+8.2% this week</span>
            </div>
            <div className={`${styles.statIcon} ${styles.blueGlow}`}>📄</div>
          </div>
        </div>

        <div className="glass-card">
          <div className={styles.statContent}>
            <div>
              <p className={styles.statLabel}>Active Workflows</p>
              <h3 className={styles.statVal}>24</h3>
              <span className={styles.statSub}>3 running now</span>
            </div>
            <div className={`${styles.statIcon} ${styles.purpleGlow}`}>🔗</div>
          </div>
        </div>

        <div className="glass-card">
          <div className={styles.statContent}>
            <div>
              <p className={styles.statLabel}>Success Rate</p>
              <h3 className={styles.statVal}>96.4%</h3>
              <span className={`${styles.trend} ${styles.trendUp}`}>+1.2% vs last month</span>
            </div>
            <div className={`${styles.statIcon} ${styles.greenGlow}`}>✅</div>
          </div>
        </div>

        <div className="glass-card">
          <div className={styles.statContent}>
            <div>
              <p className={styles.statLabel}>Last Activity</p>
              <h3 className={styles.statVal}>2 min</h3>
              <span className={styles.statSub}>Invoice Pipeline run</span>
            </div>
            <div className={`${styles.statIcon} ${styles.orangeGlow}`}>📈</div>
          </div>
        </div>
      </section>

      {/* Quick Action buttons */}
      <div className={styles.actionRow}>
        <button onClick={handleCreateNew} className="btn-premium">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M7 2.5V11.5M2.5 7H11.5" strokeLinecap="round" />
          </svg>
          New Workflow
        </button>
        <button onClick={() => onNavigate('documents')} className="btn-secondary">
          Import Documents
        </button>
      </div>

      {/* Workflows Grid Section */}
      <section className={styles.workflowsSection}>
        <div className={styles.sectionHeader}>
          <h2>Workflows</h2>
          <div className={styles.searchFilterGroup}>
            <input
              type="text"
              placeholder="Search workflows..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className={styles.filterInput}
            />
            <button className="btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }}>Filter</button>
          </div>
        </div>

        <div className={styles.workflowsGrid}>
          {filtered.map((wf) => {
            const isRunning = wf.lastRunAt === 'Running now';
            const isFailed = wf.name.includes('Medical');
            const statusText = isRunning ? 'Running' : isFailed ? 'Error' : 'Success';
            const statusClass = isRunning
              ? styles.running
              : isFailed
              ? styles.failed
              : styles.success;

            return (
              <div
                key={wf.id}
                className={`glass-card ${styles.wfCard}`}
                onClick={() => handleSelectWorkflow(wf)}
              >
                <div className={styles.wfGraphPreview}>
                  {/* SVG mini network preview */}
                  <svg className={styles.miniGraph} width="100%" height="80px">
                    <circle cx="20" cy="40" r="4" fill="var(--cat-preprocessing)" />
                    <line x1="20" y1="40" x2="60" y2="40" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
                    
                    <circle cx="60" cy="40" r="4" fill="var(--cat-ocr)" />
                    <line x1="60" y1="40" x2="100" y2="25" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
                    <line x1="60" y1="40" x2="100" y2="55" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />

                    <circle cx="100" cy="25" r="4" fill="var(--cat-rag)" />
                    <circle cx="100" cy="55" r="4" fill="var(--cat-logic)" />
                    
                    <line x1="100" y1="25" x2="140" y2="40" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
                    <line x1="100" y1="55" x2="140" y2="40" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />

                    <circle cx="140" cy="40" r="4" fill="var(--cat-export)" />

                    {/* Glowing pulse if running */}
                    {isRunning && (
                      <circle cx="60" cy="40" r="8" fill="none" stroke="var(--cat-ocr)" strokeWidth="1.5" className={styles.pingGlow} />
                    )}
                  </svg>
                </div>

                <div className={styles.wfMeta}>
                  <div className={styles.wfMetaHeader}>
                    <h3 className={styles.wfName}>{wf.name}</h3>
                    <span className={`${styles.statusBadge} ${statusClass}`}>
                      <span className={styles.pulseDot}></span>
                      {statusText}
                    </span>
                  </div>
                  <p className={styles.wfDesc}>{wf.description}</p>
                  <div className={styles.wfDetails}>
                    <span>⛓️ {wf.nodeCount} nodes</span>
                    <span>▶️ {wf.runCount} runs</span>
                    <span>🕒 {wf.lastRunAt}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
