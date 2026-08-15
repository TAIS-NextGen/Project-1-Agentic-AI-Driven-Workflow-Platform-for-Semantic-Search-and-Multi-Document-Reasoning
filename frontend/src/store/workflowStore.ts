import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import type { FlowEdge, FlowNode, Workflow, WorkflowViewport } from '../types';
import { generateId } from '../utils/idGenerator';

interface SaveWorkflowPayload {
  nodes: FlowNode[];
  edges: FlowEdge[];
  viewport: WorkflowViewport;
}

interface WorkflowStore {
  workflows: Workflow[];
  activeWorkflowId: string | null;
  createWorkflow: (name?: string) => string;
  setActiveWorkflow: (id: string | null) => void;
  saveWorkflow: (id: string, payload: SaveWorkflowPayload) => void;
  renameWorkflow: (id: string, name: string) => void;
  deleteWorkflow: (id: string) => void;
  duplicateWorkflow: (id: string) => string | null;
  recordRun: (id: string) => void;
}

const now = () => new Date().toISOString();
const emptyViewport = (): WorkflowViewport => ({ x: 0, y: 0, zoom: 1 });

const cloneNodes = (nodes: FlowNode[] = []) => nodes.map((node) => ({
  ...node,
  position: { ...node.position },
  config: { ...node.config },
}));
const cloneEdges = (edges: FlowEdge[] = []) => edges.map((edge) => ({ ...edge }));

function nextUntitledName(workflows: Workflow[]): string {
  const used = new Set(workflows.map((workflow) => workflow.name));
  if (!used.has('New workflow')) return 'New workflow';
  let index = 2;
  while (used.has(`New workflow ${index}`)) index += 1;
  return `New workflow ${index}`;
}

export const useWorkflowStore = create<WorkflowStore>()(
  persist(
    (set, get) => ({
      workflows: [],
      activeWorkflowId: null,

      createWorkflow: (requestedName) => {
        const id = generateId('wf');
        const timestamp = now();
        const name = requestedName?.trim() || nextUntitledName(get().workflows);
        const workflow: Workflow = {
          id,
          name,
          description: 'Custom document workflow',
          nodeCount: 0,
          runCount: 0,
          createdAt: timestamp,
          updatedAt: timestamp,
          nodes: [],
          edges: [],
          viewport: emptyViewport(),
        };

        set((state) => ({
          workflows: [workflow, ...state.workflows],
          activeWorkflowId: id,
        }));
        return id;
      },

      setActiveWorkflow: (id) => set({ activeWorkflowId: id }),

      saveWorkflow: (id, payload) => set((state) => ({
        workflows: state.workflows.map((workflow) => (
          workflow.id === id
            ? {
                ...workflow,
                nodes: cloneNodes(payload.nodes),
                edges: cloneEdges(payload.edges),
                viewport: { ...payload.viewport },
                nodeCount: payload.nodes.length,
                updatedAt: now(),
              }
            : workflow
        )),
      })),

      renameWorkflow: (id, rawName) => {
        const name = rawName.trim();
        if (!name) return;
        set((state) => ({
          workflows: state.workflows.map((workflow) => (
            workflow.id === id ? { ...workflow, name, updatedAt: now() } : workflow
          )),
        }));
      },

      deleteWorkflow: (id) => set((state) => ({
        workflows: state.workflows.filter((workflow) => workflow.id !== id),
        activeWorkflowId: state.activeWorkflowId === id ? null : state.activeWorkflowId,
      })),

      duplicateWorkflow: (id) => {
        const source = get().workflows.find((workflow) => workflow.id === id);
        if (!source) return null;
        const duplicateId = generateId('wf');
        const timestamp = now();
        const duplicate: Workflow = {
          ...source,
          id: duplicateId,
          name: `${source.name} copy`,
          createdAt: timestamp,
          updatedAt: timestamp,
          runCount: 0,
          lastRunAt: undefined,
          nodes: cloneNodes(source.nodes),
          edges: cloneEdges(source.edges),
          viewport: { ...(source.viewport || emptyViewport()) },
        };
        set((state) => ({ workflows: [duplicate, ...state.workflows] }));
        return duplicateId;
      },

      recordRun: (id) => set((state) => ({
        workflows: state.workflows.map((workflow) => (
          workflow.id === id
            ? {
                ...workflow,
                runCount: workflow.runCount + 1,
                lastRunAt: now(),
                updatedAt: now(),
              }
            : workflow
        )),
      })),
    }),
    {
      name: 'flowdocs-workflow-history-v2',
      storage: createJSONStorage(() => localStorage),
      version: 2,
      migrate: (persistedState: unknown) => {
        const state = persistedState as Partial<WorkflowStore> | undefined;
        return {
          workflows: (state?.workflows || []).map((workflow) => ({
            ...workflow,
            nodes: cloneNodes(workflow.nodes || []),
            edges: cloneEdges(workflow.edges || []),
            viewport: workflow.viewport || emptyViewport(),
            nodeCount: workflow.nodes?.length ?? workflow.nodeCount ?? 0,
          })),
          activeWorkflowId: state?.activeWorkflowId || null,
        } as WorkflowStore;
      },
    },
  ),
);
