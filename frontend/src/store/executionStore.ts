import { create } from 'zustand';
import { useFlowStore } from './flowStore';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error';
  nodeName: string;
  message: string;
}

export interface ExecutionRun {
  id: string;
  workflowId: string;
  workflowName: string;
  status: 'running' | 'success' | 'failed' | 'idle';
  startedAt: string;
  durationMs: number;
  nodeCount: number;
}

interface ExecutionStore {
  runs: ExecutionRun[];
  activeRun: ExecutionRun | null;
  logs: LogEntry[];
  elapsedSeconds: number;
  progress: number;
  isRunning: boolean;
  
  // Actions
  startExecution: (workflowId: string, workflowName: string) => Promise<void>;
  cancelExecution: () => void;
  clearLogs: () => void;
  addLog: (level: 'info' | 'warn' | 'error', nodeName: string, message: string) => void;
}

const mockRuns: ExecutionRun[] = [
  {
    id: 'run-141',
    workflowId: 'wf-1',
    workflowName: 'Invoice Processing Pipeline',
    status: 'success',
    startedAt: new Date(Date.now() - 3600000 * 2).toISOString(), // 2 hours ago
    durationMs: 4200,
    nodeCount: 4,
  },
  {
    id: 'run-140',
    workflowId: 'wf-2',
    workflowName: 'Contract Classifier',
    status: 'running',
    startedAt: new Date(Date.now() - 60000).toISOString(),
    durationMs: 0,
    nodeCount: 6,
  },
  {
    id: 'run-139',
    workflowId: 'wf-3',
    workflowName: 'Medical Records OCR',
    status: 'failed',
    startedAt: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
    durationMs: 1800,
    nodeCount: 5,
  },
];

let timerInterval: number | null = null;
let simulationTimeout: number | null = null;

export const useExecutionStore = create<ExecutionStore>((set, get) => ({
  runs: mockRuns,
  activeRun: null,
  logs: [],
  elapsedSeconds: 0,
  progress: 0,
  isRunning: false,

  clearLogs: () => set({ logs: [] }),

  addLog: (level, nodeName, message) => {
    const newLog: LogEntry = {
      id: Math.random().toString(36).substring(7),
      timestamp: new Date().toLocaleTimeString(),
      level,
      nodeName,
      message,
    };
    set((state) => ({ logs: [...state.logs, newLog] }));
  },

  startExecution: async (workflowId, workflowName) => {
    // Clear previous execution state
    get().cancelExecution();
    set({
      isRunning: true,
      elapsedSeconds: 0,
      progress: 0,
      logs: [],
      activeRun: {
        id: `run-${Math.floor(Math.random() * 500) + 150}`,
        workflowId,
        workflowName,
        status: 'running',
        startedAt: new Date().toISOString(),
        durationMs: 0,
        nodeCount: useFlowStore.getState().nodes.length,
      },
    });

    // Start elapsed timer
    timerInterval = window.setInterval(() => {
      set((state) => ({ elapsedSeconds: state.elapsedSeconds + 1 }));
    }, 1000);

    // Get nodes from flowStore and reset their status to idle/running
    const flowStore = useFlowStore.getState();
    const nodes = flowStore.nodes;
    
    if (nodes.length === 0) {
      get().addLog('error', 'System', 'No nodes in the canvas to execute.');
      set({ isRunning: false });
      if (timerInterval) clearInterval(timerInterval);
      return;
    }

    // Set all nodes to idle
    flowStore.setNodes(nodes.map(n => ({ ...n, status: 'idle' })));
    get().addLog('info', 'System', `Starting execution for workflow: ${workflowName}`);

    // Simulated execution step-by-step
    let nodeIndex = 0;
    
    const executeNextNode = () => {
      const currentNodes = useFlowStore.getState().nodes;
      if (nodeIndex >= currentNodes.length) {
        // Finished
        get().addLog('info', 'System', 'Execution completed successfully.');
        set((state) => {
          if (state.activeRun) {
            const completedRun: ExecutionRun = {
              ...state.activeRun,
              status: 'success',
              durationMs: state.elapsedSeconds * 1000,
            };
            return {
              isRunning: false,
              progress: 100,
              activeRun: completedRun,
              runs: [completedRun, ...state.runs],
            };
          }
          return { isRunning: false, progress: 100 };
        });
        if (timerInterval) clearInterval(timerInterval);
        return;
      }

      const node = currentNodes[nodeIndex];
      
      // Animate node running
      flowStore.setNodes(
        currentNodes.map(n => n.id === node.id ? { ...n, status: 'running' } : n)
      );
      
      get().addLog('info', node.type.toUpperCase(), `Executing node: ${node.id} (${node.type})...`);
      set({ progress: Math.floor((nodeIndex / currentNodes.length) * 100) });

      // Simulate logic based on node type
      simulationTimeout = window.setTimeout(() => {
        const updateNodes = useFlowStore.getState().nodes;
        
        // Custom warning/error simulation
        let status: 'success' | 'error' = 'success';
        if (node.type === 'ocr' && Math.random() > 0.8) {
          get().addLog('warn', 'OCR', 'Low resolution image detected, fallback activated.');
        } else if (node.type === 'conditional' && node.config.expression === '') {
          get().addLog('error', 'CONDITIONAL', 'Expression is missing in conditional node!');
          status = 'error';
        }

        flowStore.setNodes(
          updateNodes.map(n => n.id === node.id ? { ...n, status } : n)
        );

        if (status === 'error') {
          get().addLog('error', 'System', 'Execution failed at node: ' + node.id);
          set((state) => {
            if (state.activeRun) {
              const failedRun: ExecutionRun = {
                ...state.activeRun,
                status: 'failed',
                durationMs: state.elapsedSeconds * 1000,
              };
              return {
                isRunning: false,
                activeRun: failedRun,
                runs: [failedRun, ...state.runs],
              };
            }
            return { isRunning: false };
          });
          if (timerInterval) clearInterval(timerInterval);
          return;
        }

        get().addLog('info', node.type.toUpperCase(), `Completed execution for node: ${node.id}`);
        nodeIndex++;
        executeNextNode();
      }, 1500); // Wait 1.5 seconds per node
    };

    executeNextNode();
  },

  cancelExecution: () => {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
    if (simulationTimeout) {
      clearTimeout(simulationTimeout);
      simulationTimeout = null;
    }

    set((state) => {
      if (state.isRunning && state.activeRun) {
        const cancelledRun: ExecutionRun = {
          ...state.activeRun,
          status: 'failed',
          durationMs: state.elapsedSeconds * 1000,
        };
        get().addLog('warn', 'System', 'Execution cancelled by user.');
        return {
          isRunning: false,
          activeRun: null,
          runs: [cancelledRun, ...state.runs],
        };
      }
      return { isRunning: false, activeRun: null };
    });
  },
}));
