import { useState, useRef, useEffect } from 'react';
import { useExecutionStore } from '../../store/executionStore';
import { useFlowStore } from '../../store/flowStore';
import { NODE_DEFINITIONS } from '../../config/nodeDefinitions';
import styles from './ExecutionView.module.css';

type LogFilter = 'all' | 'error' | 'warn';

export function ExecutionView() {
  const {
    activeRun,
    runs,
    logs,
    elapsedSeconds,
    progress,
    isRunning,
    cancelExecution,
  } = useExecutionStore();

  const { nodes } = useFlowStore();
  const [logFilter, setLogFilter] = useState<LogFilter>('all');
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Auto scroll logs to bottom
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const filteredLogs = logs.filter((l) => {
    if (logFilter === 'all') return true;
    return l.level === logFilter;
  });

  const formatElapsed = (seconds: number) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const currentRunDisplay = activeRun || runs[0];

  return (
    <div className={styles.container}>
      {/* Left Panel: Canvas execution overview */}
      <div className={styles.leftPanel}>
        {/* Top bar for run status */}
        {isRunning && (
          <div className={styles.runStatusBar}>
            <span className={`${styles.statusDot} ${styles.running}`}></span>
            <span className={styles.statusLabel}>Running</span>
            <span className={styles.elapsed}>⏱ {formatElapsed(elapsedSeconds)} elapsed</span>
            <div className={styles.progressTrack}>
              <div className={styles.progressFill} style={{ width: `${progress}%` }}></div>
            </div>
            <span className={styles.progressPct}>{progress}%</span>
            <button onClick={cancelExecution} className={styles.cancelBtn}>
              Cancel Run
            </button>
          </div>
        )}

        {!isRunning && currentRunDisplay && (
          <div className={styles.runStatusBar}>
            <span className={`${styles.statusDot} ${styles[currentRunDisplay.status]}`}></span>
            <span className={styles.statusLabel}>{currentRunDisplay.status}</span>
            <span className={styles.elapsed}>
              {currentRunDisplay.workflowName}
            </span>
            <div className={styles.progressTrack}>
              <div
                className={`${styles.progressFill} ${currentRunDisplay.status === 'failed' ? styles.progressFailed : ''}`}
                style={{ width: '100%' }}
              ></div>
            </div>
          </div>
        )}

        {/* Node status list */}
        <div className={styles.nodeStatusPanel}>
          <h3>Node Status</h3>
          <div className={styles.nodeStatusList}>
            {nodes.map((node) => {
              const def = NODE_DEFINITIONS.find((d) => d.type === node.type);
              const statusClass =
                node.status === 'success'
                  ? styles.success
                  : node.status === 'running'
                  ? styles.running
                  : node.status === 'error'
                  ? styles.error
                  : styles.idle;

              return (
                <div key={node.id} className={styles.nodeStatusRow}>
                  <span className={`${styles.nodeDot} ${statusClass}`}></span>
                  <span className={styles.nodeStatusName}>
                    {def?.icon} {def?.name || node.type}
                  </span>
                  <span className={`${styles.nodeStatusText} ${statusClass}`}>
                    {node.status}
                  </span>
                  {node.status === 'running' && (
                    <span className={styles.runningSpinner}>⏳</span>
                  )}
                </div>
              );
            })}
            {nodes.length === 0 && (
              <p className={styles.emptyHint}>No nodes in canvas. Build a workflow first.</p>
            )}
          </div>
        </div>

        {/* Recent Runs history */}
        <div className={styles.runsHistory}>
          <h3>Recent Runs</h3>
          <div className={styles.runsList}>
            {runs.slice(0, 6).map((run) => (
              <div key={run.id} className={styles.runRow}>
                <span className={`${styles.runDot} ${styles[run.status]}`}></span>
                <div className={styles.runInfo}>
                  <span className={styles.runName}>{run.workflowName}</span>
                  <span className={styles.runId}>{run.id}</span>
                </div>
                <span className={`${styles.runStatus} ${styles[run.status]}`}>
                  {run.status}
                </span>
              </div>
            ))}
            {runs.length === 0 && (
              <p className={styles.emptyHint}>No execution history yet.</p>
            )}
          </div>
        </div>
      </div>

      {/* Right Panel: Execution logs */}
      <div className={styles.rightPanel}>
        <div className={styles.logsHeader}>
          <h3>Execution Logs</h3>
          <div className={styles.logFilterGroup}>
            {(['all', 'error', 'warn'] as LogFilter[]).map((f) => (
              <button
                key={f}
                onClick={() => setLogFilter(f)}
                className={`${styles.filterBtn} ${logFilter === f ? styles.filterBtnActive : ''}`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.logsBody}>
          {filteredLogs.length === 0 && !isRunning && (
            <div className={styles.emptyLogs}>
              <span>🔍</span>
              <p>No logs yet. Run a workflow to see execution output.</p>
            </div>
          )}
          {filteredLogs.map((log) => (
            <div
              key={log.id}
              className={`${styles.logEntry} ${styles[`log_${log.level}`]}`}
            >
              <span className={styles.logTime}>{log.timestamp}</span>
              <span className={styles.logNode}>{log.nodeName}</span>
              <span className={styles.logMsg}>{log.message}</span>
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  );
}
