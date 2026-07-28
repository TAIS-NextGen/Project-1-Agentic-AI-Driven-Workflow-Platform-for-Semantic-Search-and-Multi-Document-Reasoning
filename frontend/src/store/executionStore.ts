import { create } from 'zustand';
import { useFlowStore } from './flowStore';
import { getNodeDefinition } from '../config/nodeDefinitions';

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
  executionResults: Record<string, any> | null;

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
    startedAt: new Date(Date.now() - 3600000 * 2).toISOString(),
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
    startedAt: new Date(Date.now() - 86400000).toISOString(),
    durationMs: 1800,
    nodeCount: 5,
  },
];

const MOCK_SVG = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIzMDAiIGhlaWdodD0iMjAwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMWUyOTNiIi8+PHRleHQgeD0iNTAlIiB5PSI0NSUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtZmFtaWx5PSJzYW5zLXNlcmlmIiBmb250LXNpemU9IjE2IiBmaWxsPSIjMTBiOTgxIiBmb250LXdlaWdodD0iYm9sZCI+RGVub2lzZWQgRG9jdW1lbnQgUHJldmlldzwvdGV4dD48dGV4dCB4PSI1MCUiIHk9IjYwJSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1mYW1pbHk9InNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTEiIGZpbGw9IiM5NGEzYjgiPkNsZWFuZWQgaW1hZ2UgZ2VuZXJhdGVkIHN1Y2Nlc3NmdWxseS48L3RleHQ+PC9zdmc+';

const mockExecutionResults = (nodes: any[]) => {
  const results: Record<string, any> = {};
  nodes.forEach(node => {
    if (node.type === 'denoising' || node.type === 'image-denoise') {
      results[node.id] = {
        status: 'success',
        outputs: {
          image: {
            filename: 'denoised_document.png',
            path: MOCK_SVG,
            size_bytes: 45201,
            mime_type: 'image/png'
          },
          metadata: {
            denoise_method: node.config.method || 'pil-median',
            input_format: '.png'
          }
        }
      };
    } else if (node.type === 'document-upload') {
      results[node.id] = {
        status: 'success',
        outputs: {
          document: {
            filename: node.config.filename || 'uploaded_document.png',
            path: MOCK_SVG,
            size_bytes: 52104,
            mime_type: 'image/png'
          }
        }
      };
    } else if (node.type === 'ocr-node') {
      results[node.id] = {
        status: 'success',
        outputs: {
          text: "INVOICE #INV-2026-001\nDate: 2026-07-15\nAmount Due: $1,250.00\nVAT: $250.00",
          confidence: 0.94
        }
      };
    } else {
      results[node.id] = {
        status: 'success',
        outputs: {
          output: "Mock output for node " + node.id
        }
      };
    }
  });
  return results;
};

let timerInterval: number | null = null;
let simulationTimeout: number | null = null;

export const useExecutionStore = create<ExecutionStore>((set, get) => ({
  runs: mockRuns,
  activeRun: null,
  logs: [],
  elapsedSeconds: 0,
  progress: 0,
  isRunning: false,
  executionResults: null,

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
    get().cancelExecution();
    const flowStore = useFlowStore.getState();
    const currentNodes = flowStore.nodes;
    const currentEdges = flowStore.edges;

    set({
      isRunning: true,
      elapsedSeconds: 0,
      progress: 0,
      logs: [],
      executionResults: null,
      activeRun: {
        id: `run-${Math.floor(Math.random() * 500) + 150}`,
        workflowId,
        workflowName,
        status: 'running',
        startedAt: new Date().toISOString(),
        durationMs: 0,
        nodeCount: currentNodes.length,
      },
    });

    timerInterval = window.setInterval(() => {
      set((state) => ({ elapsedSeconds: state.elapsedSeconds + 1 }));
    }, 1000);

    if (currentNodes.length === 0) {
      get().addLog('error', 'System', 'No nodes in the canvas to execute.');
      set({ isRunning: false });
      if (timerInterval) clearInterval(timerInterval);
      return;
    }

    flowStore.setNodes(currentNodes.map(n => ({ ...n, status: 'idle' })));
    get().addLog('info', 'System', `Starting execution for workflow: ${workflowName}`);

    const backendNodes = currentNodes
      .filter(n => n.type !== 'output')
      .map(n => {
        const definition = getNodeDefinition(n.type);
        const backendType = definition?.backendType || n.type;
        return {
          id: n.id,
          type: backendType,
          config: n.config,
        };
      });

    const backendEdges = currentEdges
      .filter(e => {
        const sourceNode = currentNodes.find(n => n.id === e.source);
        const targetNode = currentNodes.find(n => n.id === e.target);
        return sourceNode && targetNode && sourceNode.type !== 'output' && targetNode.type !== 'output';
      })
      .map(e => {
        const sourceNode = currentNodes.find(n => n.id === e.source);
        const targetNode = currentNodes.find(n => n.id === e.target);
        let sourcePort = e.sourcePort || 'output';
        let targetPort = e.targetPort || 'input';

        if (sourceNode?.type === 'document-upload') {
          sourcePort = 'document';
        } else if (sourceNode?.type === 'denoising' || sourceNode?.type === 'image-denoise') {
          sourcePort = 'image';
        } else if (sourceNode?.type === 'handwriting-ocr') {
          sourcePort = 'text';
        } else if (sourceNode?.type === 'regex-extractor') {
          sourcePort = 'extracted';
        } else if (sourceNode?.type === 'semantic-extractor') {
          sourcePort = 'extracted';
        } else if (sourceNode?.type === 'document-structure-analyzer') {
          sourcePort = 'structure';
        } else if (sourceNode?.type === 'gap-checker') {
          sourcePort = 'report';
        } else if (sourceNode?.type === 'ocr-node') {
          sourcePort = 'text';
        }

        if (targetNode?.type === 'document-upload') {
          targetPort = 'file';
        } else if (targetNode?.type === 'denoising' || targetNode?.type === 'image-denoise') {
          targetPort = 'image';
        } else if (targetNode?.type === 'handwriting-ocr') {
          targetPort = 'image';
        } else if (targetNode?.type === 'regex-extractor') {
          targetPort = 'text';
        } else if (targetNode?.type === 'semantic-extractor') {
          targetPort = 'text';
        } else if (targetNode?.type === 'document-structure-analyzer') {
          targetPort = 'document';
        } else if (targetNode?.type === 'gap-checker') {
          targetPort = 'text';
        } else if (targetNode?.type === 'ocr-node') {
          targetPort = 'document';
        }

        return {
          source: e.source,
          source_port: sourcePort,
          target: e.target,
          target_port: targetPort,
        };
      });

    try {
      get().addLog('info', 'System', 'Connecting to backend service...');
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

      const payload = {
        id: workflowId,
        nodes: backendNodes,
        edges: backendEdges,
      };

      const response = await fetch(`${API_BASE_URL}/api/workflows/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errPayload = await response.json().catch(() => ({}));
        throw new Error(errPayload.detail || `Server returned ${response.status}`);
      }

      const runResult = await response.json();
      const isSuccess = runResult.status === 'completed';

      Object.entries(runResult.results).forEach(([nodeId, res]: [string, any]) => {
        const node = currentNodes.find(n => n.id === nodeId);
        const nodeName = node ? node.type.toUpperCase() : 'NODE';
        if (res.status === 'success') {
          get().addLog('info', nodeName, `Successfully executed in ${res.duration_ms?.toFixed(1) || 0}ms.`);
        } else {
          get().addLog('error', nodeName, `Failed: ${res.error}`);
        }
      });

      flowStore.setNodes(
        currentNodes.map(n => {
          if (n.type === 'output') {
            const incomingEdge = currentEdges.find(e => e.target === n.id);
            const sourceResult = incomingEdge ? runResult.results[incomingEdge.source] : null;
            return {
              ...n,
              status: sourceResult ? (sourceResult.status === 'success' ? 'success' : 'error') : 'success',
            };
          }
          const res = runResult.results[n.id];
          return {
            ...n,
            status: res ? (res.status === 'success' ? 'success' : 'error') : 'idle',
          };
        })
      );

      if (isSuccess) {
        get().addLog('info', 'System', 'Execution completed successfully.');
      } else {
        get().addLog('error', 'System', 'Execution failed at one or more nodes.');
      }

      set((state) => {
        const completedRun: ExecutionRun = {
          ...state.activeRun!,
          status: isSuccess ? 'success' : 'failed',
          durationMs: state.elapsedSeconds * 1000,
        };
        return {
          isRunning: false,
          progress: 100,
          activeRun: completedRun,
          runs: [completedRun, ...state.runs],
          executionResults: runResult.results,
        };
      });

      if (timerInterval) clearInterval(timerInterval);

    } catch (error) {
      get().addLog('warn', 'System', `Backend connection failed: ${error instanceof Error ? error.message : String(error)}`);
      get().addLog('info', 'System', 'Running workflow in offline simulated mode...');

      let nodeIndex = 0;
      const executeNextNode = () => {
        const flowNodes = useFlowStore.getState().nodes;
        if (nodeIndex >= flowNodes.length) {
          get().addLog('info', 'System', 'Simulated execution completed successfully.');
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
                executionResults: mockExecutionResults(flowNodes),
              };
            }
            return { isRunning: false, progress: 100 };
          });
          if (timerInterval) clearInterval(timerInterval);
          return;
        }

        const node = flowNodes[nodeIndex];
        flowStore.setNodes(
          flowNodes.map(n => n.id === node.id ? { ...n, status: 'running' } : n)
        );

        get().addLog('info', node.type.toUpperCase(), `Executing node: ${node.id} (${node.type})...`);
        set({ progress: Math.floor((nodeIndex / flowNodes.length) * 100) });

        simulationTimeout = window.setTimeout(() => {
          const updateNodes = useFlowStore.getState().nodes;
          let status: 'success' | 'error' = 'success';

          if (node.type === 'ocr-node' && Math.random() > 0.8) {
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
        }, 1500);
      };

      executeNextNode();
    }
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