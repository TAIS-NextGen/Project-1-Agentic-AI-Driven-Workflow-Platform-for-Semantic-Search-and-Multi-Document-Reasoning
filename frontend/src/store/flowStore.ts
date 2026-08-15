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
      { id: 'r1', type: 'document-batch-upload', position: { x: 100, y: 220 }, config: {}, status: 'ready' },
      { id: 'r2', type: 'index-documents', position: { x: 480, y: 220 }, config: {}, status: 'idle' },
    ],
    edges: [
      { id: 'er1', source: 'r1', target: 'r2', sourcePort: 'file_ids', targetPort: 'file_ids' },
    ],
  },
  // Reference-only template: the full 9-node B1 fixed RAG chain, shown as a
  // visual figure for the paper. Do NOT run — the query nodes have no question.
  'rag-pipeline-reference': {
    nodes: [
      { id: 'rp1', type: 'document-upload', position: { x: 60, y: 260 }, config: {}, status: 'ready' },
      { id: 'rp2', type: 'paddle-ocr', position: { x: 300, y: 260 }, config: { language: 'en' }, status: 'idle' },
      { id: 'rp3', type: 'text-cleaner', position: { x: 540, y: 260 }, config: {}, status: 'idle' },
      { id: 'rp4', type: 'text-splitter', position: { x: 780, y: 260 }, config: { chunk_size: 512, chunk_overlap: 100 }, status: 'idle' },
      { id: 'rp5', type: 'embedding-node', position: { x: 1020, y: 170 }, config: { model_name: 'nomic-embed-text' }, status: 'idle' },
      { id: 'rp5q', type: 'embedding-node', position: { x: 1020, y: 370 }, config: { model_name: 'nomic-embed-text', chunks: '["What is the total amount?"]' }, status: 'idle' },
      { id: 'rp6', type: 'vector-store', position: { x: 1260, y: 270 }, config: { collection: 'rag-pipeline', top_k: 5 }, status: 'idle' },
      { id: 'rp7', type: 'prompt-builder', position: { x: 1500, y: 270 }, config: { question: '', prompt_template: 'qa_concise', language: 'en' }, status: 'idle' },
      { id: 'rp8', type: 'answer-generator', position: { x: 1740, y: 270 }, config: { question: '', agent_results: '{}' }, status: 'idle' },
    ],
    edges: [
      { id: 'rpe1', source: 'rp1', target: 'rp2', sourcePort: 'document', targetPort: 'image' },
      { id: 'rpe2', source: 'rp2', target: 'rp3', sourcePort: 'text', targetPort: 'text' },
      { id: 'rpe3', source: 'rp3', target: 'rp4', sourcePort: 'cleaned_text', targetPort: 'text' },
      { id: 'rpe4', source: 'rp4', target: 'rp5', sourcePort: 'chunks', targetPort: 'chunks' },
      { id: 'rpe5', source: 'rp5', target: 'rp6', sourcePort: 'embeddings', targetPort: 'embeddings' },
      { id: 'rpe6', source: 'rp4', target: 'rp6', sourcePort: 'chunks', targetPort: 'chunks' },
      { id: 'rpe7', source: 'rp5q', target: 'rp6', sourcePort: 'embeddings', targetPort: 'query_embedding' },
      { id: 'rpe8', source: 'rp6', target: 'rp7', sourcePort: 'results', targetPort: 'chunks' },
      { id: 'rpe9', source: 'rp7', target: 'rp8', sourcePort: 'prompt', targetPort: 'question' },
      { id: 'rpe10', source: 'rp6', target: 'rp8', sourcePort: 'results', targetPort: 'agent_results' },
    ],
  },
  // Runnable single-document pipeline: indexes one document into the shared QA
  // index. Questions are asked in the QA Chat panel (not in this workflow).
  'rag-pipeline': {
    nodes: [
      { id: 'rp1', type: 'document-upload', position: { x: 60, y: 260 }, config: {}, status: 'ready' },
      { id: 'rp2', type: 'paddle-ocr', position: { x: 300, y: 260 }, config: { language: 'en' }, status: 'idle' },
      { id: 'rp3', type: 'text-cleaner', position: { x: 540, y: 260 }, config: {}, status: 'idle' },
      { id: 'rp4', type: 'text-splitter', position: { x: 780, y: 260 }, config: { chunk_size: 512, chunk_overlap: 100 }, status: 'idle' },
      { id: 'rp5', type: 'embedding-node', position: { x: 1020, y: 260 }, config: { model_name: 'nomic-embed-text' }, status: 'idle' },
      { id: 'rp6', type: 'vector-store', position: { x: 1260, y: 260 }, config: { collection: 'rag-pipeline', top_k: 5 }, status: 'idle' },
    ],
    edges: [
      { id: 'rpe1', source: 'rp1', target: 'rp2', sourcePort: 'document', targetPort: 'image' },
      { id: 'rpe2', source: 'rp2', target: 'rp3', sourcePort: 'text', targetPort: 'text' },
      { id: 'rpe3', source: 'rp3', target: 'rp4', sourcePort: 'cleaned_text', targetPort: 'text' },
      { id: 'rpe4', source: 'rp4', target: 'rp5', sourcePort: 'chunks', targetPort: 'chunks' },
      { id: 'rpe5', source: 'rp5', target: 'rp6', sourcePort: 'embeddings', targetPort: 'embeddings' },
      { id: 'rpe6', source: 'rp4', target: 'rp6', sourcePort: 'chunks', targetPort: 'chunks' },
      { id: 'rpe7', source: 'rp1', target: 'rp6', sourcePort: 'file_name', targetPort: 'filename' },
    ],
  },
  // B3 — rule-based routing: the Router deterministically selects the extraction
  // branch (OCR vs parser) from the document extension. Branches read the document
  // directly from the upload node; control edges only gate which branch executes.
  'b3-routing': {
    nodes: [
      { id: 'b1', type: 'document-upload', position: { x: 60, y: 280 }, config: {}, status: 'ready' },
      { id: 'b2', type: 'router', position: { x: 320, y: 120 }, config: { default_route: 'ocr', rules: [{ route: 'parser', extensions: ['.docx', '.pdf'] }, { route: 'ocr', extensions: ['.png', '.jpg', '.jpeg', '.tiff', '.bmp'] }] }, status: 'idle' },
      { id: 'b3', type: 'paddle-ocr', position: { x: 320, y: 280 }, config: { language: 'en' }, status: 'idle' },
      { id: 'b4', type: 'document-parser', position: { x: 320, y: 440 }, config: {}, status: 'idle' },
      { id: 'b5', type: 'text-cleaner', position: { x: 600, y: 280 }, config: {}, status: 'idle' },
      { id: 'b6', type: 'text-splitter', position: { x: 840, y: 280 }, config: { chunk_size: 512, chunk_overlap: 100 }, status: 'idle' },
      { id: 'b7', type: 'embedding-node', position: { x: 1080, y: 280 }, config: { model_name: 'nomic-embed-text' }, status: 'idle' },
      { id: 'b8', type: 'vector-store', position: { x: 1320, y: 280 }, config: { collection: 'b3', top_k: 5 }, status: 'idle' },
    ],
    edges: [
      { id: 'be1', source: 'b1', target: 'b2', sourcePort: 'document', targetPort: 'document' },
      { id: 'be2', source: 'b1', target: 'b3', sourcePort: 'document', targetPort: 'image' },
      { id: 'be3', source: 'b1', target: 'b4', sourcePort: 'document', targetPort: 'document' },
      { id: 'be4', source: 'b3', target: 'b5', sourcePort: 'text', targetPort: 'text' },
      { id: 'be5', source: 'b4', target: 'b5', sourcePort: 'text', targetPort: 'text' },
      { id: 'be6', source: 'b5', target: 'b6', sourcePort: 'cleaned_text', targetPort: 'text' },
      { id: 'be7', source: 'b6', target: 'b7', sourcePort: 'chunks', targetPort: 'chunks' },
      { id: 'be8', source: 'b7', target: 'b8', sourcePort: 'embeddings', targetPort: 'embeddings' },
      { id: 'be9', source: 'b6', target: 'b8', sourcePort: 'chunks', targetPort: 'chunks' },
      { id: 'be10', source: 'b1', target: 'b8', sourcePort: 'file_name', targetPort: 'filename' },
      { id: 'be11', source: 'b2', target: 'b3', kind: 'control', condition: 'ocr' },
      { id: 'be12', source: 'b2', target: 'b4', kind: 'control', condition: 'parser' },
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
