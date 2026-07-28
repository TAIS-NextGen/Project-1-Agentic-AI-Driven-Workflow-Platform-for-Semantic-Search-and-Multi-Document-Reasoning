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
  hidden?: boolean;
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
    type: 'document-upload',
    name: 'Document Upload',
    category: 'Preprocessing',
    icon: '⬆️',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Upload a local document to the backend storage service',
    defaultConfig: {},
    backendType: 'document-upload',
    inputs: [
      { name: 'file', type: 'document', label: 'File', required: false },
    ],
    outputs: [
      { name: 'document', type: 'document', label: 'Document' },
      { name: 'file_path', type: 'text', label: 'File Path', hidden: true },
      { name: 'file_name', type: 'text', label: 'File Name', hidden: true },
      { name: 'mime_type', type: 'text', label: 'MIME Type', hidden: true },
      { name: 'size_bytes', type: 'json', label: 'Size (bytes)', hidden: true },
    ],
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
  {
    type: 'file-converter',
    name: 'File Converter',
    category: 'Preprocessing',
    icon: '🔄',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Convert DOCX/PPTX/images to PDF, or extract plain text from DOCX',
    defaultConfig: { file_id: '', output_mode: 'pdf' },
  },
  {
    type: 'watermark-remover',
    name: 'Watermark Remover',
    category: 'Preprocessing',
    icon: '🧽',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Remove watermarks.',
    defaultConfig: { inpaint_radius: 3 },
  },
  {
    type: 'ocr-node',
    name: 'OCR Node',
    category: 'OCR',
    icon: '📄',
    color: CATEGORY_COLORS.OCR,
    description: 'Convert printed/scanned images or PDFs to text using Tesseract',
    defaultConfig: { file_id: '', language: 'eng', dpi: 300 },
    backendType: 'ocr-node',
  },
  {
    type: 'handwriting-ocr',
    name: 'Handwriting OCR',
    category: 'Extraction',
    icon: '✍️',
    color: CATEGORY_COLORS.Extraction,
    description: 'Extract handwritten text from images using OCR (supports Arabic, French, English)',
    defaultConfig: { language: 'ar' },
    backendType: 'handwriting-ocr',
    inputs: [
      { name: 'image', type: 'image', label: 'Image', required: false },
    ],
    outputs: [
      { name: 'text', type: 'text', label: 'Extracted Text' },
      { name: 'confidence', type: 'json', label: 'Confidence', hidden: true },
      { name: 'details', type: 'json', label: 'Details', hidden: true },
    ],
  },
  {
    type: 'regex-extractor',
    name: 'Regex Extractor',
    category: 'Extraction',
    icon: '🔍',
    color: CATEGORY_COLORS.Extraction,
    description: 'Extract structured fields from text using regex patterns and document templates',
    defaultConfig: {},
    backendType: 'regex-extractor',
    inputs: [
      { name: 'text', type: 'text', label: 'Text', required: false },
    ],
    outputs: [
      { name: 'extracted', type: 'json', label: 'Extracted Fields' },
      { name: 'missing', type: 'json', label: 'Missing Fields' },
      { name: 'stats', type: 'json', label: 'Statistics', hidden: true },
    ],
  },
  {
    type: 'semantic-extractor',
    name: 'Semantic Extractor',
    category: 'Extraction',
    icon: '🧠',
    color: CATEGORY_COLORS.Extraction,
    description: 'Extract structured fields from text using LLM — no regex, just descriptions',
    defaultConfig: {},
    backendType: 'semantic-extractor',
    inputs: [
      { name: 'text', type: 'text', label: 'Text', required: false },
    ],
    outputs: [
      { name: 'extracted', type: 'json', label: 'Extracted Fields' },
      { name: 'stats', type: 'json', label: 'Statistics', hidden: true },
    ],
  },
  {
    type: 'table-extractor',
    name: 'Table Extractor',
    category: 'Extraction',
    icon: '📊',
    color: CATEGORY_COLORS.Extraction,
    description: 'Detect tables in a page/region and extract row/column structure',
    defaultConfig: { file_id: '', confidence_threshold: 0.7 },
  },
  {
    type: 'text-cleaner',
    name: 'Text Cleaner',
    category: 'Preprocessing',
    icon: '🧹',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Clean and normalize raw text: whitespace, hyphenation, casing, dates',
    defaultConfig: { file_id: '', normalize_dates: false, normalize_casing: '' },
    backendType: 'text-cleaner',
  },
  {
    type: 'document-structure-analyzer',
    name: 'Structure Analyzer',
    category: 'Preprocessing',
    icon: '🏗️',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Detect document layout: titles, paragraphs, tables, figures, headers, footers',
    defaultConfig: {},
    backendType: 'document-structure-analyzer',
    inputs: [
      { name: 'document', type: 'document', label: 'Document', required: false },
    ],
    outputs: [
      { name: 'structure', type: 'json', label: 'Structure Map' },
      { name: 'summary', type: 'json', label: 'Summary', hidden: true },
    ],
  },
  {
    type: 'gap-checker',
    name: 'Gap Checker',
    category: 'Preprocessing',
    icon: '🔎',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Verify missing fields in a document against a reference checklist',
    defaultConfig: {},
    backendType: 'gap-checker',
    inputs: [
      { name: 'text', type: 'text', label: 'Text', required: true },
    ],
    outputs: [
      { name: 'report', type: 'json', label: 'Gap Report' },
      { name: 'score', type: 'json', label: 'Completeness Score' },
      { name: 'missing', type: 'json', label: 'Missing Fields' },
    ],
  },
  {
    type: 'prompt-builder',
    name: 'Prompt Builder',
    category: 'RAG/Embeddings',
    icon: '📝',
    color: CATEGORY_COLORS['RAG/Embeddings'],
    description: 'Build the final prompt for the LLM from chunks, context and question',
    defaultConfig: {},
    backendType: 'prompt-builder',
    inputs: [
      { name: 'chunks', type: 'json', label: 'Chunks', required: true },
      { name: 'context', type: 'json', label: 'Context', required: false },
      { name: 'question', type: 'text', label: 'Question', required: true },
    ],
    outputs: [
      { name: 'prompt', type: 'text', label: 'Structured Prompt' },
    ],
  },
  {
    type: 'feedback-collector',
    name: 'Feedback Collector',
    category: 'RAG/Embeddings',
    icon: '📊',
    color: CATEGORY_COLORS['RAG/Embeddings'],
    description: 'Collect user feedback to improve RAG',
    defaultConfig: {},
    backendType: 'feedback-collector',
    inputs: [
      { name: 'question', type: 'text', label: 'Question', required: true },
      { name: 'answer', type: 'text', label: 'Answer', required: true },
      { name: 'chunks_used', type: 'json', label: 'Chunks Used', required: false },
      { name: 'feedback', type: 'json', label: 'User Feedback', required: true },
    ],
    outputs: [
      { name: 'signal', type: 'json', label: 'Feedback Signal' },
      { name: 'stored', type: 'json', label: 'Storage Confirmation', hidden: true },
    ],
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