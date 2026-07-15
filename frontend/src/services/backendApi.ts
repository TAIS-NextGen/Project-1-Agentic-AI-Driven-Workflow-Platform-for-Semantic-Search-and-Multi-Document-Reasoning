import {
  CATEGORY_COLORS,
  type NodeCategory,
  type NodeDefinition,
} from '../config/nodeDefinitions';

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
  config_fields?: Array<{ key?: string; default?: unknown }>;
}

interface BackendNodesResponse {
  nodes?: BackendNodeDefinition[];
  total?: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function normalizeCategory(category: string): NodeCategory {
  const normalized = category.toLowerCase();
  if (normalized.includes('preprocess')) return 'Preprocessing';
  if (normalized.includes('ocr')) return 'OCR';
  if (normalized.includes('rag') || normalized.includes('embed')) return 'RAG/Embeddings';
  if (normalized.includes('extract') || normalized.includes('logic')) return 'Extraction';
  if (normalized.includes('output') || normalized.includes('export')) return 'Export/Output';
  return 'Preprocessing';
}

function mapBackendNodeToFrontendDefinition(node: BackendNodeDefinition): NodeDefinition {
  const category = normalizeCategory(node.category || 'preprocessing');
  const defaultConfig = (node.config_fields || []).reduce<Record<string, unknown>>((acc, field) => {
    if (field.key && field.default !== undefined) {
      acc[field.key] = field.default;
    }
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
  };
}

export async function fetchBackendNodeDefinitions(): Promise<NodeDefinition[]> {
  const response = await fetch(`${API_BASE_URL}/api/nodes`);
  if (!response.ok) {
    throw new Error(`Unable to load backend node definitions (${response.status})`);
  }

  const payload: BackendNodesResponse = await response.json();
  const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
  return nodes.map(mapBackendNodeToFrontendDefinition);
}
