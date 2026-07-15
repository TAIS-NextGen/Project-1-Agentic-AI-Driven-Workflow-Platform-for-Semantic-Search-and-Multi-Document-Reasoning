export type NodeCategory =
  | 'Preprocessing'
  | 'OCR'
  | 'RAG/Embeddings'
  | 'Extraction'
  | 'Export/Output'
  | 'Logic/Conditions';

export type NodeDefinitionInput = {
  type?: string;
  name?: string;
  label?: string;
  description?: string;
  required?: boolean;
};

export type NodeDefinitionOutput = NodeDefinitionInput;

export interface NodeDefinition {
  type: string;
  name: string;
  category: NodeCategory;
  icon: string;
  color: string;
  description?: string;
  defaultConfig: Record<string, unknown>;
  backendType?: string;
  inputs?: NodeDefinitionInput[];
  outputs?: NodeDefinitionOutput[];
}

export const NODE_CATEGORIES: NodeCategory[] = [
  'Preprocessing',
  'OCR',
  'RAG/Embeddings',
  'Extraction',
  'Export/Output',
  'Logic/Conditions',
];

export const CATEGORY_COLORS: Record<NodeCategory, string> = {
  Preprocessing: '#06b6d4',
  OCR: '#f97316',
  'RAG/Embeddings': '#a855f7',
  Extraction: '#ec4899',
  'Export/Output': '#eab308',
  'Logic/Conditions': '#3b82f6',
};

export const NODE_DEFINITIONS: NodeDefinition[] = [
  {
    type: 'document-input',
    name: 'Document Input',
    category: 'Preprocessing',
    icon: '📄',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Load documents into the workflow',
    defaultConfig: {},
  },
  {
    type: 'denoising',
    name: 'Denoising',
    category: 'Preprocessing',
    icon: '✨',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Clean and denoise document images',
    defaultConfig: { strength: 0.5 },
    backendType: 'image-denoise',
  },
  {
    type: 'text-splitter',
    name: 'Text Splitter',
    category: 'Preprocessing',
    icon: '✂️',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Split text into chunks',
    defaultConfig: { chunkSize: 512, overlap: 50 },
  },
  {
    type: 'ocr',
    name: 'OCR',
    category: 'OCR',
    icon: '👁️',
    color: CATEGORY_COLORS.OCR,
    description: 'Extract text from images',
    defaultConfig: { language: 'en' },
  },
  {
    type: 'embedding',
    name: 'Embedding',
    category: 'RAG/Embeddings',
    icon: '🔢',
    color: CATEGORY_COLORS['RAG/Embeddings'],
    description: 'Generate vector embeddings',
    defaultConfig: { model: 'text-embedding-3-small' },
  },
  {
    type: 'vector-store',
    name: 'Vector Store',
    category: 'RAG/Embeddings',
    icon: '🗄️',
    color: CATEGORY_COLORS['RAG/Embeddings'],
    description: 'Store and retrieve embeddings',
    defaultConfig: { collection: 'default' },
  },
  {
    type: 'rag',
    name: 'RAG',
    category: 'RAG/Embeddings',
    icon: '🔍',
    color: CATEGORY_COLORS['RAG/Embeddings'],
    description: 'Retrieval-augmented generation',
    defaultConfig: { topK: 5 },
  },
  {
    type: 'llm',
    name: 'LLM',
    category: 'Extraction',
    icon: '🤖',
    color: CATEGORY_COLORS.Extraction,
    description: 'Run a language model prompt',
    defaultConfig: { model: 'gpt-4o', temperature: 0.2 },
  },
  {
    type: 'classifier',
    name: 'Classifier',
    category: 'Extraction',
    icon: '🏷️',
    color: CATEGORY_COLORS.Extraction,
    description: 'Classify document content',
    defaultConfig: { labels: [] },
  },
  {
    type: 'output',
    name: 'Output',
    category: 'Export/Output',
    icon: '📤',
    color: CATEGORY_COLORS['Export/Output'],
    description: 'Export workflow results',
    defaultConfig: { format: 'json' },
  },
  {
    type: 'conditional',
    name: 'Conditional',
    category: 'Logic/Conditions',
    icon: '🔀',
    color: CATEGORY_COLORS['Logic/Conditions'],
    description: 'Branch based on a condition',
    defaultConfig: { expression: '' },
  },
];

export function getNodeDefinition(type: string): NodeDefinition | undefined {
  const staticDefinition = NODE_DEFINITIONS.find((definition) => definition.type === type);
  if (staticDefinition) {
    return staticDefinition;
  }

  if (type === 'image-denoise') {
    return {
      type,
      name: 'Image Denoise',
      category: 'Preprocessing',
      icon: '🧼',
      color: CATEGORY_COLORS.Preprocessing,
      description: 'Reduce noise in an image using the backend node',
      defaultConfig: { method: 'pil-median', max_file_size_mb: 50 },
      backendType: type,
    };
  }

  return undefined;
}

export function getNodesByCategory(): Record<NodeCategory, NodeDefinition[]> {
  const grouped = Object.fromEntries(
    NODE_CATEGORIES.map((category) => [category, [] as NodeDefinition[]]),
  ) as Record<NodeCategory, NodeDefinition[]>;

  for (const definition of NODE_DEFINITIONS) {
    grouped[definition.category].push(definition);
  }

  return grouped;
}
