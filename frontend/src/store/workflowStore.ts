import { create } from 'zustand';

import type { Workflow } from '../types';
import { generateId } from '../utils/idGenerator';

interface WorkflowStore {
  workflows: Workflow[];
  activeWorkflowId: string | null;
  createWorkflow: () => string;
  setActiveWorkflow: (id: string | null) => void;
}

const now = () => new Date().toISOString();

export const useWorkflowStore = create<WorkflowStore>((set) => ({
  workflows: [],
  activeWorkflowId: null,

  createWorkflow: () => {
    const id = generateId('wf');
    const timestamp = now();
    const workflow: Workflow = {
      id,
      name: 'Untitled Workflow',
      nodeCount: 0,
      runCount: 0,
      createdAt: timestamp,
      updatedAt: timestamp,
    };

    set((state) => ({
      workflows: [workflow, ...state.workflows],
      activeWorkflowId: id,
    }));

    return id;
  },

  setActiveWorkflow: (id) => {
    set({ activeWorkflowId: id });
  },
}));
