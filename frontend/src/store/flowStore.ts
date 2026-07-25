import { create } from 'zustand';

import type { FlowEdge, FlowNode } from '../types';
import { generateId } from '../utils/idGenerator';

interface FlowStore {
  nodes: FlowNode[];
  edges: FlowEdge[];
  selectedNodeId: string | null;
  viewport: { x: number; y: number; zoom: number };
  
  // Actions
  setNodes: (nodes: FlowNode[]) => void;
  setEdges: (edges: FlowEdge[]) => void;
  addNode: (type: string, position?: { x: number; y: number }) => string;
  updateNodePosition: (id: string, x: number, y: number) => void;
  updateNodeConfig: (id: string, config: Record<string, unknown>) => void;
  deleteNode: (id: string) => void;
  selectNode: (id: string | null) => void;
  
  connectNodes: (sourceId: string, targetId: string) => void;
  deleteEdge: (id: string) => void;
  
  setViewport: (viewport: { x: number; y: number; zoom: number }) => void;
  resetFlow: () => void;
  loadTemplate: (templateName: string) => void;
}

const DEFAULT_NODES: FlowNode[] = [
  {
    id: 'node-1',
    type: 'document-input',
    position: { x: 100, y: 200 },
    config: {},
    status: 'success',
  },
  {
    id: 'node-2',
    type: 'ocr',
    position: { x: 300, y: 200 },
    config: { language: 'en' },
    status: 'ready',
  },
  {
    id: 'node-3',
    type: 'text-splitter',
    position: { x: 500, y: 120 },
    config: { chunkSize: 512, overlap: 50 },
    status: 'idle',
  },
  {
    id: 'node-4',
    type: 'embedding',
    position: { x: 700, y: 120 },
    config: { model: 'text-embedding-3-small' },
    status: 'idle',
  },
  {
    id: 'node-5',
    type: 'vector-store',
    position: { x: 900, y: 120 },
    config: { collection: 'contracts-library' },
    status: 'idle',
  },
  {
    id: 'node-6',
    type: 'conditional',
    position: { x: 500, y: 280 },
    config: { expression: 'has_handwriting == true' },
    status: 'idle',
  },
];

const DEFAULT_EDGES: FlowEdge[] = [
  { id: 'edge-1', source: 'node-1', target: 'node-2' },
  { id: 'edge-2', source: 'node-2', target: 'node-3' },
  { id: 'edge-3', source: 'node-3', target: 'node-4' },
  { id: 'edge-4', source: 'node-4', target: 'node-5' },
  { id: 'edge-5', source: 'node-2', target: 'node-6' },
];

export const useFlowStore = create<FlowStore>((set, get) => ({
  nodes: DEFAULT_NODES,
  edges: DEFAULT_EDGES,
  selectedNodeId: null,
  viewport: { x: 0, y: 0, zoom: 1 },

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  addNode: (type, position) => {
    const id = generateId('node');
    const newNode: FlowNode = {
      id,
      type,
      position: position || { x: 250, y: 200 },
      config: {},
      status: 'idle',
    };
    
    set((state) => ({
      nodes: [...state.nodes, newNode],
      selectedNodeId: id,
    }));
    
    return id;
  },

  updateNodePosition: (id, x, y) => {
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === id ? { ...node, position: { x, y } } : node
      ),
    }));
  },

  updateNodeConfig: (id, config) => {
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === id ? { ...node, config: { ...node.config, ...config } } : node
      ),
    }));
  },

  deleteNode: (id) => {
    set((state) => ({
      nodes: state.nodes.filter((node) => node.id !== id),
      edges: state.edges.filter((edge) => edge.source !== id && edge.target !== id),
      selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
    }));
  },

  selectNode: (id) => set({ selectedNodeId: id }),

  connectNodes: (sourceId, targetId) => {
    // Prevent duplicate edges or self loops
    const exists = get().edges.some(
      (edge) => edge.source === sourceId && edge.target === targetId
    );
    if (exists || sourceId === targetId) return;

    const newEdge: FlowEdge = {
      id: generateId('edge'),
      source: sourceId,
      target: targetId,
    };

    set((state) => ({
      edges: [...state.edges, newEdge],
    }));
  },

  deleteEdge: (id) => {
    set((state) => ({
      edges: state.edges.filter((edge) => edge.id !== id),
    }));
  },

  setViewport: (viewport) => set({ viewport }),

  resetFlow: () => {
    set({
      nodes: [],
      edges: [],
      selectedNodeId: null,
      viewport: { x: 0, y: 0, zoom: 1 },
    });
  },

  loadTemplate: (templateName) => {
    if (templateName === 'invoice') {
      set({
        nodes: [
          {
            id: 'n1',
            type: 'document-input',
            position: { x: 100, y: 200 },
            config: {},
            status: 'success',
          },
          {
            id: 'n2',
            type: 'ocr',
            position: { x: 300, y: 200 },
            config: { language: 'fr' },
            status: 'success',
          },
          {
            id: 'n3',
            type: 'llm',
            position: { x: 520, y: 200 },
            config: { model: 'gpt-4o', prompt: 'Extract fields: invoice_number, amount_vat, date' },
            status: 'ready',
          },
          {
            id: 'n4',
            type: 'output',
            position: { x: 740, y: 200 },
            config: { format: 'json' },
            status: 'idle',
          },
        ],
        edges: [
          { id: 'e1', source: 'n1', target: 'n2' },
          { id: 'e2', source: 'n2', target: 'n3' },
          { id: 'e3', source: 'n3', target: 'n4' },
        ],
        selectedNodeId: null,
      });
    } else if (templateName === 'rag') {
      set({
        nodes: [
          {
            id: 'r1',
            type: 'document-input',
            position: { x: 100, y: 150 },
            config: {},
            status: 'success',
          },
          {
            id: 'r2',
            type: 'text-splitter',
            position: { x: 300, y: 150 },
            config: { chunkSize: 1000, overlap: 100 },
            status: 'ready',
          },
          {
            id: 'r3',
            type: 'embedding',
            position: { x: 500, y: 150 },
            config: { model: 'text-embedding-3-small' },
            status: 'idle',
          },
          {
            id: 'r4',
            type: 'vector-store',
            position: { x: 700, y: 150 },
            config: { collection: 'rag-docs' },
            status: 'idle',
          },
          {
            id: 'r5',
            type: 'rag',
            position: { x: 900, y: 250 },
            config: { topK: 3 },
            status: 'idle',
          },
        ],
        edges: [
          { id: 'er1', source: 'r1', target: 'r2' },
          { id: 'er2', source: 'r2', target: 'r3' },
          { id: 'er3', source: 'r3', target: 'r4' },
          { id: 'er4', source: 'r4', target: 'r5' },
        ],
        selectedNodeId: null,
      });
    }
  },
}));
