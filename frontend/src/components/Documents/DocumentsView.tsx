import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react';
import {
  deleteDocument,
  documentDownloadUrl,
  importDocumentFromUrl,
  listDocuments,
  uploadDocuments,
} from '../../services/backendApi';
import { useFlowStore } from '../../store/flowStore';
import { useWorkflowStore } from '../../store/workflowStore';
import type { AppRoute, DocumentRecord } from '../../types';
import styles from './DocumentsView.module.css';

interface DocumentsViewProps {
  onNavigate: (route: AppRoute) => void;
}

type ImportSource = 'local' | 'cloud-url' | 'gdrive' | 'onedrive';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function fileIcon(document: DocumentRecord): string {
  if (document.mime_type.startsWith('image/')) return '🖼️';
  if (document.extension === '.pdf') return '📕';
  if (['.xlsx', '.xlsm', '.csv'].includes(document.extension)) return '📗';
  if (document.extension === '.docx') return '📘';
  return '📄';
}

export function DocumentsView({ onNavigate }: DocumentsViewProps) {
  const [subView, setSubView] = useState<'library' | 'import'>('library');
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentRecord | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<ImportSource>('local');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [cloudUrl, setCloudUrl] = useState('');
  const [cloudFilename, setCloudFilename] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const refreshRequestIdRef = useRef(0);

  const resetFlow = useFlowStore((state) => state.resetFlow);
  const addNode = useFlowStore((state) => state.addNode);
  const createWorkflow = useWorkflowStore((state) => state.createWorkflow);
  const saveWorkflow = useWorkflowStore((state) => state.saveWorkflow);

  const refreshDocuments = async () => {
    const requestId = ++refreshRequestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const loaded = await listDocuments();
      // React StrictMode can launch two requests in development. Ignore any
      // older response so a startup failure cannot overwrite a later success.
      if (requestId !== refreshRequestIdRef.current) return;
      setDocuments(loaded);
      setSelectedDocument((current) => {
        if (!current) return loaded[0] || null;
        return loaded.find((item) => item.file_id === current.file_id) || loaded[0] || null;
      });
      setError(null);
    } catch (caught) {
      if (requestId !== refreshRequestIdRef.current) return;
      setError(caught instanceof Error ? caught.message : 'Unable to load documents.');
    } finally {
      if (requestId === refreshRequestIdRef.current) setLoading(false);
    }
  };

  useEffect(() => {
    void refreshDocuments();
  }, []);

  const filteredDocuments = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return documents.filter((document) => (
      !normalized
      || document.filename.toLowerCase().includes(normalized)
      || document.extension.toLowerCase().includes(normalized)
    ));
  }, [documents, search]);

  const imageCount = documents.filter((document) => document.mime_type.startsWith('image/')).length;
  const pdfCount = documents.filter((document) => document.extension === '.pdf').length;
  const officeCount = documents.filter((document) => ['.docx', '.xlsx', '.xlsm', '.csv'].includes(document.extension)).length;

  const appendFiles = (files: File[]) => {
    const allowed = files.filter((file) => !selectedFiles.some((existing) => (
      existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified
    )));
    setSelectedFiles((current) => [...current, ...allowed]);
    setUploadMessage(null);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    appendFiles(Array.from(event.dataTransfer.files));
  };

  const handleLocalUpload = async () => {
    if (!selectedFiles.length) {
      setUploadMessage('Select at least one file.');
      return;
    }
    setUploading(true);
    setUploadMessage(null);
    try {
      const result = await uploadDocuments(selectedFiles);
      if (result.documents.length) {
        setDocuments((current) => [
          ...result.documents,
          ...current.filter((existing) => !result.documents.some((uploaded) => uploaded.file_id === existing.file_id)),
        ]);
        setSelectedDocument(result.documents[0]);
      }
      setSelectedFiles([]);
      const errorText = result.errors.length
        ? ` ${result.failed} file(s) rejected: ${result.errors.map((item) => `${item.filename}: ${item.error}`).join('; ')}`
        : '';
      setUploadMessage(`${result.uploaded} file(s) imported successfully.${errorText}`);
      if (result.uploaded) window.setTimeout(() => setSubView('library'), 500);
    } catch (caught) {
      setUploadMessage(caught instanceof Error ? caught.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleCloudImport = async () => {
    if (!cloudUrl.trim()) {
      setUploadMessage('Enter a public direct file URL.');
      return;
    }
    setUploading(true);
    setUploadMessage(null);
    try {
      const imported = await importDocumentFromUrl(cloudUrl.trim(), cloudFilename.trim() || undefined);
      setDocuments((current) => [imported, ...current.filter((item) => item.file_id !== imported.file_id)]);
      setSelectedDocument(imported);
      setCloudUrl('');
      setCloudFilename('');
      setUploadMessage(`${imported.filename} imported from the cloud URL.`);
      window.setTimeout(() => setSubView('library'), 500);
    } catch (caught) {
      setUploadMessage(caught instanceof Error ? caught.message : 'Cloud import failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (document: DocumentRecord) => {
    if (!window.confirm(`Delete “${document.filename}” from local storage?`)) return;
    try {
      await deleteDocument(document.file_id);
      const remaining = documents.filter((item) => item.file_id !== document.file_id);
      setDocuments(remaining);
      setSelectedDocument((current) => current?.file_id === document.file_id ? remaining[0] || null : current);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Delete failed.');
    }
  };

  const handleUseInWorkflow = (document: DocumentRecord) => {
    resetFlow();
    const workflowId = createWorkflow(`Process ${document.filename}`);
    addNode('document-input', { x: 140, y: 200 }, {
      file_id: document.file_id,
      filename: document.filename,
      mime_type: document.mime_type,
      size_bytes: document.size_bytes,
      uploaded_at: document.uploaded_at,
    });
    const flow = useFlowStore.getState();
    saveWorkflow(workflowId, { nodes: flow.nodes, edges: flow.edges, viewport: flow.viewport });
    onNavigate('workflows');
  };

  return (
    <div className={styles.container}>
      {subView === 'library' ? (
        <div className={styles.libraryContainer}>
          <div className={styles.mainContent}>
            <header className={styles.header}>
              <div>
                <h1 className={styles.title}>Document Library</h1>
                <p className={styles.subtitle}>{documents.length} real document{documents.length === 1 ? '' : 's'} stored by the backend</p>
              </div>
              <div className={styles.headerActions}>
                <div className={styles.searchBar}>
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    type="text"
                    placeholder="Search documents..."
                    className={styles.searchInput}
                  />
                </div>
                <button onClick={() => void refreshDocuments()} className="btn-secondary">Refresh</button>
                <button onClick={() => { setUploadMessage(null); setSubView('import'); }} className="btn-premium">Import</button>
              </div>
            </header>

            {error && <div className={styles.errorBanner}><strong>Backend error:</strong> {error} Check that `run.bat` started the API on port 8000.</div>}

            <section className={styles.foldersSection}>
              <h3>Overview</h3>
              <div className={styles.foldersGrid}>
                {[
                  { name: 'All documents', count: documents.length, icon: '📁' },
                  { name: 'PDF files', count: pdfCount, icon: '📕' },
                  { name: 'Office & tables', count: officeCount, icon: '📊' },
                  { name: 'Images', count: imageCount, icon: '🖼️' },
                ].map((folder) => (
                  <div key={folder.name} className={`glass-card ${styles.folderCard}`}>
                    <div className={styles.folderHeader}><span className={styles.folderIcon}>{folder.icon}</span></div>
                    <h4>{folder.name}</h4>
                    <p>{folder.count} file{folder.count === 1 ? '' : 's'}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className={styles.filesSection}>
              <h3>Files</h3>
              <div className={styles.tableWrapper}>
                {loading ? (
                  <div className={styles.tableState}>Loading documents from the backend…</div>
                ) : !filteredDocuments.length ? (
                  <div className={styles.tableState}>
                    <span>📭</span>
                    <strong>{documents.length ? 'No matching document' : 'No imported documents'}</strong>
                    {!documents.length && <button className="btn-premium" onClick={() => setSubView('import')}>Import a document</button>}
                  </div>
                ) : (
                  <table className={styles.filesTable}>
                    <thead><tr><th>Name</th><th>Type</th><th>Source</th><th>Size</th><th>Imported</th><th></th></tr></thead>
                    <tbody>
                      {filteredDocuments.map((document) => (
                        <tr
                          key={document.file_id}
                          className={selectedDocument?.file_id === document.file_id ? styles.selectedRow : ''}
                          onClick={() => setSelectedDocument(document)}
                        >
                          <td><div className={styles.fileNameCell}><span className={styles.fileIcon}>{fileIcon(document)}</span><span className={styles.fileName}>{document.filename}</span></div></td>
                          <td className={styles.fileType}>{document.extension.replace('.', '').toUpperCase()}</td>
                          <td><span className={`${styles.status} ${styles.success}`}><span className={styles.statusDot}></span>{document.source === 'cloud-url' ? 'Cloud URL' : 'Local'}</span></td>
                          <td className={styles.modified}>{formatSize(document.size_bytes)}</td>
                          <td className={styles.modified}>{formatDate(document.uploaded_at)}</td>
                          <td className={styles.actions}>
                            <button className={styles.playBtn} onClick={(event) => { event.stopPropagation(); handleUseInWorkflow(document); }} title="Use in a new workflow">▶️</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          </div>

          {selectedDocument && (
            <aside className={styles.previewDrawer}>
              <div className={styles.drawerHeader}><h3>Document details</h3><button className={styles.closeBtn} onClick={() => setSelectedDocument(null)}>×</button></div>
              <div className={styles.previewBox}><div className={styles.previewDocIcon}>{fileIcon(selectedDocument)}</div><h4>{selectedDocument.filename}</h4></div>
              <div className={styles.metaList}>
                <div className={styles.metaItem}><span className={styles.metaLabel}>Type</span><span className={styles.metaValue}>{selectedDocument.mime_type}</span></div>
                <div className={styles.metaItem}><span className={styles.metaLabel}>Size</span><span className={styles.metaValue}>{formatSize(selectedDocument.size_bytes)}</span></div>
                <div className={styles.metaItem}><span className={styles.metaLabel}>Source</span><span className={styles.metaValue}>{selectedDocument.source}</span></div>
                <div className={styles.metaItem}><span className={styles.metaLabel}>File ID</span><span className={styles.metaValue} title={selectedDocument.file_id}>{selectedDocument.file_id.slice(0, 8)}…</span></div>
              </div>
              <div className={styles.drawerActions}>
                <button className="btn-premium" onClick={() => handleUseInWorkflow(selectedDocument)} style={{ width: '100%', justifyContent: 'center' }}>Use in new workflow</button>
                <button className="btn-secondary" onClick={() => window.open(documentDownloadUrl(selectedDocument.file_id), '_blank')} style={{ width: '100%', justifyContent: 'center' }}>Download</button>
                <button className={styles.deleteDocumentButton} onClick={() => void handleDelete(selectedDocument)}>Delete document</button>
              </div>
            </aside>
          )}
        </div>
      ) : (
        <div className={styles.importContainer}>
          <div className={styles.importHeaderBar}>
            <button className={styles.backBtn} onClick={() => setSubView('library')}>← Back to Library</button>
            <h2>Import Documents</h2>
            <p>Upload real local files, or download a file from a public cloud URL.</p>
          </div>

          <div className={styles.wizardLayout}>
            <aside className={styles.connectorList}>
              <button className={`${styles.connectorTab} ${activeSource === 'local' ? styles.connectorActive : ''}`} onClick={() => { setActiveSource('local'); setUploadMessage(null); }}>💻 Local files <span className={styles.conBadge}>Ready</span></button>
              <button className={`${styles.connectorTab} ${activeSource === 'cloud-url' ? styles.connectorActive : ''}`} onClick={() => { setActiveSource('cloud-url'); setUploadMessage(null); }}>🌐 Cloud URL <span className={styles.conBadge}>Ready</span></button>
              <button className={`${styles.connectorTab} ${activeSource === 'gdrive' ? styles.connectorActive : ''}`} onClick={() => setActiveSource('gdrive')}>🔺 Google Drive <span className={styles.setupBadge}>OAuth needed</span></button>
              <button className={`${styles.connectorTab} ${activeSource === 'onedrive' ? styles.connectorActive : ''}`} onClick={() => setActiveSource('onedrive')}>☁️ OneDrive <span className={styles.setupBadge}>OAuth needed</span></button>
            </aside>

            <section className={styles.fileBrowser}>
              {activeSource === 'local' && (
                <>
                  <div className={styles.browserHeader}><div><strong>Local upload</strong><p>Select several files or drag them here.</p></div></div>
                  <div
                    className={`${styles.dropZone} ${dragActive ? styles.dropZoneActive : ''}`}
                    onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }}
                    onDragOver={(event) => event.preventDefault()}
                    onDragLeave={() => setDragActive(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      hidden
                      accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.bmp,.webp,.docx,.txt,.md,.csv,.xlsx,.xlsm"
                      onChange={(event) => appendFiles(Array.from(event.target.files || []))}
                    />
                    <span>⬆</span><strong>Drop files here or click to browse</strong><small>PDF, images, DOCX, XLSX, CSV, TXT and Markdown · max 50 MB each</small>
                  </div>
                  <div className={styles.selectedUploadList}>
                    {selectedFiles.map((file, index) => (
                      <div key={`${file.name}-${file.lastModified}`}><span>📄 {file.name}</span><small>{formatSize(file.size)}</small><button onClick={() => setSelectedFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))}>×</button></div>
                    ))}
                    {!selectedFiles.length && <p>No local files selected.</p>}
                  </div>
                </>
              )}

              {activeSource === 'cloud-url' && (
                <div className={styles.cloudForm}>
                  <div className={styles.cloudIcon}>🌐</div>
                  <h3>Import from a public direct URL</h3>
                  <p>The backend downloads the file and stores it in the same document library. Private URLs and internal network addresses are blocked.</p>
                  <label>Direct file URL</label>
                  <input value={cloudUrl} onChange={(event) => setCloudUrl(event.target.value)} placeholder="https://example.com/report.pdf" />
                  <label>Filename override <span>(optional)</span></label>
                  <input value={cloudFilename} onChange={(event) => setCloudFilename(event.target.value)} placeholder="report.pdf" />
                </div>
              )}

              {(activeSource === 'gdrive' || activeSource === 'onedrive') && (
                <div className={styles.connectorSetup}>
                  <span>{activeSource === 'gdrive' ? '🔺' : '☁️'}</span>
                  <h3>{activeSource === 'gdrive' ? 'Google Drive' : 'OneDrive'} connector</h3>
                  <p>This connector is no longer shown as falsely connected. A real integration requires an OAuth client ID, redirect URL and user authorization. Use Local files or Cloud URL immediately.</p>
                  <button className="btn-secondary" onClick={() => setActiveSource('cloud-url')}>Use Cloud URL instead</button>
                </div>
              )}
            </section>

            <aside className={styles.importSummary}>
              <h3>Import summary</h3>
              {activeSource === 'local' && <><div className={styles.totalRow}><span>Selected files</span><span>{selectedFiles.length}</span></div><div className={styles.totalRow}><span>Total size</span><span>{formatSize(selectedFiles.reduce((sum, file) => sum + file.size, 0))}</span></div></>}
              {activeSource === 'cloud-url' && <div className={styles.totalRow}><span>Source</span><span>Public URL</span></div>}
              {uploadMessage && <div className={styles.uploadFeedback}>{uploadMessage}</div>}
              {activeSource === 'local' && <button className="btn-premium" disabled={uploading || !selectedFiles.length} onClick={() => void handleLocalUpload()} style={{ width: '100%', justifyContent: 'center', marginTop: 'auto' }}>{uploading ? 'Uploading…' : `Import ${selectedFiles.length || ''} file${selectedFiles.length === 1 ? '' : 's'}`}</button>}
              {activeSource === 'cloud-url' && <button className="btn-premium" disabled={uploading || !cloudUrl.trim()} onClick={() => void handleCloudImport()} style={{ width: '100%', justifyContent: 'center', marginTop: 'auto' }}>{uploading ? 'Downloading…' : 'Import cloud file'}</button>}
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
