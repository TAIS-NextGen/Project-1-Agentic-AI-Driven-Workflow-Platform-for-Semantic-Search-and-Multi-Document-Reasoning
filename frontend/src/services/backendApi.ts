import {
  CATEGORY_COLORS,
  type NodeCategory,
  type NodeDefinition,
} from '../config/nodeDefinitions';
import type { DocumentRecord } from '../types';

interface BackendNodeDefinition {
  type: string;
  name: string;
  category: string;
  icon?: string;
  color?: string;
  description?: string;
  version?: string;
  inputs?: Array<Record<string, unknown>>;
  outputs?: Array<Record<string, unknown>>;
  config_fields?: Array<{
    key?: string;
    label?: string;
    type?: string;
    required?: boolean;
    default?: unknown;
    options?: string[];
    description?: string;
    placeholder?: string;
  }>;
}

interface BackendNodesResponse {
  nodes?: BackendNodeDefinition[];
  total?: number;
}

interface DocumentsResponse {
  documents: DocumentRecord[];
  total: number;
}

export interface BatchUploadResponse {
  documents: DocumentRecord[];
  errors: Array<{ filename?: string; error: string }>;
  uploaded: number;
  failed: number;
}

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function normalizeCategory(category: string): NodeCategory {
  const normalized = category.toLowerCase();
  if (normalized.includes('preprocess') || normalized.includes('ingestion') || normalized.includes('normalization')) return 'Preprocessing';
  if (normalized.includes('ocr')) return 'OCR';
  if (normalized.includes('rag') || normalized.includes('embed') || normalized.includes('cluster')) return 'RAG/Embeddings';
  if (normalized.includes('extract') || normalized.includes('logic') || normalized.includes('agent') || normalized.includes('analysis') || normalized.includes('compar')) return 'Extraction';
  if (normalized.includes('output') || normalized.includes('export')) return 'Export/Output';
  return 'Preprocessing';
}

function mapBackendNodeToFrontendDefinition(node: BackendNodeDefinition): NodeDefinition {
  const category = normalizeCategory(node.category || 'preprocessing');
  const defaultConfig = (node.config_fields || []).reduce<Record<string, unknown>>((acc, field) => {
    if (field.key && field.default !== undefined) acc[field.key] = field.default;
    return acc;
  }, {});

  return {
    type: node.type,
    name: node.name,
    category,
    icon: node.icon || '⚙️',
    color: node.color || CATEGORY_COLORS[category],
    description: node.description || `Backend node: ${node.type}`,
    defaultConfig,
    inputs: node.inputs as NodeDefinition['inputs'],
    outputs: node.outputs as NodeDefinition['outputs'],
    configFields: (node.config_fields || []).flatMap((field) => field.key ? [{
      key: field.key,
      label: field.label,
      type: field.type,
      required: field.required,
      default: field.default,
      options: field.options,
      description: field.description,
      placeholder: field.placeholder,
    }] : []),
  };
}

async function parseError(response: Response, fallback: string): Promise<Error> {
  const payload = await response.json().catch(() => ({}));
  const detail = typeof payload?.detail === 'string' ? payload.detail : fallback;
  return new Error(detail);
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

export async function fetchBackendNodeDefinitions(): Promise<NodeDefinition[]> {
  const response = await fetch(`${API_BASE_URL}/api/nodes`);
  if (!response.ok) throw await parseError(response, `Unable to load backend node definitions (${response.status})`);
  const payload: BackendNodesResponse = await response.json();
  return (Array.isArray(payload.nodes) ? payload.nodes : []).map(mapBackendNodeToFrontendDefinition);
}

export async function listDocuments(): Promise<DocumentRecord[]> {
  const response = await fetch(`${API_BASE_URL}/api/documents`);
  if (!response.ok) throw await parseError(response, `Unable to load documents (${response.status})`);
  const payload: DocumentsResponse = await response.json();
  return Array.isArray(payload.documents) ? payload.documents : [];
}

export async function uploadDocument(file: File): Promise<DocumentRecord> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_BASE_URL}/api/documents/upload`, { method: 'POST', body: formData });
  if (!response.ok) throw await parseError(response, `Upload failed (${response.status})`);
  return response.json();
}

export async function uploadDocuments(files: File[], relativePaths: string[] = []): Promise<BatchUploadResponse> {
  const formData = new FormData();
  files.forEach((file, index) => {
    formData.append('files', file, file.name);
    formData.append('relative_paths', relativePaths[index] || file.name);
  });
  const response = await fetch(`${API_BASE_URL}/api/documents/upload/batch`, { method: 'POST', body: formData });
  if (!response.ok) throw await parseError(response, `Batch upload failed (${response.status})`);
  return response.json();
}

export async function importDocumentFromUrl(url: string, filename?: string): Promise<DocumentRecord> {
  const response = await fetch(`${API_BASE_URL}/api/documents/import-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, filename: filename?.trim() || undefined }),
  });
  if (!response.ok) throw await parseError(response, `Cloud import failed (${response.status})`);
  return response.json();
}

export async function deleteDocument(fileId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${encodeURIComponent(fileId)}`, { method: 'DELETE' });
  if (!response.ok) throw await parseError(response, `Delete failed (${response.status})`);
}

export function documentDownloadUrl(fileId: string): string {
  return `${API_BASE_URL}/api/documents/${encodeURIComponent(fileId)}/download`;
}

export interface NodeExecutionResult {
  node_id: string;
  status: string;
  outputs: Record<string, any>;
  error?: string | null;
  duration_ms?: number | null;
}

export async function executeSingleNode(
  nodeId: string,
  nodeType: string,
  config: Record<string, unknown>,
): Promise<NodeExecutionResult> {
  const response = await fetch(`${API_BASE_URL}/api/workflows/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: `node-test-${nodeId}`,
      nodes: [{ id: nodeId, type: nodeType, config }],
      edges: [],
      validate_mode: 'relaxed',
    }),
  });
  if (!response.ok) throw await parseError(response, `Node test failed (${response.status})`);
  const payload = await response.json();
  return payload.results[nodeId] as NodeExecutionResult;
}
