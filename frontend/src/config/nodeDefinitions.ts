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

export interface NodeConfigField {
  key: string;
  label?: string;
  type?: string;
  required?: boolean;
  default?: unknown;
  options?: string[];
  description?: string;
  placeholder?: string;
}

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
  configFields?: NodeConfigField[];
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
    description: 'Select an imported document or upload a local file',
    defaultConfig: { max_file_size_mb: 50 },
    backendType: 'document-upload',
    inputs: [{ name: 'file', label: 'File', type: 'document', required: false }],
    outputs: [
      { name: 'document', label: 'Document', type: 'document' },
      { name: 'file_path', label: 'File Path', type: 'text' },
    ],
  },
  {
    type: 'document-upload',
    name: 'Document Upload',
    category: 'Preprocessing',
    icon: '⬆️',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Upload a local document to the backend storage service',
    defaultConfig: {},
    backendType: 'document-upload',
  },
  {
    type: 'corpus-input',
    name: 'Corpus Input',
    category: 'Preprocessing',
    icon: '📁',
    color: '#0ea5e9',
    description: 'Select a folder and import all supported documents as one corpus',
    defaultConfig: { folder_name: '', file_ids: [], documents: [], file_count: 0 },
    backendType: 'corpus-input',
    inputs: [],
    outputs: [
      { name: 'corpus', label: 'Document Corpus', type: 'corpus' },
      { name: 'documents', label: 'Documents', type: 'document[]' },
      { name: 'metadata', label: 'Corpus Metadata', type: 'json' },
    ],
  },
  {
    type: 'topic-clustering',
    name: 'Topic Clustering',
    category: 'RAG/Embeddings',
    icon: '🧠',
    color: '#a855f7',
    description: 'Group a document corpus by topic and show which documents belong to each cluster',
    defaultConfig: { number_of_clusters: 0, max_automatic_clusters: 8, create_downloads: true },
    backendType: 'topic-clustering',
    inputs: [{ name: 'corpus', label: 'Document Corpus', type: 'corpus', required: true }],
    outputs: [
      { name: 'clusters', label: 'Topic Clusters', type: 'json' },
      { name: 'assignments', label: 'Document Assignments', type: 'table' },
      { name: 'metadata', label: 'Metadata', type: 'json' },
      { name: 'downloads', label: 'Downloadable Results', type: 'json' },
    ],
  },
  {
    type: 'comparison-agent',
    name: 'Comparison Agent',
    category: 'Extraction',
    icon: '⚖️',
    color: '#38bdf8',
    description: 'Compare two documents and show additions, deletions, and modified content',
    defaultConfig: {
      comparison_level: 'line',
      ignore_whitespace: true,
      ignore_case: false,
      create_downloads: true,
    },
    backendType: 'comparison-agent',
    inputs: [
      { name: 'original_document', label: 'Original Document', type: 'document', required: true },
      { name: 'revised_document', label: 'Document to Compare', type: 'document', required: true },
    ],
    outputs: [
      { name: 'comparison', label: 'Comparison Result', type: 'json' },
      { name: 'summary', label: 'Comparison Summary', type: 'json' },
      { name: 'diff', label: 'Unified Diff', type: 'text' },
      { name: 'downloads', label: 'Downloadable Reports', type: 'json' },
      { name: 'metadata', label: 'Metadata', type: 'json' },
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
    type: 'contrast-enhancer',
    name: 'Contrast Enhancer',
    category: 'Preprocessing',
    icon: '☀️',
    color: '#f59e0b',
    description: 'Improve readability, contrast, brightness and sharpness',
    defaultConfig: { contrast: 1.35, brightness: 1.08, sharpness: 1.1, auto_contrast: true, cutoff: 1 },
    backendType: 'contrast-enhancer',
    inputs: [{ name: 'image', label: 'Image', type: 'image', required: false }],
    outputs: [
      { name: 'image', label: 'Enhanced Image', type: 'image' },
      { name: 'metadata', label: 'Metadata', type: 'json' },
    ],
  },
  {
    type: 'document-parser',
    name: 'Document Parser',
    category: 'Preprocessing',
    icon: '🧩',
    color: '#14b8a6',
    description: 'Extract complete text and structured data from the latest upstream document',
    defaultConfig: {
      parse_entire_document: true,
      include_tables: true,
      include_headers_footers: true,
      preserve_page_breaks: true,
      sheet_name: '',
      max_rows_per_sheet: 5000,
      max_file_size_mb: 50,
      create_downloads: true,
    },
    backendType: 'document-parser',
    inputs: [{ name: 'document', label: 'Document', type: 'document', required: false }],
    outputs: [
      { name: 'text', label: 'Raw Text', type: 'text' },
      { name: 'data', label: 'Structured Data', type: 'json' },
      { name: 'metadata', label: 'Metadata', type: 'json' },
      { name: 'downloads', label: 'Downloadable Outputs', type: 'json' },
    ],
  },
  {
    type: 'date-normalizer',
    name: 'Date Normalizer',
    category: 'Preprocessing',
    icon: '📅',
    color: '#8b5cf6',
    description: 'Detect dates in text or documents and convert them to a selected format',
    defaultConfig: {
      output_format: 'YYYY-MM-DD',
      replace_in_text: true,
    },
    backendType: 'date-normalizer',
    inputs: [
      { name: 'text', label: 'Text', type: 'text', required: false },
      { name: 'document', label: 'Document', type: 'document', required: false },
    ],
    outputs: [
      { name: 'normalized_text', label: 'Normalized Text', type: 'text' },
      { name: 'dates', label: 'Normalized Dates', type: 'json' },
      { name: 'metadata', label: 'Metadata', type: 'json' },
    ],
  },
  {
    type: 'masker',
    name: 'Masker',
    category: 'Preprocessing',
    icon: '🛡️',
    color: '#ef4444',
    description: 'Mask sensitive data in a PDF while preserving the document layout',
    defaultConfig: {
      mask_emails: true,
      mask_phones: true,
      mask_ids: true,
      mask_addresses: true,
      mask_financial: true,
      mask_ip_addresses: true,
      mask_style: 'black',
    },
    backendType: 'masker',
    inputs: [
      { name: 'document', label: 'Document', type: 'document', required: false },
      { name: 'text', label: 'Document Text', type: 'text', required: false },
    ],
    outputs: [
      { name: 'document', label: 'Masked PDF', type: 'document' },
      { name: 'report', label: 'Masking Report', type: 'json' },
      { name: 'metadata', label: 'Metadata', type: 'json' },
    ],
  },
  {
    type: 'orientation-detector',
    name: 'Orientation detector',
    category: 'Preprocessing',
    icon: '🔄',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Detect and correct page orientation',
    defaultConfig: {},
    backendType: 'orientation-detector',
    inputs: [
      {
        name: 'image',
        type: 'image',
        label: 'Image/page',
        description: 'Image or page whose orientation needs to be corrected',
      },
    ],
    outputs: [
      {
        name: 'image',
        type: 'image',
        label: 'Reoriented page',
        description: 'Image/page with corrected orientation',
      },
      {
        name: 'metadata',
        type: 'json',
        label: 'Metadata',
        description: 'Information on detected orientation and applied correction',
      },
    ],
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
    type: 'language-detector',
    name: 'Language Detector',
    category: 'Extraction',
    icon: '🌐',
    color: CATEGORY_COLORS.Extraction,
    description: 'Detect the language(s) of a given text. Supports multi-language documents.',
    defaultConfig: { detection_mode: 'document', min_probability: 0.1, max_languages: 5 },
    backendType: 'language-detector',
    inputs: [
      {
        name: 'text',
        type: 'text',
        label: 'Text',
        description: 'Raw text to detect language from',
      },
    ],
    outputs: [
      {
        name: 'languages',
        type: 'json',
        label: 'Detected Languages',
        description: 'List of detected languages with confidence scores',
      },
      {
        name: 'languages_str',
        type: 'text',
        label: 'Detected Language(s)',
        description: 'Comma-separated list of detected languages',
      },
    ],
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
    backendType: 'file-converter',
    inputs: [{ name: 'document', label: 'Document', type: 'document', required: false }],
    outputs: [
      { name: 'converted_path', label: 'Converted File', type: 'document' },
      { name: 'text', label: 'Extracted Text', type: 'text' },
    ],
  },
  {
    type: 'watermark-remover',
    name: 'Watermark Remover',
    category: 'Preprocessing',
    icon: '🧽',
    color: CATEGORY_COLORS.Preprocessing,
    description: 'Remove watermarks.',
    defaultConfig: { inpaint_radius: 3 },
    backendType: 'watermark-remover',
    inputs: [{ name: 'document', label: 'Document/Image', type: 'document', required: true }],
    outputs: [{ name: 'cleaned_document', label: 'Cleaned Document', type: 'document' }],
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