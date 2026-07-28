import { useState, useEffect, useRef } from 'react';
import { useFlowStore } from '../../store/flowStore';
import { getNodeDefinition } from '../../config/nodeDefinitions';
import { uploadDocument } from '../../services/backendApi';
import { useExecutionStore } from '../../store/executionStore';
import styles from './NodeConfigPanel.module.css';

export function NodeConfigPanel() {
  const { selectedNodeId, nodes, edges, updateNodeConfig, selectNode } = useFlowStore();
  const { executionResults } = useExecutionStore();
  const [activeTab, setActiveTab] = useState<'parameters' | 'io' | 'test' | 'results'>('parameters');
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);

  const node = nodes.find((n) => n.id === selectedNodeId);
  const definition = node ? getNodeDefinition(node.type) : null;

  let nodeResult = null;
  if (node && executionResults) {
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
    }
  }, [selectedNodeId, node]);

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
        uploaded_at: new Date().toISOString(),
      };
      setLocalConfig(updatedConfig);
      updateNodeConfig(node.id, updatedConfig);
      setUploadMessage(`Uploaded ${payload.filename} successfully.`);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const renderConfigFields = () => {
    switch (node.type) {
      case 'ocr-node':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Language</label>
              <select
                value={localConfig.language || 'eng'}
                onChange={(e) => handleUpdateField('language', e.target.value)}
                className={styles.select}
              >
                <option value="eng">English</option>
                <option value="fra">French</option>
                <option value="ara">Arabic</option>
                <option value="eng+fra">English + French</option>
                <option value="eng+ara">English + Arabic</option>
                <option value="fra+ara">French + Arabic</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>PDF Resolution: {localConfig.dpi || 300} DPI</label>
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
              <label>File ID (standalone mode)</label>
              <input
                type="text"
                value={String(localConfig.file_id || '')}
                onChange={(e) => handleUpdateField('file_id', e.target.value)}
                className={styles.textInput}
                placeholder="From /api/documents/upload"
              />
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

      case 'document-upload':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Select a document to upload</label>
              <input
                type="file"
                onChange={handleUploadDocument}
                className={styles.textInput}
              />
              {uploading && <p className={styles.helpText}>Uploading…</p>}
              {uploadMessage && <p className={styles.helpText}>{uploadMessage}</p>}
              {localConfig.filename && (
                <div className={styles.metaRow} style={{ marginTop: '8px', borderBottom: 'none' }}>
                  <span className={styles.metaLabel}>Remembered File:</span>
                  <span className={styles.metaValue} style={{ color: '#10b981' }}>{localConfig.filename}</span>
                </div>
              )}
            </div>
            <div className={styles.formGroup}>
              <label>Stored File ID</label>
              <input
                type="text"
                value={String(localConfig.file_id || '')}
                onChange={(e) => handleUpdateField('file_id', e.target.value)}
                className={styles.textInput}
                placeholder="Assigned by backend"
              />
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

      case 'handwriting-ocr':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Language</label>
              <select
                value={localConfig.language || 'ar'}
                onChange={(e) => handleUpdateField('language', e.target.value)}
                className={styles.select}
              >
                <option value="ar">Arabic</option>
                <option value="fr">French</option>
                <option value="en">English</option>
                <option value="ar,en">Arabic + English</option>
                <option value="fr,en">French + English</option>
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
                value={(localConfig.allowed_extensions || ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']).join(', ')}
                onChange={(e) => handleUpdateField('allowed_extensions', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
                className={styles.textInput}
                placeholder=".png, .jpg"
              />
            </div>
            <div className={styles.formGroup}>
              <label>File ID (standalone mode)</label>
              <input
                type="text"
                value={String(localConfig.file_id || '')}
                onChange={(e) => handleUpdateField('file_id', e.target.value)}
                className={styles.textInput}
                placeholder="From /api/documents/upload"
              />
            </div>
          </>
        );

      case 'regex-extractor':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Template</label>
              <select
                value={localConfig.template || 'generic'}
                onChange={(e) => handleUpdateField('template', e.target.value)}
                className={styles.select}
              >
                <option value="generic">Generic</option>
                <option value="invoice_fr">Invoice (French)</option>
                <option value="invoice_ar">Invoice (Arabic)</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Language</label>
              <select
                value={localConfig.language || 'fr'}
                onChange={(e) => handleUpdateField('language', e.target.value)}
                className={styles.select}
              >
                <option value="fr">French</option>
                <option value="en">English</option>
                <option value="ar">Arabic</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Custom Patterns (JSON)</label>
              <textarea
                value={localConfig.custom_patterns || '[]'}
                onChange={(e) => handleUpdateField('custom_patterns', e.target.value)}
                className={styles.textarea}
                rows={6}
                placeholder='[{"key":"invoice_number","pattern":"INV-\\d+","label":"Invoice #"}]'
              />
              <span className={styles.helpText}>Used when template is &quot;custom&quot;</span>
            </div>
            <div className={styles.formGroup}>
              <label>File ID (standalone mode)</label>
              <input
                type="text"
                value={String(localConfig.file_id || '')}
                onChange={(e) => handleUpdateField('file_id', e.target.value)}
                className={styles.textInput}
                placeholder="From /api/documents/upload"
              />
            </div>
          </>
        );

      case 'semantic-extractor':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Document Type</label>
              <select
                value={localConfig.document_type || 'generic'}
                onChange={(e) => handleUpdateField('document_type', e.target.value)}
                className={styles.select}
              >
                <option value="generic">Generic</option>
                <option value="invoice_fr">Invoice (French)</option>
                <option value="invoice_ar">Invoice (Arabic)</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Language</label>
              <select
                value={localConfig.language || 'fr'}
                onChange={(e) => handleUpdateField('language', e.target.value)}
                className={styles.select}
              >
                <option value="fr">French</option>
                <option value="en">English</option>
                <option value="ar">Arabic</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Custom Fields (JSON)</label>
              <textarea
                value={localConfig.fields || '[]'}
                onChange={(e) => handleUpdateField('fields', e.target.value)}
                className={styles.textarea}
                rows={6}
                placeholder='[{"key":"date","label":"Date","description":"Document date"}]'
              />
              <span className={styles.helpText}>Used when document type is &quot;custom&quot;</span>
            </div>
            <div className={styles.formGroup}>
              <label>File ID (standalone mode)</label>
              <input
                type="text"
                value={String(localConfig.file_id || '')}
                onChange={(e) => handleUpdateField('file_id', e.target.value)}
                className={styles.textInput}
                placeholder="From /api/documents/upload"
              />
            </div>
          </>
        );

      case 'text-cleaner':
        return (
          <>
            <div className={styles.toggleGroup}>
              <div className={styles.toggleRow}>
                <span>Fix Hyphenation</span>
                <input
                  type="checkbox"
                  checked={localConfig.fix_hyphenation ?? true}
                  onChange={(e) => handleUpdateField('fix_hyphenation', e.target.checked)}
                />
              </div>
              <div className={styles.toggleRow}>
                <span>Collapse Whitespace</span>
                <input
                  type="checkbox"
                  checked={localConfig.collapse_whitespace ?? true}
                  onChange={(e) => handleUpdateField('collapse_whitespace', e.target.checked)}
                />
              </div>
              <div className={styles.toggleRow}>
                <span>Strip Special Chars</span>
                <input
                  type="checkbox"
                  checked={localConfig.strip_special_chars ?? false}
                  onChange={(e) => handleUpdateField('strip_special_chars', e.target.checked)}
                />
              </div>
              <div className={styles.toggleRow}>
                <span>Normalize Dates</span>
                <input
                  type="checkbox"
                  checked={localConfig.normalize_dates ?? false}
                  onChange={(e) => handleUpdateField('normalize_dates', e.target.checked)}
                />
              </div>
            </div>
            <div className={styles.formGroup}>
              <label>Casing</label>
              <select
                value={localConfig.normalize_casing || 'none'}
                onChange={(e) => handleUpdateField('normalize_casing', e.target.value)}
                className={styles.select}
              >
                <option value="none">Keep as-is</option>
                <option value="lower">lowercase</option>
                <option value="upper">UPPERCASE</option>
                <option value="title">Title Case</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Date Output Format</label>
              <input
                type="text"
                value={localConfig.date_output_format || '%Y-%m-%d'}
                onChange={(e) => handleUpdateField('date_output_format', e.target.value)}
                className={styles.textInput}
                placeholder="%Y-%m-%d"
              />
            </div>
            <div className={styles.formGroup}>
              <label>File ID (standalone mode)</label>
              <input
                type="text"
                value={String(localConfig.file_id || '')}
                onChange={(e) => handleUpdateField('file_id', e.target.value)}
                className={styles.textInput}
                placeholder="From /api/documents/upload"
              />
            </div>
          </>
        );

      case 'document-structure-analyzer':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Partition Strategy</label>
              <select
                value={localConfig.strategy || 'auto'}
                onChange={(e) => handleUpdateField('strategy', e.target.value)}
                className={styles.select}
              >
                <option value="auto">Auto</option>
                <option value="fast">Fast (no OCR)</option>
                <option value="hi_res">High Resolution (Tesseract)</option>
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
                value={(localConfig.allowed_extensions || ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']).join(', ')}
                onChange={(e) => handleUpdateField('allowed_extensions', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
                className={styles.textInput}
                placeholder=".pdf, .png, .jpg"
              />
            </div>
            <div className={styles.formGroup}>
              <label>File ID (standalone mode)</label>
              <input
                type="text"
                value={String(localConfig.file_id || '')}
                onChange={(e) => handleUpdateField('file_id', e.target.value)}
                className={styles.textInput}
                placeholder="From /api/documents/upload"
              />
            </div>
          </>
        );

      case 'gap-checker':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Checklist Template</label>
              <select
                value={localConfig.template || 'generic'}
                onChange={(e) => handleUpdateField('template', e.target.value)}
                className={styles.select}
              >
                <option value="generic">Generic</option>
                <option value="invoice_fr">Invoice (French)</option>
                <option value="claim_dossier">Claim Dossier</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Language</label>
              <select
                value={localConfig.language || 'fr'}
                onChange={(e) => handleUpdateField('language', e.target.value)}
                className={styles.select}
              >
                <option value="fr">French</option>
                <option value="en">English</option>
                <option value="ar">Arabic</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Strictness Threshold: {localConfig.strictness_threshold ?? 0.85}</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={localConfig.strictness_threshold ?? 0.85}
                onChange={(e) => handleUpdateField('strictness_threshold', parseFloat(e.target.value))}
                className={styles.range}
              />
              <div className={styles.rangeLabels}>
                <span>0 (lenient)</span>
                <span>1 (strict)</span>
              </div>
            </div>
            <div className={styles.formGroup}>
              <label>Evaluation Mode</label>
              <select
                value={localConfig.evaluation_mode || 'both'}
                onChange={(e) => handleUpdateField('evaluation_mode', e.target.value)}
                className={styles.select}
              >
                <option value="deterministic_only">Deterministic Only (regex)</option>
                <option value="semantic">Semantic (LLM)</option>
                <option value="both">Both (regex + LLM)</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Custom Checklist (JSON)</label>
              <textarea
                value={localConfig.custom_checklist || '[]'}
                onChange={(e) => handleUpdateField('custom_checklist', e.target.value)}
                className={styles.textarea}
                rows={6}
                placeholder='[{"key":"date","label":"Date","required":true}]'
              />
            </div>
          </>
        );

      case 'prompt-builder':
        return (
          <>
            <div className={styles.formGroup}>
              <label>Prompt Template</label>
              <select
                value={localConfig.prompt_template || 'qa_with_sources'}
                onChange={(e) => handleUpdateField('prompt_template', e.target.value)}
                className={styles.select}
              >
                <option value="qa_with_sources">Q&A with Sources</option>
                <option value="qa_concise">Q&A Concise</option>
                <option value="summary">Summary</option>
                <option value="analysis">Analysis</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Language</label>
              <select
                value={localConfig.language || 'fr'}
                onChange={(e) => handleUpdateField('language', e.target.value)}
                className={styles.select}
              >
                <option value="fr">French</option>
                <option value="en">English</option>
                <option value="ar">Arabic</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label>Custom Template</label>
              <textarea
                value={localConfig.custom_template || ''}
                onChange={(e) => handleUpdateField('custom_template', e.target.value)}
                className={styles.textarea}
                rows={4}
                placeholder="Use {'{'}chunks{'}'}, {'{'}context{'}'}, {'{'}question{'}'} placeholders"
              />
              <span className={styles.helpText}>Used when template is &quot;Custom&quot;</span>
            </div>
            <div className={styles.formGroup}>
              <label>System Prompt</label>
              <textarea
                value={localConfig.system_prompt || ''}
                onChange={(e) => handleUpdateField('system_prompt', e.target.value)}
                className={styles.textarea}
                rows={3}
                placeholder="Optional system instruction"
              />
            </div>
          </>
        );

      case 'feedback-collector':
        return (
          <div className={styles.formGroup}>
            <label>Storage Path</label>
            <input
              type="text"
              value={localConfig.storage_path || 'data/feedback'}
              onChange={(e) => handleUpdateField('storage_path', e.target.value)}
              className={styles.textInput}
              placeholder="data/feedback"
            />
            <span className={styles.helpText}>Directory where feedback entries are stored</span>
          </div>
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
                <option value="auto">Auto (contrast + binarize)</option>
                <option value="pil-median">Median Filter (denoise)</option>
                <option value="contrast">Contrast Enhancement</option>
                <option value="binarize">Binarize (threshold)</option>
                <option value="sharpen">Sharpen</option>
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
        return (
          <p className={styles.noParams}>No parameters required for this node category.</p>
        );
    }
  };

  const [panelWidth, setPanelWidth] = useState(320);
  const [isResizing, setIsResizing] = useState(false);
  const resizeStartRef = useRef(0);

  useEffect(() => {
    if (!isResizing) return;
    const onMove = (e: globalThis.MouseEvent) => {
      const delta = resizeStartRef.current - e.clientX;
      setPanelWidth(prev => Math.min(Math.max(prev + delta, 240), 500));
      resizeStartRef.current = e.clientX;
    };
    const onUp = () => setIsResizing(false);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [isResizing]);

  return (
    <aside className={styles.panel} style={{ width: panelWidth }}>
      <div
        className={styles.resizeHandle}
        onMouseDown={(e) => {
          e.preventDefault();
          resizeStartRef.current = e.clientX;
          setIsResizing(true);
        }}
      />
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
            {renderConfigFields()}
          </div>
        )}

        {activeTab === 'io' && (
          <div className={styles.ioList}>
            <h4>Input Connectors ({definition.inputs?.length || 0})</h4>
            {(definition.inputs && definition.inputs.length > 0
              ? definition.inputs.map(input => (
                  <div key={input.name} className={styles.ioItem}>
                    <span>⬇️ {input.label || input.name}{input.required ? ' *' : ''}</span>
                    <span className={styles.ioType}>{input.type || 'any'}</span>
                  </div>
                ))
              : (
                <div className={styles.ioItem}>
                  <span>⬇️ Input</span>
                  <span className={styles.ioType}>any</span>
                </div>
              )
            )}
            <h4 style={{ marginTop: '20px' }}>Output Connectors ({definition.outputs?.length || 0})</h4>
            {(definition.outputs && definition.outputs.length > 0
              ? definition.outputs.map(output => (
                  <div key={output.name} className={styles.ioItem}>
                    <span>📤 {output.label || output.name}</span>
                    <span className={styles.ioType}>{output.type || 'any'}</span>
                  </div>
                ))
              : (
                <div className={styles.ioItem}>
                  <span>📤 Output</span>
                  <span className={styles.ioType}>any</span>
                </div>
              )
            )}
          </div>
        )}

        {activeTab === 'test' && (
          <div className={styles.testSection}>
            <p>Mock execution of this node individually with active configuration settings.</p>
            <button className="btn-premium" style={{ width: '100%', justifyContent: 'center' }}>
              Test Node
            </button>
            <div className={styles.testLog}>
              <code>[INFO] Node initialised...</code>
              <code>[INFO] Connection verified...</code>
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
                const imgSrc = isBase64 ? imgPath : `${API_BASE_URL}/${imgPath}`;

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