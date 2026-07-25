import { useState, useEffect } from 'react';
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
            {renderConfigFields()}
          </div>
        )}

        {activeTab === 'io' && (
          <div className={styles.ioList}>
            <h4>Input Connectors</h4>
            <div className={styles.ioItem}>
              <span>⬇️ Input Port</span>
              <span className={styles.ioType}>Document Object</span>
            </div>

            <h4 style={{ marginTop: '20px' }}>Output Connectors</h4>
            <div className={styles.ioItem}>
              <span>📤 Output Port</span>
              <span className={styles.ioType}>Extracted Text / JSON</span>
            </div>
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