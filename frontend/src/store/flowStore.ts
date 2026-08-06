import { create } from 'zustand';

import type { FlowEdge, FlowNode } from '../types';
import { getNodeDefinition } from '../config/nodeDefinitions';
import { generateId } from '../utils/idGenerator';

export interface FlowViewport {
  x: number;
  y: number;
  zoom: number;
}

interface FlowStore {
  nodes: FlowNode[];
  edges: FlowEdge[];
  selectedNodeId: string | null;
  viewport: FlowViewport;

  setNodes: (nodes: FlowNode[]) => void;
  setEdges: (edges: FlowEdge[]) => void;
  loadFlow: (nodes: FlowNode[], edges: FlowEdge[], viewport?: FlowViewport) => void;
  addNode: (type: string, position?: { x: number; y: number }, config?: Record<string, unknown>) => string;
  updateNodePosition: (id: string, x: number, y: number) => void;
  updateNodeConfig: (id: string, config: Record<string, unknown>) => void;
  deleteNode: (id: string) => void;
  selectNode: (id: string | null) => void;

  connectNodes: (sourceId: string, targetId: string) => void;
  deleteEdge: (id: string) => void;

  setViewport: (viewport: FlowViewport) => void;
  resetFlow: () => void;
  loadTemplate: (templateName: string) => void;
}

const EMPTY_VIEWPORT: FlowViewport = { x: 0, y: 0, zoom: 1 };

const TEMPLATE_FLOWS: Record<string, { nodes: FlowNode[]; edges: FlowEdge[] }> = {
  invoice: {
    nodes: [
      { id: 'n1', type: 'document-input', position: { x: 100, y: 200 }, config: {}, status: 'ready' },
      { id: 'n2', type: 'ocr', position: { x: 360, y: 200 }, config: { language: 'fr' }, status: 'idle' },
      {
        id: 'n3',
        type: 'llm',
        position: { x: 620, y: 200 },
        config: { model: 'gpt-4o', prompt: 'Extract fields: invoice_number, amount_vat, date' },
        status: 'idle',
      },
      { id: 'n4', type: 'output', position: { x: 880, y: 200 }, config: { format: 'json' }, status: 'idle' },
    ],
    edges: [
      { id: 'e1', source: 'n1', target: 'n2' },
      { id: 'e2', source: 'n2', target: 'n3' },
      { id: 'e3', source: 'n3', target: 'n4' },
    ],
  },
  enhance: {
    nodes: [
      { id: 'i1', type: 'document-input', position: { x: 100, y: 200 }, config: {}, status: 'ready' },
      {
        id: 'i2',
        type: 'contrast-enhancer',
        position: { x: 360, y: 200 },
        config: { contrast: 1.35, brightness: 1.08, sharpness: 1.1, auto_contrast: true, cutoff: 1 },
        status: 'idle',
      },
      { id: 'i3', type: 'ocr', position: { x: 620, y: 200 }, config: { language: 'fr' }, status: 'idle' },
      { id: 'i4', type: 'output', position: { x: 880, y: 200 }, config: { format: 'json' }, status: 'idle' },
    ],
    edges: [
      { id: 'ie1', source: 'i1', target: 'i2' },
      { id: 'ie2', source: 'i2', target: 'i3' },
      { id: 'ie3', source: 'i3', target: 'i4' },
    ],
  },
  parser: {
    nodes: [
      { id: 'p1', type: 'document-input', position: { x: 100, y: 200 }, config: {}, status: 'ready' },
      {
        id: 'p2',
        type: 'document-parser',
        position: { x: 360, y: 200 },
        config: { parse_entire_document: true, include_tables: true, include_headers_footers: true, preserve_page_breaks: true, create_downloads: true, sheet_name: '', max_rows_per_sheet: 5000 },
        status: 'idle',
      },
      { id: 'p3', type: 'text-splitter', position: { x: 620, y: 200 }, config: { chunkSize: 1000, overlap: 100 }, status: 'idle' },
      { id: 'p4', type: 'output', position: { x: 880, y: 200 }, config: { format: 'json' }, status: 'idle' },
    ],
    edges: [
      { id: 'pe1', source: 'p1', target: 'p2' },
      { id: 'pe2', source: 'p2', target: 'p3' },
      { id: 'pe3', source: 'p3', target: 'p4' },
    ],
  },
  clustering: {
    nodes: [
      {
        id: 'c1',
        type: 'corpus-input',
        position: { x: 140, y: 210 },
        config: { folder_name: '', file_ids: [], documents: [], file_count: 0 },
        status: 'ready',
      },
      {
        id: 'c2',
        type: 'topic-clustering',
        position: { x: 440, y: 210 },
        config: { number_of_clusters: 0, max_automatic_clusters: 8, create_downloads: true },
        status: 'idle',
      },
    ],
    edges: [
      { id: 'ce1', source: 'c1', target: 'c2', sourcePort: 'corpus', targetPort: 'corpus' },
    ],
  },
  comparison: {
    nodes: [
      {
        id: 'cmp-input-original',
        type: 'document-input',
        position: { x: 80, y: 130 },
        config: {},
        status: 'ready',
      },
      {
        id: 'cmp-input-revised',
        type: 'document-input',
        position: { x: 80, y: 330 },
        config: {},
        status: 'ready',
      },
      {
        id: 'cmp-agent',
        type: 'comparison-agent',
        position: { x: 410, y: 230 },
        config: {
          comparison_level: 'line',
          ignore_whitespace: true,
          ignore_case: false,
          create_downloads: true,
        },
        status: 'idle',
      },
    ],
    edges: [
      {
        id: 'cmp-edge-original',
        source: 'cmp-input-original',
        target: 'cmp-agent',
        sourcePort: 'document',
        targetPort: 'original_document',
      },
      {
        id: 'cmp-edge-revised',
        source: 'cmp-input-revised',
        target: 'cmp-agent',
        sourcePort: 'document',
        targetPort: 'revised_document',
      },
    ],
  },
  rag: {
    nodes: [
      { id: 'r1', type: 'document-input', position: { x: 100, y: 150 }, config: {}, status: 'ready' },
      { id: 'r2', type: 'text-splitter', position: { x: 360, y: 150 }, config: { chunkSize: 1000, overlap: 100 }, status: 'idle' },
      { id: 'r3', type: 'embedding', position: { x: 620, y: 150 }, config: { model: 'text-embedding-3-small' }, status: 'idle' },
      { id: 'r4', type: 'vector-store', position: { x: 880, y: 150 }, config: { collection: 'rag-docs' }, status: 'idle' },
      { id: 'r5', type: 'rag', position: { x: 1140, y: 250 }, config: { topK: 3 }, status: 'idle' },
    ],
    edges: [
      { id: 'er1', source: 'r1', target: 'r2' },
      { id: 'er2', source: 'r2', target: 'r3' },
      { id: 'er3', source: 'r3', target: 'r4' },
      { id: 'er4', source: 'r4', target: 'r5' },
    ],
  },
};

const cloneNodes = (nodes: FlowNode[]) => nodes.map((node) => ({
  ...node,
  position: { ...node.position },
  config: { ...node.config },
}));
const cloneEdges = (edges: FlowEdge[]) => edges.map((edge) => ({ ...edge }));

export const useFlowStore = create<FlowStore>((set, get) => ({
  // A newly opened editor is intentionally empty. Templates are opt-in.
  nodes: [],
  edges: [],
  selectedNodeId: null,
  viewport: EMPTY_VIEWPORT,

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),
  loadFlow: (nodes, edges, viewport = EMPTY_VIEWPORT) => set({
    nodes: cloneNodes(nodes),
    edges: cloneEdges(edges),
    viewport: { ...viewport },
    selectedNodeId: null,
  }),

  addNode: (type, position, config = {}) => {
    const id = generateId('node');
    const newNode: FlowNode = {
      id,
      type,
      position: position || { x: 250, y: 200 },
      config: { ...(getNodeDefinition(type)?.defaultConfig || {}), ...config },
      status: 'idle',
    };

    set((state) => ({
      nodes: [...state.nodes, newNode],
      selectedNodeId: id,
    }));
    return id;
  },

  updateNodePosition: (id, x, y) => set((state) => ({
    nodes: state.nodes.map((node) => (
      node.id === id ? { ...node, position: { x, y } } : node
    )),
  })),

  updateNodeConfig: (id, config) => set((state) => ({
    nodes: state.nodes.map((node) => (
      node.id === id ? { ...node, config: { ...node.config, ...config } } : node
    )),
  })),

  deleteNode: (id) => set((state) => ({
    nodes: state.nodes.filter((node) => node.id !== id),
    edges: state.edges.filter((edge) => edge.source !== id && edge.target !== id),
    selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
  })),

  selectNode: (id) => set({ selectedNodeId: id }),

  connectNodes: (sourceId, targetId) => {
    const state = get();
    const exists = state.edges.some((edge) => edge.source === sourceId && edge.target === targetId);
    if (exists || sourceId === targetId) return;

    const targetNode = state.nodes.find((node) => node.id === targetId);
    let targetPort: string | undefined;
    if (targetNode?.type === 'comparison-agent') {
      const usedPorts = new Set(
        state.edges
          .filter((edge) => edge.target === targetId)
          .map((edge) => edge.targetPort)
          .filter(Boolean),
      );
      targetPort = ['original_document', 'revised_document'].find((port) => !usedPorts.has(port));
      if (!targetPort) return;
    }

    set((current) => ({
      edges: [
        ...current.edges,
        {
          id: generateId('edge'),
          source: sourceId,
          target: targetId,
          targetPort,
        },
      ],
    }));
  },

  deleteEdge: (id) => set((state) => ({
    edges: state.edges.filter((edge) => edge.id !== id),
  })),

  setViewport: (viewport) => set({ viewport }),

  resetFlow: () => set({
    nodes: [],
    edges: [],
    selectedNodeId: null,
    viewport: { ...EMPTY_VIEWPORT },
  }),

  loadTemplate: (templateName) => {
    const template = TEMPLATE_FLOWS[templateName];
    if (!template) return;
    set({
      nodes: cloneNodes(template.nodes),
      edges: cloneEdges(template.edges),
      selectedNodeId: null,
      viewport: { ...EMPTY_VIEWPORT },
    });
  },
}));
