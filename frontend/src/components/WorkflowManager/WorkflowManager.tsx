import { useMemo, useState } from 'react';

import { useFlowStore } from '../../store/flowStore';
import { useWorkflowStore } from '../../store/workflowStore';
import type { Workflow } from '../../types';
import styles from './WorkflowManager.module.css';

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function WorkflowManager() {
  const [search, setSearch] = useState('');
  const workflows = useWorkflowStore((state) => state.workflows);
  const createWorkflow = useWorkflowStore((state) => state.createWorkflow);
  const setActiveWorkflow = useWorkflowStore((state) => state.setActiveWorkflow);
  const deleteWorkflow = useWorkflowStore((state) => state.deleteWorkflow);
  const duplicateWorkflow = useWorkflowStore((state) => state.duplicateWorkflow);
  const resetFlow = useFlowStore((state) => state.resetFlow);

  const filtered = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return workflows
      .filter((workflow) => !normalized || workflow.name.toLowerCase().includes(normalized))
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  }, [search, workflows]);

  const handleCreate = () => {
    resetFlow();
    createWorkflow();
  };

  const handleOpen = (workflow: Workflow) => {
    setActiveWorkflow(workflow.id);
  };

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>WORKSPACE</span>
          <h1>Workflow history</h1>
          <p>Create a pipeline from scratch or reopen any workflow saved in this browser.</p>
        </div>
        <button className="btn-premium" onClick={handleCreate}>＋ New empty workflow</button>
      </header>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <span>⌕</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search saved workflows…"
          />
        </div>
        <span>{workflows.length} saved workflow{workflows.length === 1 ? '' : 's'}</span>
      </div>

      {!filtered.length ? (
        <div className={styles.emptyState}>
          <div>⌘</div>
          <h2>{workflows.length ? 'No matching workflow' : 'No workflow created yet'}</h2>
          <p>{workflows.length ? 'Try another search.' : 'Start with a blank canvas and add only the nodes you need.'}</p>
          {!workflows.length && <button className="btn-premium" onClick={handleCreate}>Create the first workflow</button>}
        </div>
      ) : (
        <div className={styles.grid}>
          {filtered.map((workflow) => (
            <article key={workflow.id} className={styles.card} onClick={() => handleOpen(workflow)}>
              <div className={styles.preview}>
                {workflow.nodes.length ? workflow.nodes.slice(0, 8).map((node, index) => (
                  <span
                    key={node.id}
                    style={{ left: `${12 + (index % 4) * 24}%`, top: `${26 + Math.floor(index / 4) * 38}%` }}
                  />
                )) : <strong>EMPTY</strong>}
              </div>
              <div className={styles.cardBody}>
                <div className={styles.cardTitleRow}>
                  <h2>{workflow.name}</h2>
                  <span>{workflow.nodeCount} nodes</span>
                </div>
                <p>{workflow.description || 'Custom document workflow'}</p>
                <div className={styles.meta}>
                  <span>Updated {formatDate(workflow.updatedAt)}</span>
                  <span>{workflow.runCount} run{workflow.runCount === 1 ? '' : 's'}</span>
                </div>
                <div className={styles.actions} onClick={(event) => event.stopPropagation()}>
                  <button onClick={() => handleOpen(workflow)}>Open</button>
                  <button onClick={() => duplicateWorkflow(workflow.id)}>Duplicate</button>
                  <button
                    className={styles.deleteButton}
                    onClick={() => {
                      if (window.confirm(`Delete “${workflow.name}”?`)) deleteWorkflow(workflow.id);
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
