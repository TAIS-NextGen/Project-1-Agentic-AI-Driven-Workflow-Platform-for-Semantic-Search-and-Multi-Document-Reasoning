import { useState, useEffect, useMemo } from 'react';
import { useFlowStore } from '../../store/flowStore';
import { getNodeDefinition, NODE_DEFINITIONS, type NodeDefinition } from '../../config/nodeDefinitions';
import { executeSingleNode, listDocuments, uploadDocument, uploadDocuments, type NodeExecutionResult } from '../../services/backendApi';
import type { DocumentRecord } from '../../types';
import { useExecutionStore } from '../../store/executionStore';
import styles from './NodeConfigPanel.module.css';


interface ResolvedInputSource {
  kind: 'document' | 'image' | 'text' | 'corpus' | 'data';
  sourceNodeId: string;
  sourceNodeName: string;
  sourcePort: string;
  sourcePortLabel: string;
  targetPort: string;
  filename?: string;
  documentCount?: number;
  folderName?: string;
  fromExecution: boolean;
}

const FILE_DESCRIPTOR_KEYS = [
  'document',
  'cleaned_document',
  'converted_document',
  'converted_file',
  'converted_path',
  'processed_document',
  'enhanced_document',
  'image',
  'file',
  'artifact',
  'output',
];

function basenameFromPath(value: string): string | null {
  const normalized = value.trim().replaceAll('\\', '/');
  if (!normalized) return null;
  const candidate = normalized.split('/').filter(Boolean).pop() || '';
  return /\.[a-z0-9]{1,12}$/i.test(candidate) ? candidate : null;
}

function filenameFromOutput(value: unknown, depth = 0): string | null {
  if (value == null || depth > 5) return null;

  if (typeof value === 'string') {
    return basenameFromPath(value);
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const filename = filenameFromOutput(item, depth + 1);
      if (filename) return filename;
    }
    return null;
  }

  if (typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;

  for (const key of ['filename', 'file_name', 'original_filename', 'stored_name']) {
    const candidate = record[key];
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim();
  }

  for (const key of ['path', 'output_path', 'download_url']) {
    const candidate = record[key];
    if (typeof candidate === 'string') {
      const filename = basenameFromPath(candidate);
      if (filename) return filename;
    }
  }

  for (const key of FILE_DESCRIPTOR_KEYS) {
    if (!(key in record)) continue;
    const filename = filenameFromOutput(record[key], depth + 1);
    if (filename) return filename;
  }

  for (const nested of Object.values(record)) {
    const filename = filenameFromOutput(nested, depth + 1);
    if (filename) return filename;
  }
  return null;
}

export function NodeConfigPanel({ backendDefinitions = [] }: { backendDefinitions?: NodeDefinition[] }) {
  const { selectedNodeId, nodes, edges, updateNodeConfig, selectNode } = useFlowStore();
  const { executionResults } = useExecutionStore();
  const [activeTab, setActiveTab] = useState<'parameters' | 'io' | 'test' | 'results'>('parameters');
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<NodeExecutionResult | null>(null);
  const [libraryDocuments, setLibraryDocuments] = useState<DocumentRecord[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(false);

  const mergedDefinitions = useMemo(
    () => new Map(
      [...NODE_DEFINITIONS, ...backendDefinitions].map((def) => [def.type, def]),
    ),
    [backendDefinitions],
  );

  const resolveDefinition = (type: string) => mergedDefinitions.get(type) || getNodeDefinition(type);

  const node = nodes.find((n) => n.id === selectedNodeId);
  const definition = node ? resolveDefinition(node.type) : null;
  const incomingEdges = node ? edges.filter((edge) => edge.target === node.id) : [];
  const findNearestConfiguredFilename = (startNodeId: string): string | null => {
    const queue = [startNodeId];
    const visited = new Set<string>();
    while (queue.length) {
      const currentNodeId = queue.shift();
      if (!currentNodeId || visited.has(currentNodeId)) continue;
      visited.add(currentNodeId);
      const currentNode = nodes.find((candidate) => candidate.id === currentNodeId);
      if (!currentNode) continue;

      const executionFilename = filenameFromOutput(executionResults?.[currentNode.id]?.outputs);
      const configuredFilename = typeof currentNode.config?.filename === 'string'
        ? currentNode.config.filename.trim()
        : '';
      if (executionFilename || configuredFilename) return executionFilename || configuredFilename;

      edges
        .filter((edge) => edge.target === currentNode.id)
        .forEach((edge) => queue.push(edge.source));
    }
    return null;
  };

  const resolveInputSources = (): ResolvedInputSource[] => {
    if (!definition) return [];
    return incomingEdges.flatMap((edge) => {
    const sourceNode = nodes.find((candidate) => candidate.id === edge.source);
    if (!sourceNode) return [];

    const sourceDefinition = resolveDefinition(sourceNode.type);
    const outputs = executionResults?.[sourceNode.id]?.outputs || {};
    const outputEntries = Object.entries(outputs);
    const explicitPort = edge.sourcePort && edge.sourcePort !== 'output' ? edge.sourcePort : undefined;

    let sourcePort = explicitPort;
    if (!sourcePort) {
      const textEntry = outputEntries.find(([key, value]) => (
        ['text', 'raw_text', 'cleaned_text', 'normalized_text', 'content'].includes(key)
        && typeof value === 'string'
        && value.trim().length > 0
      ));
      const fileEntry = outputEntries.find(([, value]) => filenameFromOutput(value));
      sourcePort = textEntry?.[0] || fileEntry?.[0];
    }
    if (!sourcePort) {
      if (sourceNode.type === 'document-parser') sourcePort = 'text';
      else if (sourceNode.type === 'file-converter') {
        sourcePort = sourceNode.config?.output_mode === 'text' ? 'text' : 'converted_path';
      }
    }
    if (!sourcePort) {
      const acceptedTypes = (definition.inputs || []).map((port) => port.type).filter(Boolean);
      sourcePort = acceptedTypes
        .flatMap((acceptedType) => sourceDefinition?.outputs?.filter((port) => port.type === acceptedType) || [])
        .map((port) => port.name)
        .find(Boolean);
    }
    if (!sourcePort) {
      const outputPriority = ['corpus', 'documents', 'document', 'cleaned_document', 'converted_path', 'converted_file', 'image', 'text', 'normalized_text', 'chunks', 'data', 'output'];
      sourcePort = outputPriority.find((name) => sourceDefinition?.outputs?.some((port) => port.name === name))
        || sourceDefinition?.outputs?.[0]?.name
        || edge.sourcePort
        || 'output';
    }

    const portDefinition = sourceDefinition?.outputs?.find((port) => port.name === sourcePort);
    const selectedOutput = outputs[sourcePort];
    const executionFilename = filenameFromOutput(selectedOutput) || filenameFromOutput(outputs);
    const configuredFilename = typeof sourceNode.config?.filename === 'string'
      ? sourceNode.config.filename.trim()
      : '';
    const filename = executionFilename || configuredFilename || findNearestConfiguredFilename(sourceNode.id) || undefined;

    const portType = String(portDefinition?.type || '').toLowerCase();
    let kind: ResolvedInputSource['kind'] = 'data';
    if (portType === 'corpus' || sourcePort === 'corpus') kind = 'corpus';
    else if (portType === 'text' || portType === 'chunks' || ['text', 'normalized_text', 'cleaned_text', 'raw_text'].includes(sourcePort)) kind = 'text';
    else if (portType === 'image') kind = 'image';
    else if (portType.includes('document') || filename) kind = 'document';

    const outputRecord = selectedOutput && typeof selectedOutput === 'object' ? selectedOutput as Record<string, unknown> : null;
    const outputDocuments = Array.isArray(outputRecord?.documents) ? outputRecord?.documents : null;
    const configuredDocuments = Array.isArray(sourceNode.config?.documents) ? sourceNode.config.documents : [];
    const documentCount = kind === 'corpus'
      ? Number(outputRecord?.document_count || outputDocuments?.length || sourceNode.config?.file_count || configuredDocuments.length || 0)
      : undefined;
    const folderName = kind === 'corpus'
      ? String(outputRecord?.name || sourceNode.config?.folder_name || 'Document corpus')
      : undefined;

    return [{
      kind,
      sourceNodeId: sourceNode.id,
      sourceNodeName: sourceDefinition?.name || sourceNode.type,
      sourcePort,
      sourcePortLabel: portDefinition?.label || sourcePort.replaceAll('_', ' '),
      targetPort: edge.targetPort || 'input',
      filename,
      documentCount,
      folderName,
      fromExecution: Boolean(outputEntries.length),
    }];
  });
  };

  const inputSources = resolveInputSources();
  let nodeResult: any = testResult;
  if (!nodeResult && node && executionResults) {
    if (node.type === 'output') {
      const incomingEdge = edges.find((e) => e.target === node.id);
      if (incomingEdge) {
        nodeResult = executionResults[incomingEdge.source];
      }
    } else {
      nodeResult = executionResults[node.id];
    }
  }

  const [localConfig, setLocalConfig] = useState<Record<string, any>>({});

  useEffect(() => {
    if (node) {
      setLocalConfig(node.config || {});
      setTestResult(null);
      setTestMessage(null);
      setUploadMessage(null);
    }
  }, [selectedNodeId, node]);


  useEffect(() => {
    if (!node || !['document-input', 'document-upload'].includes(node.type)) return;
    let mounted = true;
    setLibraryLoading(true);
    listDocuments()
      .then((documents) => {
        if (mounted) setLibraryDocuments(documents);
      })
      .catch(() => {
        if (mounted) setLibraryDocuments([]);
      })
      .finally(() => {
        if (mounted) setLibraryLoading(false);
      });
    return () => { mounted = false; };
  }, [node?.type, selectedNodeId]);

  if (!node || !definition) return null;

  const handleUpdateField = (key: string, value: any) => {
    setLocalConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleApply = () => {
    updateNodeConfig(node.id, localConfig);
    selectNode(null);
  };

  const handleCancel = () => {
    selectNode(null);
  };

  const handleUploadDocument = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadMessage(null);

    try {
      const payload = await uploadDocument(file);
      const updatedConfig = {
        ...localConfig,
        file_id: payload.file_id,
        filename: payload.filename,
        mime_type: payload.mime_type,
        size_bytes: payload.size_bytes,
        uploaded_at: payload.uploaded_at,
      };
      setLocalConfig(updatedConfig);
      updateNodeConfig(node.id, updatedConfig);
      setLibraryDocuments((current) => [payload, ...current.filter((item) => item.file_id !== payload.file_id)]);
      setUploadMessage(`Uploaded ${payload.filename} successfully.`);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleUploadCorpus = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;

    const supported = /\.(pdf|docx|xlsx|xlsm|csv|txt|md)$/i;
    const acceptedFiles = files.filter((file) => supported.test(file.name));
    const rejectedCount = files.length - acceptedFiles.length;
    if (!acceptedFiles.length) {
      setUploadMessage('The selected folder contains no supported documents.');
      event.target.value = '';
      return;
    }

    const relativePaths = acceptedFiles.map((file) => {
      const candidate = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
      return candidate || file.name;
    });
    const folderName = relativePaths[0]?.split('/')[0] || 'Document corpus';

    setUploading(true);
    setUploadMessage(`Uploading ${acceptedFiles.length} document${acceptedFiles.length === 1 ? '' : 's'}…`);
    try {
      const payload = await uploadDocuments(acceptedFiles, relativePaths);
      const documents = payload.documents.map((document) => ({
        file_id: document.file_id,
        filename: document.filename,
        relative_path: document.relative_path || document.filename,
        path: document.path,
        mime_type: document.mime_type,
        extension: document.extension,
        size_bytes: document.size_bytes,
      }));
      const updatedConfig = {
        ...localConfig,
        folder_name: folderName,
        file_ids: documents.map((document) => document.file_id),
        documents,
        file_count: documents.length,
      };
      setLocalConfig(updatedConfig);
      updateNodeConfig(node.id, updatedConfig);
      const parts = [`${documents.length} document${documents.length === 1 ? '' : 's'} imported from ${folderName}.`];
      if (payload.failed) parts.push(`${payload.failed} file${payload.failed === 1 ? '' : 's'} could not be imported.`);
      if (rejectedCount) parts.push(`${rejectedCount} unsupported file${rejectedCount === 1 ? '' : 's'} ignored.`);
      setUploadMessage(parts.join(' '));
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : 'Folder import failed.');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const handleTestNode = async () => {
    setTesting(true);
    setTestMessage('Initialising node test…');
    setTestResult(null);
    updateNodeConfig(node.id, localConfig);

    try {
      const backendType = definition.backendType || node.type;
      const result = await executeSingleNode(node.id, backendType, localConfig);
      setTestResult(result);
      setTestMessage(result.status === 'success'
        ? `Test completed in ${(result.duration_ms || 0).toFixed(1)} ms.`
        : `Test failed: ${result.error || 'Unknown error'}`);
      if (result.status === 'success') {
        setActiveTab('results');
      }
    } catch (error) {
      setTestMessage(error instanceof Error ? error.message : 'Node test failed.');
    } finally {
      setTesting(false);
    }
  };

  const renderInputSourceSummary = () => {
    if (['document-input', 'document-upload', 'corpus-input'].includes(node.type)) return null;

    if (!inputSources.length) {
      const expected = definition.inputs?.map((port) => port.label || port.name).filter(Boolean).join(' or ');
      return (
        <div className={styles.connectionCard}>
          <strong>No input connected</strong>
          <span>Connect {expected || 'an upstream node'} before running this node.</span>
        </div>
      );
    }

    const orderedSources = node.type === 'comparison-agent'
      ? [...inputSources].sort((left, right) => (
          left.targetPort === 'original_document' ? -1 : right.targetPort === 'original_document' ? 1 : 0
        ))
      : inputSources;

    return (
      <>
        <div className={styles.sourceList}>
          {orderedSources.map((source) => {
            const isFile = source.kind === 'document' || source.kind === 'image';
            const isCorpus = source.kind === 'corpus';
            const comparisonTitle = node.type === 'comparison-agent'
              ? source.targetPort === 'revised_document'
                ? 'Document to compare'
                : 'Original document'
              : null;
            const title = comparisonTitle
              || (isCorpus ? 'Input corpus' : isFile ? 'Input document' : source.kind === 'text' ? 'Input text' : 'Input data');
            const value = isCorpus
              ? `${source.folderName || 'Document corpus'} · ${source.documentCount || 0} document${source.documentCount === 1 ? '' : 's'}`
              : isFile ? (source.filename || source.sourceNodeName) : source.sourceNodeName;
            return (
              <div className={styles.inputDocumentCard} key={`${source.sourceNodeId}-${source.sourcePort}-${source.targetPort}`}>
                <div>
                  <strong>{title}</strong>
                  <span>
                    {isFile || isCorpus ? 'Received from' : 'Produced by'} {source.sourceNodeName} · {source.sourcePortLabel}
                    {source.fromExecution ? ' · latest executed output' : ''}
                  </span>
                </div>
                <code title={value}>{value}</code>
              </div>
            );
          })}
        </div>
        {node.type === 'comparison-agent' && inputSources.length < 2 && (
          <div className={styles.connectionCard}>
            <strong>One more document is required</strong>
            <span>Connect a second Document Input node to complete the comparison.</span>
          </div>
        )}
      </>
    );
  };

  const renderConfigFields = () => {
    switch (node.type) {
      case 'ocr':
        return (
          <>
            <div className={styles.formGroup}>
              <label>OCR Engine</label>
              <select
                value={localConfig.engine || 'tesseract'}
                onChange={(e) => handleUpdateField('engine', e.target.value)}
                className={styles.select}
              >
                <option value="tesseract">Tesseract OCR</option>
                <option value="cloud-vision">Google Cloud Vision</option>
                <option value="azure-ocr">Azure Read API</option>
                <option value="pdf-extractor">Native PDF Parser</option>
              </select>
            </div>

            <div className={styles.formGroup}>
              <label>Language(s)</label>
              <div className={styles.pillsRow}>
                {['English', 'French', 'Arabic'].map((lang) => {
                  const currentLangs = localConfig.languages || ['English'];
                  const exists = currentLangs.includes(lang);
                  return (
                    <button
                      key={lang}
                      onClick={() => {
                        const next = exists
                          ? currentLangs.filter((l: string) => l !== lang)
                          : [...currentLangs, lang];
                        handleUpdateField('languages', next.length ? next : ['English']);
                      }}
                      className={`${styles.pill} ${exists ? styles.pillActive : ''}`}
                    >
                      {lang} {exists ? '×' : '+'}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className={styles.formGroup}>
              <label>Resolution (DPI): {localConfig.dpi || 300}</label>
              <input
                type="range"
                min="72"
                max="600"
                step="1"
                value={localConfig.dpi || 300}
                onChange={(e) => handleUpdateField('dpi', parseInt(e.target.value))}
                className={styles.range}
              />
              <div className={styles.rangeLabels}>
                <span>72 DPI</span>
                <span>600 DPI</span>
              </div>
            </div>

            <div className={styles.formGroup}>
              <label>Output Format</label>
              <div className={styles.formatButtonGroup}>
                {['Plain Text', 'Structured', 'JSON'].map((fmt) => {
                  const active = (localConfig.format || 'Structured') === fmt;
                  return (
                    <button
                      key={fmt}
                      onClick={() => handleUpdateField('format', fmt)}
                      className={`${styles.formatBtn} ${active ? styles.formatBtnActive : ''}`}
                    >
                      {fmt}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className={styles.formGroup}>
              <label>Confidence Threshold: {localConfig.confidence || 75}%</label>
              <input
                type="range"
                min="0"
                max="100"
                value={localConfig.confidence || 75}
                onChange={(e) => handleUpdateField('confidence', parseInt(e.target.value))}
                className={styles.range}
              />
            </div>

            <div className={styles.toggleGroup}>
              <div className={styles.toggleRow}>
                <span>Preserve Layout</span>
                <input
                  type="checkbox"
                  checked={localConfig.preserveLayout ?? true}
                  onChange={(e) => handleUpdateField('preserveLayout', e.target.checked)}
                />
              </div>
              <div className={styles.toggleRow}>
                <span>Ignore Headers/Footers</span>
                <input
                  type="checkbox"
                  checked={localConfig.ignoreHeadersFooters ?? false}
                  onChange={(e) => handleUpdateField('ignoreHeadersFooters', e.target.checked)}
                />
              </div>
            </div>
          </>
        );

      case 'llm':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Language Model</label>
              <select
                value={localConfig.model || 'gpt-4o'}
                onChange={(e) => handleUpdateField('model', e.target.value)}
                className={styles.select}
              >
                <option value="gpt-4o">gpt-4o (Default)</option>
                <option value="gpt-4-turbo">gpt-4-turbo</option>
                <option value="claude-3-5-sonnet">claude-3.5-sonnet</option>
                <option value="gemini-1.5-pro">gemini-1.5-pro</option>
              </select>
            </div>

            <div className={styles.formGroup}>
              <label>Temperature: {localConfig.temperature ?? 0.2}</label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={localConfig.temperature ?? 0.2}
                onChange={(e) => handleUpdateField('temperature', parseFloat(e.target.value))}
                className={styles.range}
              />
            </div>

            <div className={styles.formGroup}>
              <label>Prompt Template</label>
              <textarea
                value={localConfig.prompt || ''}
                onChange={(e) => handleUpdateField('prompt', e.target.value)}
                placeholder="Write system instructions or queries here..."
                className={styles.textarea}
                rows={6}
              />
            </div>
          </>
        );

      case 'document-input':
      case 'document-upload':
        return (
          <>
            <div className={styles.infoCard}>
              <strong>Document source</strong>
              <span>Choose a document already present in the library or upload a new local file.</span>
            </div>
            <div className={styles.formGroup}>
              <label>Document library</label>
              <select
                value={String(localConfig.file_id || '')}
                onChange={(event) => {
                  const selected = libraryDocuments.find((item) => item.file_id === event.target.value);
                  if (!selected) {
                    handleUpdateField('file_id', '');
                    return;
                  }
                  setLocalConfig((current) => ({
                    ...current,
                    file_id: selected.file_id,
                    filename: selected.filename,
                    mime_type: selected.mime_type,
                    size_bytes: selected.size_bytes,
                    uploaded_at: selected.uploaded_at,
                  }));
                }}
                className={styles.select}
              >
                <option value="">{libraryLoading ? 'Loading documents…' : 'Select an imported document'}</option>
                {libraryDocuments.map((document) => (
                  <option key={document.file_id} value={document.file_id}>
                    {document.filename}
                  </option>
                ))}
              </select>
              {!libraryLoading && !libraryDocuments.length && (
                <p className={styles.helpText}>No imported document yet. Upload one below or use the Documents page.</p>
              )}
            </div>
            <div className={styles.formGroup}>
              <label>Upload a new local document</label>
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.bmp,.webp,.docx,.txt,.md,.csv,.xlsx,.xlsm"
                onChange={handleUploadDocument}
                className={styles.fileInput}
              />
              {uploading && <p className={styles.helpText}>Uploading…</p>}
              {uploadMessage && <p className={styles.helpText}>{uploadMessage}</p>}
              {localConfig.filename && (
                <div className={styles.metaRow} style={{ marginTop: '8px', borderBottom: 'none' }}>
                  <span className={styles.metaLabel}>Selected file:</span>
                  <span className={styles.metaValue} style={{ color: '#10b981' }}>{String(localConfig.filename)}</span>
                </div>
              )}
            </div>
            <div className={styles.formGroup}>
              <label>Max File Size (MB): {localConfig.max_file_size_mb ?? 50}</label>
              <input
                type="number"
                min="1"
                max="500"
                value={localConfig.max_file_size_mb ?? 50}
                onChange={(e) => handleUpdateField('max_file_size_mb', parseInt(e.target.value, 10))}
                className={styles.textInput}
              />
            </div>
          </>
        );

      case 'corpus-input': {
        const documents = Array.isArray(localConfig.documents) ? localConfig.documents : [];
        return (
          <>
            <div className={styles.infoCard}>
              <strong>Document folder</strong>
              <span>Select one folder. All supported PDF, Word, Excel, CSV, TXT and Markdown files are uploaded as one corpus.</span>
            </div>

            <div className={styles.formGroup}>
              <label>Select a folder</label>
              <input
                type="file"
                multiple
                accept=".pdf,.docx,.xlsx,.xlsm,.csv,.txt,.md"
                onChange={handleUploadCorpus}
                className={styles.fileInput}
                {...({ webkitdirectory: '', directory: '' } as any)}
              />
              {uploading && <p className={styles.helpText}>Importing folder…</p>}
              {uploadMessage && <p className={styles.helpText}>{uploadMessage}</p>}
            </div>

            {documents.length > 0 && (
              <div className={styles.corpusSummary}>
                <div className={styles.corpusSummaryHeader}>
                  <div>
                    <strong>📁 {String(localConfig.folder_name || 'Document corpus')}</strong>
                    <span>{documents.length} document{documents.length === 1 ? '' : 's'} ready</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      const updated = { ...localConfig, folder_name: '', file_ids: [], documents: [], file_count: 0 };
                      setLocalConfig(updated);
                      updateNodeConfig(node.id, updated);
                      setUploadMessage(null);
                    }}
                    className={styles.clearCorpusButton}
                  >
                    Clear
                  </button>
                </div>
                <div className={styles.corpusFiles}>
                  {documents.slice(0, 10).map((document: any, index: number) => (
                    <div key={String(document.file_id || `${document.filename}-${index}`)}>
                      <span>📄</span>
                      <code title={String(document.relative_path || document.filename || '')}>
                        {String(document.relative_path || document.filename || 'document')}
                      </code>
                    </div>
                  ))}
                  {documents.length > 10 && <small>+ {documents.length - 10} more documents</small>}
                </div>
              </div>
            )}

            <div className={styles.infoCard}>
              <strong>Next step</strong>
              <span>Connect this node to Topic Clustering. The complete corpus is passed through the Document Corpus output.</span>
            </div>
          </>
        );
      }

      case 'topic-clustering':
        return (
          <>
            <div className={styles.infoCard}>
              <strong>Automatic topic grouping</strong>
              <span>The node parses every document, compares its content and returns the documents belonging to each topic.</span>
            </div>

            <div className={styles.formGroup}>
              <label>Number of clusters</label>
              <select
                value={Number(localConfig.number_of_clusters ?? 0)}
                onChange={(event) => handleUpdateField('number_of_clusters', Number(event.target.value))}
                className={styles.select}
              >
                <option value={0}>Automatic — recommended</option>
                {Array.from({ length: 11 }, (_, index) => index + 2).map((count) => (
                  <option key={count} value={count}>{count} clusters</option>
                ))}
              </select>
              <span className={styles.helpText}>Automatic mode evaluates several cluster counts and keeps the clearest separation.</span>
            </div>

            <div className={styles.toggleGroup}>
              <label className={styles.toggleRow}>
                <span>
                  <strong>Create downloadable results</strong>
                  <small>Generate JSON, CSV and ZIP files containing all clusters and document assignments.</small>
                </span>
                <input
                  type="checkbox"
                  checked={localConfig.create_downloads ?? true}
                  onChange={(event) => handleUpdateField('create_downloads', event.target.checked)}
                />
              </label>
            </div>

            <div className={styles.infoCard}>
              <strong>Outputs</strong>
              <span>Topic name, keywords, document list, similarity score and complete assignment table.</span>
            </div>
          </>
        );

      case 'comparison-agent':
        return (
          <>
            <div className={styles.infoCard}>
              <strong>Compare two complete documents</strong>
              <span>
                Connect the original document first, then connect the new or revised document.
                The agent extracts both files and shows every added, removed, or modified section.
              </span>
            </div>

            <div className={styles.formGroup}>
              <label>Comparison detail</label>
              <select
                value={localConfig.comparison_level || 'line'}
                onChange={(event) => handleUpdateField('comparison_level', event.target.value)}
                className={styles.select}
              >
                <option value="line">Line by line — recommended</option>
                <option value="paragraph">Paragraph by paragraph</option>
              </select>
            </div>

            <div className={styles.toggleGroup}>
              <label className={styles.toggleRow}>
                <span>
                  <strong>Ignore spacing differences</strong>
                  <small>Treat indentation and repeated spaces as equivalent.</small>
                </span>
                <input
                  type="checkbox"
                  checked={localConfig.ignore_whitespace ?? true}
                  onChange={(event) => handleUpdateField('ignore_whitespace', event.target.checked)}
                />
              </label>
              <label className={styles.toggleRow}>
                <span>
                  <strong>Ignore upper/lower case</strong>
                  <small>Treat “Document” and “document” as the same value.</small>
                </span>
                <input
                  type="checkbox"
                  checked={localConfig.ignore_case ?? false}
                  onChange={(event) => handleUpdateField('ignore_case', event.target.checked)}
                />
              </label>
              <label className={styles.toggleRow}>
                <span>
                  <strong>Create downloadable reports</strong>
                  <small>Generate JSON, text diff, side-by-side HTML, and ZIP reports.</small>
                </span>
                <input
                  type="checkbox"
                  checked={localConfig.create_downloads ?? true}
                  onChange={(event) => handleUpdateField('create_downloads', event.target.checked)}
                />
              </label>
            </div>

            <div className={styles.infoCard}>
              <strong>Supported documents</strong>
              <span>PDF, DOCX, XLSX/XLSM, CSV, TXT and Markdown. Scanned PDFs need OCR first.</span>
            </div>
          </>
        );

      case 'denoising':
      case 'image-denoise':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Method</label>
              <select
                value={localConfig.method || 'pil-median'}
                onChange={(e) => handleUpdateField('method', e.target.value)}
                className={styles.select}
              >
                <option value="pil-median">PIL Median Filter</option>
                <option value="gaussian">Gaussian Blur</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Max File Size (MB): {localConfig.max_file_size_mb ?? 50}</label>
              <input
                type="number"
                min="1"
                max="500"
                value={localConfig.max_file_size_mb ?? 50}
                onChange={(e) => handleUpdateField('max_file_size_mb', parseInt(e.target.value, 10))}
                className={styles.textInput}
              />
            </div>
            <div className={styles.formGroup}>
              <label>Allowed Extensions</label>
              <input
                type="text"
                value={(localConfig.allowed_extensions || ['.png', '.jpg', '.jpeg']).join(', ')}
                onChange={(e) => handleUpdateField('allowed_extensions', e.target.value.split(',').map((entry) => entry.trim()).filter(Boolean))}
                className={styles.textInput}
                placeholder=".png, .jpg"
              />
            </div>
          </>
        );

      case 'contrast-enhancer':
        return (
          <>
            <div className={styles.infoCard}>
              <strong>Local image enhancement</strong>
              <span>Upload an image or connect an upstream image node. No cloud key is required.</span>
            </div>
            <div className={styles.formGroup}>
              <label>Test image</label>
              <input type="file" accept="image/*" onChange={handleUploadDocument} className={styles.fileInput} />
              {uploading && <p className={styles.helpText}>Uploading…</p>}
              {uploadMessage && <p className={styles.helpText}>{uploadMessage}</p>}
              {localConfig.filename && <span className={styles.fileBadge}>✓ {String(localConfig.filename)}</span>}
            </div>
            <div className={styles.formGroup}>
              <label>Contrast <span>{Number(localConfig.contrast ?? 1.35).toFixed(2)}×</span></label>
              <input type="range" min="0.5" max="3" step="0.05" value={localConfig.contrast ?? 1.35}
                onChange={(e) => handleUpdateField('contrast', Number(e.target.value))} className={styles.range} />
            </div>
            <div className={styles.formGroup}>
              <label>Brightness <span>{Number(localConfig.brightness ?? 1.08).toFixed(2)}×</span></label>
              <input type="range" min="0.5" max="2" step="0.05" value={localConfig.brightness ?? 1.08}
                onChange={(e) => handleUpdateField('brightness', Number(e.target.value))} className={styles.range} />
            </div>
            <div className={styles.formGroup}>
              <label>Sharpness <span>{Number(localConfig.sharpness ?? 1.1).toFixed(2)}×</span></label>
              <input type="range" min="0" max="3" step="0.05" value={localConfig.sharpness ?? 1.1}
                onChange={(e) => handleUpdateField('sharpness', Number(e.target.value))} className={styles.range} />
            </div>
            <div className={styles.toggleGroup}>
              <label className={styles.toggleRow}>
                <span><strong>Automatic tonal correction</strong><small>Stretch dark and light pixels before manual enhancement.</small></span>
                <input type="checkbox" checked={localConfig.auto_contrast ?? true}
                  onChange={(e) => handleUpdateField('auto_contrast', e.target.checked)} />
              </label>
            </div>
            <div className={styles.formGroup}>
              <label>Auto-contrast cutoff <span>{Number(localConfig.cutoff ?? 1)}%</span></label>
              <input type="range" min="0" max="10" step="0.5" value={localConfig.cutoff ?? 1}
                onChange={(e) => handleUpdateField('cutoff', Number(e.target.value))} className={styles.range} />
            </div>
          </>
        );

      case 'document-parser': {
        const parseEntireDocument = localConfig.parse_entire_document ?? true;
        return (
          <>
            <div className={styles.infoCard}>
              <strong>Latest upstream document</strong>
              <span>
                The parser automatically uses the nearest processed file in the connected chain.
                A converted or cleaned document takes priority over the original import.
              </span>
            </div>

            <div className={styles.toggleGroup}>
              <label className={styles.toggleRow}>
                <span><strong>Parse entire document</strong><small>Read every PDF page, Word block, Excel sheet and row, CSV row, and text line.</small></span>
                <input type="checkbox" checked={parseEntireDocument}
                  onChange={(e) => handleUpdateField('parse_entire_document', e.target.checked)} />
              </label>
              <label className={styles.toggleRow}>
                <span><strong>Include tables</strong><small>Return Word tables and spreadsheet rows as structured JSON.</small></span>
                <input type="checkbox" checked={localConfig.include_tables ?? true}
                  onChange={(e) => handleUpdateField('include_tables', e.target.checked)} />
              </label>
              <label className={styles.toggleRow}>
                <span><strong>Include Word headers and footers</strong><small>Extract section headers, footers and their tables.</small></span>
                <input type="checkbox" checked={localConfig.include_headers_footers ?? true}
                  onChange={(e) => handleUpdateField('include_headers_footers', e.target.checked)} />
              </label>
              <label className={styles.toggleRow}>
                <span><strong>Preserve PDF page boundaries</strong><small>Add page separators to the full text result.</small></span>
                <input type="checkbox" checked={localConfig.preserve_page_breaks ?? true}
                  onChange={(e) => handleUpdateField('preserve_page_breaks', e.target.checked)} />
              </label>
              <label className={styles.toggleRow}>
                <span><strong>Create downloadable outputs</strong><small>Generate the complete TXT, structured JSON and ZIP bundle.</small></span>
                <input type="checkbox" checked={localConfig.create_downloads ?? true}
                  onChange={(e) => handleUpdateField('create_downloads', e.target.checked)} />
              </label>
            </div>

            <div className={styles.formGroup}>
              <label>Excel sheet (optional)</label>
              <input type="text" value={localConfig.sheet_name || ''}
                onChange={(e) => handleUpdateField('sheet_name', e.target.value)}
                placeholder="Leave empty to parse all sheets" className={styles.textInput} />
            </div>

            {!parseEntireDocument && (
              <div className={styles.formGroup}>
                <label>Maximum rows per Excel/CSV sheet</label>
                <input type="number" min="1" max="1000000" value={localConfig.max_rows_per_sheet ?? 5000}
                  onChange={(e) => handleUpdateField('max_rows_per_sheet', Number(e.target.value))} className={styles.textInput} />
                <span className={styles.helpText}>This limit is ignored while “Parse entire document” is enabled.</span>
              </div>
            )}

            <div className={styles.formGroup}>
              <label>Maximum file size (MB)</label>
              <input type="number" min="1" max="500" value={localConfig.max_file_size_mb ?? 50}
                onChange={(e) => handleUpdateField('max_file_size_mb', Number(e.target.value))} className={styles.textInput} />
            </div>
          </>
        );
      }

      case 'masker': {
        const categories = [
          { key: 'mask_emails', title: 'Emails', detail: 'Email addresses such as name@company.com.' },
          { key: 'mask_phones', title: 'Phone numbers', detail: 'Local and international phone numbers.' },
          { key: 'mask_ids', title: 'IDs and identifiers', detail: 'CIN, passport, SSN, matricule and labelled ID values.' },
          { key: 'mask_addresses', title: 'Postal addresses', detail: 'Common street and postal-address expressions.' },
          { key: 'mask_financial', title: 'Financial data', detail: 'IBANs and payment-card numbers.' },
          { key: 'mask_ip_addresses', title: 'IP addresses', detail: 'IPv4 addresses found in the document.' },
        ];
        return (
          <>
            <div className={styles.infoCard}>
              <strong>Permanent PDF masking</strong>
              <span>
                Sensitive values are removed from the PDF and replaced by solid boxes.
                The original file is kept unchanged and a new downloadable PDF is created.
              </span>
            </div>

            <div className={styles.toggleGroup}>
              {categories.map((category) => (
                <label className={styles.toggleRow} key={category.key}>
                  <span><strong>{category.title}</strong><small>{category.detail}</small></span>
                  <input
                    type="checkbox"
                    checked={localConfig[category.key] ?? true}
                    onChange={(e) => handleUpdateField(category.key, e.target.checked)}
                  />
                </label>
              ))}
            </div>

            <div className={styles.formGroup}>
              <label>Mask appearance</label>
              <select
                value={localConfig.mask_style || 'black'}
                onChange={(e) => handleUpdateField('mask_style', e.target.value)}
                className={styles.select}
              >
                <option value="black">Black boxes</option>
                <option value="white">White boxes</option>
              </select>
              <span className={styles.helpText}>The text underneath is permanently removed, not visually covered.</span>
            </div>

            <div className={styles.infoCard}>
              <strong>Output</strong>
              <span>A new PDF with the same pages and layout, plus a report containing counts only.</span>
            </div>
          </>
        );
      }

      case 'date-normalizer':
        return (
          <>
            <div className={styles.infoCard}>
              <strong>Date normalization</strong>
              <span>
                Convert dates found in the connected text or document to one consistent format.
                The input source shown above is used automatically.
              </span>
            </div>

            <div className={styles.formGroup}>
              <label>Date format</label>
              <select
                value={localConfig.output_format || 'YYYY-MM-DD'}
                onChange={(e) => handleUpdateField('output_format', e.target.value)}
                className={styles.select}
              >
                <option value="YYYY-MM-DD">YYYY-MM-DD — 2026-08-12</option>
                <option value="DD/MM/YYYY">DD/MM/YYYY — 12/08/2026</option>
                <option value="MM/DD/YYYY">MM/DD/YYYY — 08/12/2026</option>
              </select>
              <span className={styles.helpText}>When a time is present, it is kept automatically.</span>
            </div>

            <div className={styles.toggleGroup}>
              <label className={styles.toggleRow}>
                <span>
                  <strong>Replace dates in returned text</strong>
                  <small>Disable this option to keep the original text and return only the detected dates list.</small>
                </span>
                <input
                  type="checkbox"
                  checked={localConfig.replace_in_text ?? true}
                  onChange={(e) => handleUpdateField('replace_in_text', e.target.checked)}
                />
              </label>
            </div>

            <div className={styles.infoCard}>
              <strong>Outputs</strong>
              <span>Normalized text, structured date list, and source metadata.</span>
            </div>
          </>
        );

      case 'text-splitter':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Chunk Size: {localConfig.chunkSize || 512} characters</label>
              <input
                type="range"
                min="128"
                max="2048"
                step="32"
                value={localConfig.chunkSize || 512}
                onChange={(e) => handleUpdateField('chunkSize', parseInt(e.target.value))}
                className={styles.range}
              />
            </div>
            <div className={styles.formGroup}>
              <label>Chunk Overlap: {localConfig.overlap || 50} characters</label>
              <input
                type="range"
                min="0"
                max="500"
                step="10"
                value={localConfig.overlap || 50}
                onChange={(e) => handleUpdateField('overlap', parseInt(e.target.value))}
                className={styles.range}
              />
            </div>
          </>
        );

      case 'embedding':
        return (
          <div className={styles.formGroup}>
            <label>Embedding Model</label>
            <select
              value={localConfig.model || 'text-embedding-3-small'}
              onChange={(e) => handleUpdateField('model', e.target.value)}
              className={styles.select}
            >
              <option value="text-embedding-3-small">text-embedding-3-small (1536 dim)</option>
              <option value="text-embedding-3-large">text-embedding-3-large (3072 dim)</option>
              <option value="cohere-multilingual-v3">cohere-multilingual-v3</option>
            </select>
          </div>
        );

      case 'vector-store':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Collection Name</label>
              <input
                type="text"
                value={localConfig.collection || 'default'}
                onChange={(e) => handleUpdateField('collection', e.target.value)}
                className={styles.textInput}
              />
            </div>
            <div className={styles.formGroup}>
              <label>Distance Metric</label>
              <select
                value={localConfig.metric || 'cosine'}
                onChange={(e) => handleUpdateField('metric', e.target.value)}
                className={styles.select}
              >
                <option value="cosine">Cosine Similarity</option>
                <option value="l2">Euclidean Distance (L2)</option>
                <option value="ip">Inner Product</option>
              </select>
            </div>
          </>
        );

      case 'conditional':
        return (
          <div className={styles.formGroup}>
            <label>Conditional Branching Expression</label>
            <input
              type="text"
              value={localConfig.expression || ''}
              onChange={(e) => handleUpdateField('expression', e.target.value)}
              placeholder="e.g. has_handwriting == true"
              className={styles.textInput}
            />
            <span className={styles.helpText}>Branching routes output based on statement outcome.</span>
          </div>
        );

      default:
        return renderGenericConfigFields();
    }
  };

  const renderGenericConfigFields = () => {
    const fields = definition.configFields || [];
    if (!fields.length) {
      return <p className={styles.noParams}>No parameters required for this node.</p>;
    }

    return (
      <>
        {fields.map((field: any) => {
          const key = field.key;
          const value = localConfig[key] !== undefined ? localConfig[key] : field.default;
          const isTags = field.type === 'tags';
          const isSelect = field.type === 'select';
          const isNumber = field.type === 'number';
          const isJson = field.type === 'json';
          const isCheckbox = field.type === 'boolean' || field.type === 'checkbox';

          return (
            <div key={key} className={styles.formGroup}>
              <label>{field.label || key}</label>

              {isSelect && field.options ? (
                <select
                  value={value ?? ''}
                  onChange={(e) => handleUpdateField(key, e.target.value)}
                  className={styles.select}
                >
                  {field.options.map((opt: string) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : isTags && Array.isArray(field.default) ? (
                <div className={styles.pillsRow}>
                  {field.default.map((tag: string) => {
                    const currentTags: string[] = Array.isArray(value) ? value : [];
                    const active = currentTags.includes(tag);
                    return (
                      <button
                        key={tag}
                        onClick={() => {
                          const next = active
                            ? currentTags.filter((t: string) => t !== tag)
                            : [...currentTags, tag];
                          handleUpdateField(key, next);
                        }}
                        className={`${styles.pill} ${active ? styles.pillActive : ''}`}
                      >
                        {tag} {active ? '×' : '+'}
                      </button>
                    );
                  })}
                </div>
              ) : isTags && typeof field.default === 'string' ? (
                <input
                  type="text"
                  value={Array.isArray(value) ? value.join(',') : value ?? ''}
                  onChange={(e) => handleUpdateField(key, e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean))}
                  placeholder={field.placeholder || field.default}
                  className={styles.textInput}
                />
              ) : isNumber ? (
                <input
                  type="number"
                  value={value ?? ''}
                  onChange={(e) => handleUpdateField(key, e.target.value === '' ? '' : parseFloat(e.target.value))}
                  className={styles.textInput}
                  step="0.01"
                />
              ) : isJson ? (
                <textarea
                  value={typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                  onChange={(e) => handleUpdateField(key, e.target.value)}
                  rows={4}
                  className={styles.textarea}
                  placeholder={field.placeholder || '{"key": "value"}'}
                />
              ) : isCheckbox ? (
                <input
                  type="checkbox"
                  checked={Boolean(value)}
                  onChange={(e) => handleUpdateField(key, e.target.checked)}
                />
              ) : (
                <input
                  type="text"
                  value={value ?? ''}
                  onChange={(e) => handleUpdateField(key, e.target.value)}
                  placeholder={field.placeholder || field.description || ''}
                  className={styles.textInput}
                />
              )}

              {field.description && (
                <span className={styles.helpText}>{field.description}</span>
              )}
            </div>
          );
        })}
      </>
    );
  };

  const testRequiresWorkflow = incomingEdges.length > 0 || ['date-normalizer', 'document-parser', 'masker', 'comparison-agent'].includes(node.type);

  return (
    <aside className={styles.panel}>
      <div className={styles.panelHeader}>
        <div className={styles.nodeMeta}>
          <span className={styles.nodeIcon}>{definition.icon}</span>
          <div>
            <h3>{definition.name}</h3>
            <span>{definition.category} Node</span>
          </div>
        </div>
        <button className={styles.closeBtn} onClick={handleCancel}>×</button>
      </div>

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'parameters' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('parameters')}
        >
          Parameters
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'io' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('io')}
        >
          I/O Ports
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'test' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('test')}
        >
          Test Run
        </button>
        {nodeResult && (
          <button
            className={`${styles.tab} ${activeTab === 'results' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('results')}
          >
            Outputs
          </button>
        )}
      </div>

      <div className={styles.tabContent}>
        {activeTab === 'parameters' && (
          <div className={styles.fieldsScroll}>
            {renderInputSourceSummary()}
            {renderConfigFields()}
          </div>
        )}

        {activeTab === 'io' && (
          <div className={styles.ioList}>
            <h4>Input Connectors</h4>
            {(definition.inputs?.length ? definition.inputs : [{ name: 'input', label: 'Input', type: 'any' }]).map((port) => (
              <div className={styles.ioItem} key={`input-${port.name || port.label}`}>
                <span><i className={styles.inputDot} /> {port.label || port.name || 'Input'}</span>
                <span className={styles.ioType}>{port.type || 'any'}{port.required === false ? ' · optional' : ''}</span>
              </div>
            ))}

            <h4 style={{ marginTop: '20px' }}>Output Connectors</h4>
            {(definition.outputs?.length ? definition.outputs : [{ name: 'output', label: 'Output', type: 'any' }]).map((port) => (
              <div className={styles.ioItem} key={`output-${port.name || port.label}`}>
                <span><i className={styles.outputDot} /> {port.label || port.name || 'Output'}</span>
                <span className={styles.ioType}>{port.type || 'any'}</span>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'test' && (
          <div className={styles.testSection}>
            <div className={styles.infoCard}>
              <strong>{testRequiresWorkflow ? 'Run the connected workflow' : 'Real backend test'}</strong>
              <span>
                {testRequiresWorkflow
                  ? 'This node needs the input shown in the Parameters tab. Run the complete workflow so the latest upstream output is used.'
                  : 'The selected node runs alone with its current configuration.'}
              </span>
            </div>
            <button
              onClick={handleTestNode}
              disabled={testing || testRequiresWorkflow}
              className="btn-premium"
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {testRequiresWorkflow ? 'Use Run Workflow' : testing ? 'Running test…' : '▶ Test Node'}
            </button>
            <div className={styles.testLog}>
              <code>[CONFIG] {Object.keys(localConfig).length} parameter(s) ready</code>
              {inputSources.map((source) => (
                <code key={`${source.sourceNodeId}-${source.sourcePort}`}>
                  [INPUT] {source.filename || `${source.sourceNodeName} · ${source.sourcePortLabel}`}
                </code>
              ))}
              {testMessage && <code className={testResult?.status === 'success' ? styles.logSuccess : styles.logMessage}>{testMessage}</code>}
            </div>
          </div>
        )}

        {activeTab === 'results' && nodeResult && (
          <div className={styles.resultsSection}>
            {(() => {
              const outputs = nodeResult.outputs || {};
              const hasImage = outputs.image && typeof outputs.image === 'object';

              if (hasImage) {
                const imgData = outputs.image;
                const imgPath = imgData.path || '';
                const isBase64 = imgPath.startsWith('data:');
                const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
                const normalizedPath = String(imgPath).replaceAll('\\', '/').replace(/^\//, '');
                const imgSrc = isBase64 ? imgPath : `${API_BASE_URL}/${normalizedPath}`;

                return (
                  <div className={styles.imageResult}>
                    <div className={styles.imageWrapper}>
                      <img src={imgSrc} alt={imgData.filename || 'Output'} className={styles.previewImage} />
                    </div>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>File:</span>
                      <span className={styles.metaValue}>{imgData.filename || 'Unknown'}</span>
                    </div>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>Size:</span>
                      <span className={styles.metaValue}>{(imgData.size_bytes / 1024).toFixed(1)} KB</span>
                    </div>
                    <div className={styles.metaRow}>
                      <span className={styles.metaLabel}>Format:</span>
                      <span className={styles.metaValue}>{imgData.mime_type || 'image/png'}</span>
                    </div>
                    <a
                      href={imgSrc}
                      download={imgData.filename || 'denoised_document.png'}
                      className={`btn-premium ${styles.downloadLink}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      📥 Download Image
                    </a>
                  </div>
                );
              }

              if (node.type === 'masker' && outputs.document && typeof outputs.document === 'object') {
                const maskedDocument = outputs.document;
                const report = outputs.report && typeof outputs.report === 'object' ? outputs.report : {};
                const metadata = outputs.metadata && typeof outputs.metadata === 'object' ? outputs.metadata : {};
                const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
                const rawUrl = String(maskedDocument.download_url || maskedDocument.path || '');
                const normalizedPath = rawUrl.replaceAll('\\', '/');
                const href = normalizedPath.startsWith('http')
                  ? normalizedPath
                  : normalizedPath.startsWith('/')
                    ? `${API_BASE_URL}${normalizedPath}`
                    : `${API_BASE_URL}/${normalizedPath.replace(/^\//, '')}`;
                const entries = Object.entries(report.by_type || {});

                return (
                  <div className={styles.textResult}>
                    <div className={styles.resultHeader}>
                      <h4>Masked PDF</h4>
                      <span>{Number(report.total_masked || 0)} item{Number(report.total_masked || 0) === 1 ? '' : 's'} masked</span>
                    </div>

                    <div className={`${styles.completenessBanner} ${styles.complete}`}>
                      <strong>✓ PDF created</strong>
                      <span>{maskedDocument.filename || 'masked-document.pdf'}</span>
                    </div>

                    <div className={styles.downloadGrid}>
                      <a
                        href={href}
                        download={maskedDocument.filename || 'masked-document.pdf'}
                        className={`btn-premium ${styles.downloadLink}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        📥 Download masked PDF
                      </a>
                      <a
                        href={href}
                        className={`btn-premium ${styles.downloadLink}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        ↗ Open PDF
                      </a>
                    </div>

                    <div className={styles.metadataGrid}>
                      <div><span>masked items</span><strong>{String(report.total_masked || 0)}</strong></div>
                      <div><span>redaction areas</span><strong>{String(report.redaction_areas || 0)}</strong></div>
                      <div><span>pages with masks</span><strong>{String(report.pages_with_masks || 0)}</strong></div>
                      <div><span>file size</span><strong>{maskedDocument.size_bytes ? `${(Number(maskedDocument.size_bytes) / 1024).toFixed(1)} KB` : '—'}</strong></div>
                      {entries.map(([key, value]) => (
                        <div key={key}><span>{key.replaceAll('_', ' ').toLowerCase()}</span><strong>{String(value)}</strong></div>
                      ))}
                    </div>

                    <details className={styles.payloadDetails}>
                      <summary>Masking report</summary>
                      <pre className={styles.codeBlock}>{JSON.stringify({ report, metadata }, null, 2)}</pre>
                    </details>
                  </div>
                );
              }

              if (node.type === 'comparison-agent' && outputs.comparison && typeof outputs.comparison === 'object') {
                const comparison = outputs.comparison as any;
                const summary = outputs.summary && typeof outputs.summary === 'object'
                  ? outputs.summary as any
                  : comparison.summary || {};
                const changes = Array.isArray(comparison.changes) ? comparison.changes : [];
                const original = comparison.original || {};
                const revised = comparison.revised || {};
                const downloads = outputs.downloads && typeof outputs.downloads === 'object' ? outputs.downloads : {};
                const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
                const downloadItems = [
                  { key: 'html', label: 'Open side-by-side report', icon: '↔️', open: true },
                  { key: 'json', label: 'Download comparison JSON', icon: '🧾' },
                  { key: 'diff', label: 'Download text diff', icon: '📝' },
                  { key: 'bundle', label: 'Download complete ZIP', icon: '📦' },
                ].flatMap((item) => {
                  const descriptor = downloads[item.key];
                  if (!descriptor?.download_url) return [];
                  const href = String(descriptor.download_url).startsWith('http')
                    ? descriptor.download_url
                    : `${API_BASE_URL}${descriptor.download_url}`;
                  return [{ ...item, descriptor, href }];
                });
                const similarityPercent = Number(summary.similarity_percent || 0);

                return (
                  <div className={styles.comparisonResults}>
                    <div className={styles.resultHeader}>
                      <h4>Document comparison</h4>
                      <span>{changes.length} change block{changes.length === 1 ? '' : 's'}</span>
                    </div>

                    <div className={styles.comparisonDocuments}>
                      <div className={styles.comparisonDocumentCard}>
                        <span>Original</span>
                        <strong title={String(original.filename || '')}>{String(original.filename || 'Original document')}</strong>
                        <small>{Number(original.line_count || 0).toLocaleString()} lines</small>
                      </div>
                      <div className={styles.comparisonArrow}>→</div>
                      <div className={styles.comparisonDocumentCard}>
                        <span>Compared</span>
                        <strong title={String(revised.filename || '')}>{String(revised.filename || 'Document to compare')}</strong>
                        <small>{Number(revised.line_count || 0).toLocaleString()} lines</small>
                      </div>
                    </div>

                    <div className={`${styles.comparisonSimilarity} ${summary.identical ? styles.comparisonIdentical : ''}`}>
                      <div>
                        <strong>{similarityPercent.toFixed(1)}%</strong>
                        <span>text similarity</span>
                      </div>
                      <p>{summary.identical ? 'The two documents are identical with the selected settings.' : 'Differences were found and are listed below.'}</p>
                    </div>

                    <div className={styles.comparisonStats}>
                      <div><span>Added</span><strong className={styles.statAdded}>{String(summary.added_units || 0)}</strong></div>
                      <div><span>Removed</span><strong className={styles.statRemoved}>{String(summary.removed_units || 0)}</strong></div>
                      <div><span>Modified</span><strong className={styles.statModified}>{String(summary.modified_units || 0)}</strong></div>
                      <div><span>Unchanged</span><strong>{String(summary.unchanged_units || 0)}</strong></div>
                    </div>

                    {changes.length === 0 ? (
                      <div className={styles.noChanges}>✓ No difference detected.</div>
                    ) : (
                      <div className={styles.comparisonChanges}>
                        {changes.slice(0, 150).map((change: any, index: number) => {
                          const changeType = String(change.type || 'modified');
                          const badgeClass = changeType === 'added'
                            ? styles.changeBadgeAdded
                            : changeType === 'removed'
                              ? styles.changeBadgeRemoved
                              : styles.changeBadgeModified;
                          const originalRange = change.original_start
                            ? `${change.original_start}${change.original_end && change.original_end !== change.original_start ? `–${change.original_end}` : ''}`
                            : '—';
                          const revisedRange = change.revised_start
                            ? `${change.revised_start}${change.revised_end && change.revised_end !== change.revised_start ? `–${change.revised_end}` : ''}`
                            : '—';
                          return (
                            <section className={styles.changeCard} key={String(change.id || index)}>
                              <div className={styles.changeHeader}>
                                <span className={badgeClass}>{changeType}</span>
                                <small>Original {originalRange} · Compared {revisedRange}</small>
                              </div>
                              <div className={styles.changeBody}>
                                {changeType !== 'added' && (
                                  <div className={`${styles.changeColumn} ${styles.changeOld}`}>
                                    <span>Original</span>
                                    <pre>{String(change.original_text || '')}</pre>
                                  </div>
                                )}
                                {changeType !== 'removed' && (
                                  <div className={`${styles.changeColumn} ${styles.changeNew}`}>
                                    <span>Compared</span>
                                    <pre>{String(change.revised_text || '')}</pre>
                                  </div>
                                )}
                              </div>
                              {changeType === 'modified' && Array.isArray(change.inline_changes) && change.inline_changes.length > 0 && (
                                <div className={styles.inlineDiff}>
                                  {change.inline_changes.map((segment: any, segmentIndex: number) => (
                                    <span
                                      key={`${segmentIndex}-${segment.type}`}
                                      className={segment.type === 'added'
                                        ? styles.inlineAdded
                                        : segment.type === 'removed'
                                          ? styles.inlineRemoved
                                          : styles.inlineEqual}
                                    >
                                      {String(segment.text || '')}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </section>
                          );
                        })}
                        {changes.length > 150 && (
                          <span className={styles.helpText}>Only the first 150 change blocks are displayed. Download the complete report below.</span>
                        )}
                      </div>
                    )}

                    {downloadItems.length > 0 && (
                      <div className={styles.downloadGrid}>
                        {downloadItems.map((item) => (
                          <a
                            key={item.key}
                            href={item.href}
                            download={item.open ? undefined : item.descriptor.filename}
                            className={`btn-premium ${styles.downloadLink}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {item.icon} {item.label}
                          </a>
                        ))}
                      </div>
                    )}

                    <details className={styles.payloadDetails}>
                      <summary>Complete comparison payload</summary>
                      <pre className={styles.codeBlock}>{JSON.stringify({ comparison, metadata: outputs.metadata }, null, 2)}</pre>
                    </details>
                  </div>
                );
              }

              if (node.type === 'topic-clustering' && Array.isArray(outputs.clusters)) {
                const clusters = outputs.clusters as any[];
                const metadata = outputs.metadata && typeof outputs.metadata === 'object' ? outputs.metadata : {};
                const downloads = outputs.downloads && typeof outputs.downloads === 'object' ? outputs.downloads : {};
                const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
                const downloadItems = [
                  { key: 'json', label: 'Download clusters JSON', icon: '🧾' },
                  { key: 'csv', label: 'Download assignments CSV', icon: '📊' },
                  { key: 'bundle', label: 'Download complete ZIP', icon: '📦' },
                ].flatMap((item) => {
                  const descriptor = downloads[item.key];
                  if (!descriptor?.download_url) return [];
                  const href = String(descriptor.download_url).startsWith('http')
                    ? descriptor.download_url
                    : `${API_BASE_URL}${descriptor.download_url}`;
                  return [{ ...item, descriptor, href }];
                });

                return (
                  <div className={styles.clusterResults}>
                    <div className={styles.resultHeader}>
                      <h4>Topic clusters</h4>
                      <span>{clusters.length} cluster{clusters.length === 1 ? '' : 's'} · {Number(metadata.clustered_document_count || 0)} documents</span>
                    </div>

                    <div className={`${styles.completenessBanner} ${styles.complete}`}>
                      <strong>✓ Corpus clustered</strong>
                      <span>
                        {String(metadata.corpus_name || 'Document corpus')} · {String(metadata.cluster_count_mode || 'automatic')} cluster count
                        {metadata.quality_score != null ? ` · quality ${Number(metadata.quality_score).toFixed(3)}` : ''}
                      </span>
                    </div>

                    <div className={styles.clusterList}>
                      {clusters.map((cluster: any) => (
                        <section className={styles.clusterCard} key={String(cluster.cluster_id)}>
                          <div className={styles.clusterHeader}>
                            <div>
                              <span>Cluster {String(cluster.cluster_id)}</span>
                              <strong>{String(cluster.label || `Topic ${cluster.cluster_id}`)}</strong>
                            </div>
                            <b>{Number(cluster.document_count || 0)}</b>
                          </div>
                          {Array.isArray(cluster.keywords) && cluster.keywords.length > 0 && (
                            <div className={styles.clusterKeywords}>
                              {cluster.keywords.slice(0, 5).map((keyword: string) => <span key={keyword}>{keyword}</span>)}
                            </div>
                          )}
                          <div className={styles.clusterDocuments}>
                            {(Array.isArray(cluster.documents) ? cluster.documents : []).map((document: any, index: number) => (
                              <div key={String(document.file_id || `${document.filename}-${index}`)}>
                                <span className={styles.clusterDocumentIcon}>📄</span>
                                <div>
                                  <strong title={String(document.relative_path || document.filename)}>
                                    {String(document.relative_path || document.filename || 'document')}
                                  </strong>
                                  <small>{Math.round(Number(document.similarity || 0) * 100)}% similarity</small>
                                </div>
                              </div>
                            ))}
                          </div>
                        </section>
                      ))}
                    </div>

                    {downloadItems.length > 0 && (
                      <div className={styles.downloadGrid}>
                        {downloadItems.map((item) => (
                          <a
                            key={item.key}
                            href={item.href}
                            download={item.descriptor.filename}
                            className={`btn-premium ${styles.downloadLink}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {item.icon} {item.label}
                          </a>
                        ))}
                      </div>
                    )}

                    {Array.isArray(metadata.skipped_documents) && metadata.skipped_documents.length > 0 && (
                      <details className={styles.payloadDetails}>
                        <summary>{metadata.skipped_documents.length} skipped document{metadata.skipped_documents.length === 1 ? '' : 's'}</summary>
                        <pre className={styles.codeBlock}>{JSON.stringify(metadata.skipped_documents, null, 2)}</pre>
                      </details>
                    )}
                    <details className={styles.payloadDetails}>
                      <summary>Complete clustering payload</summary>
                      <pre className={styles.codeBlock}>{JSON.stringify({ clusters, assignments: outputs.assignments, metadata }, null, 2)}</pre>
                    </details>
                  </div>
                );
              }

              if (typeof outputs.normalized_text === 'string') {
                const dates = Array.isArray(outputs.dates) ? outputs.dates : [];
                return (
                  <div className={styles.textResult}>
                    <div className={styles.resultHeader}>
                      <h4>Normalized text</h4>
                      <span>{dates.length} date{dates.length === 1 ? '' : 's'}</span>
                    </div>
                    <pre className={styles.textPreview} dir="auto">{outputs.normalized_text || 'No text returned.'}</pre>
                    <div className={styles.dateResultList}>
                      {dates.length === 0 && <span className={styles.helpText}>No date expression was detected.</span>}
                      {dates.map((date: any, index: number) => (
                        <div className={styles.dateResultItem} key={`${date.start ?? index}-${date.original ?? index}`}>
                          <div>
                            <span className={styles.dateOriginal} dir="auto">{String(date.original || '')}</span>
                            <span className={styles.dateArrow}>→</span>
                            <strong>{String(date.normalized || '')}</strong>
                          </div>
                          <small>
                            {date.detected_language || 'auto'} · {date.calendar || 'gregorian'}
                            {date.is_relative ? ' · relative' : ''}
                          </small>
                        </div>
                      ))}
                    </div>
                    {outputs.metadata && (
                      <div className={styles.metadataGrid}>
                        {Object.entries(outputs.metadata).slice(0, 10).map(([key, value]) => (
                          <div key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{String(value)}</strong></div>
                        ))}
                      </div>
                    )}
                    <details className={styles.payloadDetails}>
                      <summary>Full normalized dates payload</summary>
                      <pre className={styles.codeBlock}>{JSON.stringify(dates, null, 2)}</pre>
                    </details>
                  </div>
                );
              }

              if (typeof outputs.text === 'string') {
                const previewLimit = 50000;
                const previewText = outputs.text.length > previewLimit
                  ? `${outputs.text.slice(0, previewLimit)}\n\n… Preview stopped at ${previewLimit.toLocaleString()} characters. Download the full output below.`
                  : outputs.text;
                const downloads = outputs.downloads && typeof outputs.downloads === 'object'
                  ? outputs.downloads
                  : {};
                const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
                const downloadItems = [
                  { key: 'text', label: 'Download full TXT', icon: '📄' },
                  { key: 'json', label: 'Download structured JSON', icon: '🧾' },
                  { key: 'bundle', label: 'Download complete ZIP', icon: '📦' },
                ].flatMap((item) => {
                  const descriptor = downloads[item.key];
                  if (!descriptor?.download_url) return [];
                  const href = String(descriptor.download_url).startsWith('http')
                    ? descriptor.download_url
                    : `${API_BASE_URL}${descriptor.download_url}`;
                  return [{ ...item, descriptor, href }];
                });

                return (
                  <div className={styles.textResult}>
                    <div className={styles.resultHeader}>
                      <h4>Extracted Content</h4>
                      <span>{outputs.text.length.toLocaleString()} characters</span>
                    </div>

                    {outputs.metadata && (
                      <div className={`${styles.completenessBanner} ${outputs.metadata.complete ? styles.complete : styles.truncated}`}>
                        <strong>{outputs.metadata.complete ? '✓ Complete document parsed' : '⚠ Limited result'}</strong>
                        <span>
                          {outputs.metadata.source_node_type
                            ? `Latest version from ${outputs.metadata.source_node_type} (${outputs.metadata.source_output_port || 'artifact'}).`
                            : `Source: ${outputs.metadata.selected_source || 'connected document'}.`}
                        </span>
                      </div>
                    )}

                    <div className={styles.previewLabel}>
                      <strong>On-screen preview</strong>
                      <span>The downloadable files always contain the complete parser result.</span>
                    </div>
                    <pre className={styles.textPreview}>{previewText || 'No textual content extracted.'}</pre>

                    {downloadItems.length > 0 && (
                      <div className={styles.downloadGrid}>
                        {downloadItems.map((item) => (
                          <a
                            key={item.key}
                            href={item.href}
                            download={item.descriptor.filename}
                            className={`btn-premium ${styles.downloadLink}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {item.icon} {item.label}
                          </a>
                        ))}
                      </div>
                    )}

                    {outputs.metadata && (
                      <div className={styles.metadataGrid}>
                        {Object.entries(outputs.metadata).slice(0, 14).map(([key, value]) => (
                          <div key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{String(value)}</strong></div>
                        ))}
                      </div>
                    )}
                    <details className={styles.payloadDetails}>
                      <summary>Structured data preview</summary>
                      <pre className={styles.codeBlock}>{JSON.stringify(outputs.data || {}, null, 2).slice(0, 100000)}</pre>
                    </details>
                  </div>
                );
              }

              return (
                <div className={styles.jsonResult}>
                  <h4>Outputs Payload</h4>
                  <pre className={styles.codeBlock}>
                    {JSON.stringify(outputs, null, 2)}
                  </pre>
                </div>
              );
            })()}
          </div>
        )}
      </div>

      <div className={styles.panelActions}>
        <button onClick={handleCancel} className="btn-secondary">Cancel</button>
        <button onClick={handleApply} className="btn-premium">Apply Configuration</button>
      </div>
    </aside>
  );
}