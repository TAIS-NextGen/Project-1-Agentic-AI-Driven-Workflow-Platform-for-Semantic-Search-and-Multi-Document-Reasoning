import { create } from 'zustand';

import { getNodeDefinition } from '../config/nodeDefinitions';
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
  executionResults: Record<string, any> | null;

  startExecution: (workflowId: string, workflowName: string) => Promise<void>;
  cancelExecution: () => void;
  clearLogs: () => void;
  addLog: (level: 'info' | 'warn' | 'error', nodeName: string, message: string) => void;
}

let timerInterval: number | null = null;
let activeAbortController: AbortController | null = null;

function clearExecutionResources() {
  if (timerInterval !== null) {
    window.clearInterval(timerInterval);
    timerInterval = null;
  }
  activeAbortController = null;
}

function portsAreCompatible(sourceType?: string, targetType?: string) {
  if (!sourceType || !targetType || sourceType === 'any' || targetType === 'any') return true;
  const compatibility: Record<string, string[]> = {
    document: ['document', 'document[]', 'image', 'any'],
    'document[]': ['document[]', 'any'],
    image: ['image', 'document', 'any'],
    text: ['text', 'chunks', 'any'],
    chunks: ['chunks', 'text', 'any'],
    json: ['json', 'any'],
    embedding: ['embedding', 'any'],
    table: ['table', 'any'],
    corpus: ['corpus', 'any'],
  };
  return (compatibility[sourceType] || [sourceType, 'any']).includes(targetType);
}

function resolvePorts(
  sourceType: string | undefined,
  targetType: string | undefined,
  sourcePort?: string,
  targetPort?: string,
) {
  const sourceDefinition = sourceType ? getNodeDefinition(sourceType) : undefined;
  const targetDefinition = targetType ? getNodeDefinition(targetType) : undefined;
  const sourceOutputs = sourceDefinition?.outputs || [];
  const targetInputs = targetDefinition?.inputs || [];

  const explicitSource = sourcePort && sourcePort !== 'output' ? sourcePort : undefined;
  const explicitTarget = targetPort && targetPort !== 'input' ? targetPort : undefined;

  const outputPriority = [
    'corpus',
    'documents',
    'document',
    'cleaned_document',
    'converted_path',
    'converted_file',
    'image',
    'text',
    'normalized_text',
    'chunks',
    'data',
    'output',
  ];
  const inputPriority = targetType === 'topic-clustering'
    ? ['corpus']
    : targetType === 'comparison-agent'
      ? ['original_document', 'revised_document']
      : targetType === 'document-parser'
      ? ['document']
      : targetType === 'masker'
        ? ['document', 'text']
        : ['text', 'document', 'image', 'chunks', 'data', 'input'];

  const orderedOutputs = [
    ...outputPriority.flatMap((name) => sourceOutputs.filter((port) => port.name === name)),
    ...sourceOutputs.filter((port) => !outputPriority.includes(port.name || '')),
  ];
  const orderedInputs = [
    ...inputPriority.flatMap((name) => targetInputs.filter((port) => port.name === name)),
    ...targetInputs.filter((port) => !inputPriority.includes(port.name || '')),
  ];

  let source = explicitSource
    ? sourceOutputs.find((port) => port.name === explicitSource)
    : undefined;
  let target = explicitTarget
    ? targetInputs.find((port) => port.name === explicitTarget)
    : undefined;

  if (source && !target) {
    target = orderedInputs.find((port) => portsAreCompatible(source?.type, port.type));
  } else if (target && !source) {
    source = orderedOutputs.find((port) => portsAreCompatible(port.type, target?.type));
  } else if (!source && !target) {
    for (const candidateSource of orderedOutputs) {
      const candidateTarget = orderedInputs.find((port) => portsAreCompatible(candidateSource.type, port.type));
      if (candidateTarget) {
        source = candidateSource;
        target = candidateTarget;
        break;
      }
    }
  }

  source ||= orderedOutputs[0];
  target ||= orderedInputs[0];

  // Backward-compatible fallbacks for static nodes that do not yet expose ports.
  let resolvedSourcePort = source?.name || explicitSource || sourcePort || 'output';
  let resolvedTargetPort = target?.name || explicitTarget || targetPort || 'input';

  if (!sourceOutputs.length) {
    if (sourceType === 'document-upload' || sourceType === 'document-input') resolvedSourcePort = 'document';
    else if (['denoising', 'image-denoise', 'contrast-enhancer'].includes(sourceType || '')) resolvedSourcePort = 'image';
    else if (sourceType === 'document-parser') resolvedSourcePort = 'text';
    else if (sourceType === 'date-normalizer') resolvedSourcePort = 'normalized_text';
    else if (sourceType === 'masker') resolvedSourcePort = 'document';
    else if (sourceType === 'corpus-input') resolvedSourcePort = 'corpus';
    else if (sourceType === 'topic-clustering') resolvedSourcePort = 'clusters';
    else if (sourceType === 'comparison-agent') resolvedSourcePort = 'comparison';
  }

  if (!targetInputs.length) {
    if (['denoising', 'image-denoise', 'contrast-enhancer'].includes(targetType || '')) resolvedTargetPort = 'image';
    else if (targetType === 'document-parser') resolvedTargetPort = 'document';
    else if (targetType === 'masker') resolvedTargetPort = 'document';
    else if (targetType === 'topic-clustering') resolvedTargetPort = 'corpus';
    else if (targetType === 'comparison-agent') resolvedTargetPort = explicitTarget || 'original_document';
    else if (['text-splitter', 'llm', 'classifier', 'date-normalizer'].includes(targetType || '')) resolvedTargetPort = 'text';
  }

  return { sourcePort: resolvedSourcePort, targetPort: resolvedTargetPort };
}

export const useExecutionStore = create<ExecutionStore>((set, get) => ({
  // No fake execution history: every row shown here comes from a real run in this session.
  runs: [],
  activeRun: null,
  logs: [],
  elapsedSeconds: 0,
  progress: 0,
  isRunning: false,
  executionResults: null,

  clearLogs: () => set({ logs: [] }),

  addLog: (level, nodeName, message) => {
    const newLog: LogEntry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
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
    const startedAtMs = Date.now();
    const run: ExecutionRun = {
      id: `run-${startedAtMs}`,
      workflowId,
      workflowName,
      status: 'running',
      startedAt: new Date(startedAtMs).toISOString(),
      durationMs: 0,
      nodeCount: currentNodes.length,
    };

    set({
      isRunning: true,
      elapsedSeconds: 0,
      progress: 5,
      logs: [],
      executionResults: null,
      activeRun: run,
    });

    timerInterval = window.setInterval(() => {
      set((state) => ({ elapsedSeconds: state.elapsedSeconds + 1 }));
    }, 1000);

    const failRun = (message: string) => {
      const durationMs = Date.now() - startedAtMs;
      get().addLog('error', 'System', message);
      const failedRun: ExecutionRun = { ...run, status: 'failed', durationMs };
      set((state) => ({
        isRunning: false,
        progress: 100,
        activeRun: failedRun,
        runs: [failedRun, ...state.runs],
      }));
      clearExecutionResources();
    };

    if (!currentNodes.length) {
      failRun('The workflow is empty. Add and configure at least one node before running it.');
      return;
    }

    const backendNodes = currentNodes
      .filter((node) => node.type !== 'output')
      .map((node) => {
        const definition = getNodeDefinition(node.type);
        return {
          id: node.id,
          type: definition?.backendType || node.type,
          config: node.config,
        };
      });

    if (!backendNodes.length) {
      failRun('The workflow contains no executable backend node.');
      return;
    }

    flowStore.setNodes(currentNodes.map((node) => ({ ...node, status: 'idle' })));
    get().addLog('info', 'System', `Starting real backend execution for “${workflowName}”.`);

    const backendEdges = currentEdges
      .filter((edge) => {
        const sourceNode = currentNodes.find((node) => node.id === edge.source);
        const targetNode = currentNodes.find((node) => node.id === edge.target);
        return sourceNode && targetNode && sourceNode.type !== 'output' && targetNode.type !== 'output';
      })
      .map((edge) => {
        const sourceNode = currentNodes.find((node) => node.id === edge.source);
        const targetNode = currentNodes.find((node) => node.id === edge.target);
        let targetPort = edge.targetPort;
        if (targetNode?.type === 'comparison-agent' && (!targetPort || targetPort === 'input')) {
          const incoming = currentEdges.filter((candidate) => candidate.target === edge.target);
          const ordinal = incoming.findIndex((candidate) => candidate.id === edge.id);
          targetPort = ordinal <= 0 ? 'original_document' : 'revised_document';
        }
        const ports = resolvePorts(sourceNode?.type, targetNode?.type, edge.sourcePort, targetPort);
        return {
          source: edge.source,
          source_port: ports.sourcePort,
          target: edge.target,
          target_port: ports.targetPort,
        };
      });

    activeAbortController = new AbortController();

    try {
      set({ progress: 20 });
      get().addLog('info', 'System', 'Sending the workflow to the backend on port 8000…');
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBaseUrl}/api/workflows/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: workflowId,
          nodes: backendNodes,
          edges: backendEdges,
          validate_mode: 'relaxed',
        }),
        signal: activeAbortController.signal,
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const detail = typeof payload?.detail === 'string'
          ? payload.detail
          : `Backend returned HTTP ${response.status}.`;
        throw new Error(detail);
      }

      const runResult = await response.json();
      const results = (runResult.results || {}) as Record<string, any>;
      const succeeded = runResult.status === 'completed';

      Object.entries(results).forEach(([nodeId, result]) => {
        const sourceNode = currentNodes.find((node) => node.id === nodeId);
        const label = sourceNode ? sourceNode.type.toUpperCase() : 'NODE';
        if (result.status === 'success') {
          get().addLog('info', label, `Completed in ${Number(result.duration_ms || 0).toFixed(1)} ms.`);
        } else {
          get().addLog('error', label, result.error || 'Node execution failed.');
        }
      });

      flowStore.setNodes(currentNodes.map((node) => {
        if (node.type === 'output') {
          const incomingEdge = currentEdges.find((edge) => edge.target === node.id);
          const sourceResult = incomingEdge ? results[incomingEdge.source] : null;
          return {
            ...node,
            status: sourceResult?.status === 'success' ? 'success' : 'error',
          };
        }
        const result = results[node.id];
        return {
          ...node,
          status: result?.status === 'success' ? 'success' : 'error',
        };
      }));

      const completedRun: ExecutionRun = {
        ...run,
        status: succeeded ? 'success' : 'failed',
        durationMs: Date.now() - startedAtMs,
      };
      get().addLog(
        succeeded ? 'info' : 'error',
        'System',
        succeeded ? 'Workflow completed successfully.' : 'The backend reported one or more failed nodes.',
      );
      set((state) => ({
        isRunning: false,
        progress: 100,
        activeRun: completedRun,
        runs: [completedRun, ...state.runs],
        executionResults: results,
      }));
      clearExecutionResources();
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        clearExecutionResources();
        return;
      }

      flowStore.setNodes(currentNodes.map((node) => (
        node.type === 'output' ? { ...node, status: 'idle' } : { ...node, status: 'error' }
      )));
      failRun(
        `Real execution failed: ${error instanceof Error ? error.message : String(error)}. `
        + 'No simulated result was generated. Verify that run.bat started the backend.',
      );
    }
  },

  cancelExecution: () => {
    if (activeAbortController) {
      activeAbortController.abort();
    }
    if (timerInterval !== null) {
      window.clearInterval(timerInterval);
      timerInterval = null;
    }
    activeAbortController = null;

    set((state) => {
      if (!state.isRunning || !state.activeRun) {
        return { isRunning: false, activeRun: null };
      }
      const cancelledRun: ExecutionRun = {
        ...state.activeRun,
        status: 'failed',
        durationMs: state.elapsedSeconds * 1000,
      };
      const log: LogEntry = {
        id: `${Date.now()}-cancel`,
        timestamp: new Date().toLocaleTimeString(),
        level: 'warn',
        nodeName: 'System',
        message: 'Execution cancelled by user.',
      };
      return {
        isRunning: false,
        activeRun: null,
        runs: [cancelledRun, ...state.runs],
        logs: [...state.logs, log],
      };
    });
  },
}));
