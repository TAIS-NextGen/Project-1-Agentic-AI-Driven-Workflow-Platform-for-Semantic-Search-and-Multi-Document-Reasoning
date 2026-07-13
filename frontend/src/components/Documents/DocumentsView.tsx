import { useState } from 'react';
import type { AppRoute } from '../../types';
import styles from './DocumentsView.module.css';

interface DocumentsViewProps {
  onNavigate: (route: AppRoute) => void;
}

interface DocFile {
  id: string;
  name: string;
  type: string;
  size: string;
  status: 'success' | 'running' | 'idle' | 'error';
  tags: string[];
  modified: string;
  folder: string;
}

const mockFiles: DocFile[] = [
  {
    id: 'doc-1',
    name: 'ACME_Contract_Jan.pdf',
    type: 'PDF',
    size: '1.2 MB',
    status: 'success',
    tags: ['contract', 'Q1'],
    modified: '2h ago',
    folder: 'Contracts 2024',
  },
  {
    id: 'doc-2',
    name: 'HealthCo_MSA.pdf',
    type: 'PDF',
    size: '840 KB',
    status: 'success',
    tags: ['contract'],
    modified: '2h ago',
    folder: 'Contracts 2024',
  },
  {
    id: 'doc-3',
    name: 'Invoice_Q4.xlsx',
    type: 'XLSX',
    size: '120 KB',
    status: 'running',
    tags: ['invoice'],
    modified: 'Now',
    folder: 'Financial Reports',
  },
  {
    id: 'doc-4',
    name: 'Meeting_Notes_Mar.docx',
    type: 'DOCX',
    size: '56 KB',
    status: 'idle',
    tags: [],
    modified: '3d ago',
    folder: 'General',
  },
  {
    id: 'doc-5',
    name: 'Patient_Record_4821.pdf',
    type: 'PDF',
    size: '2.1 MB',
    status: 'error',
    tags: ['medical'],
    modified: '1d ago',
    folder: 'Medical Records',
  },
  {
    id: 'doc-6',
    name: 'Budget_2025.xlsx',
    type: 'XLSX',
    size: '340 KB',
    status: 'success',
    tags: ['finance'],
    modified: '5d ago',
    folder: 'Financial Reports',
  },
];

const folders = [
  { name: 'Contracts 2024', count: 47, updated: '2h ago' },
  { name: 'Medical Records', count: 128, updated: '1d ago' },
  { name: 'Financial Reports', count: 34, updated: '3d ago' },
  { name: 'HR Documents', count: 89, updated: '1w ago' },
];

export function DocumentsView({ onNavigate }: DocumentsViewProps) {
  const [subView, setSubView] = useState<'library' | 'import'>('library');
  const [selectedFile, setSelectedFile] = useState<DocFile | null>(mockFiles[2]); // Default selected file
  const [activeConnector, setActiveConnector] = useState('gdrive');
  const [importSelected, setImportSelected] = useState<Record<string, boolean>>({
    'file-1': true,
    'file-2': true,
    'file-3': true,
  });
  const [batchName, setBatchName] = useState('Contracts — Q1 2025');

  const toggleImportSelect = (id: string) => {
    setImportSelected(prev => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className={styles.container}>
      {subView === 'library' ? (
        <div className={styles.libraryContainer}>
          <div className={styles.mainContent}>
            {/* Library Header */}
            <header className={styles.header}>
              <div>
                <h1 className={styles.title}>Document Library</h1>
                <p className={styles.subtitle}>302 documents across 4 folders</p>
              </div>
              <div className={styles.headerActions}>
                <div className={styles.searchBar}>
                  <input type="text" placeholder="Search documents..." className={styles.searchInput} />
                </div>
                <button className="btn-secondary">Filter</button>
                <button onClick={() => setSubView('import')} className="btn-premium">Import</button>
              </div>
            </header>

            {/* Folders Grid */}
            <section className={styles.foldersSection}>
              <h3>Folders</h3>
              <div className={styles.foldersGrid}>
                {folders.map(f => (
                  <div key={f.name} className={`glass-card ${styles.folderCard}`}>
                    <div className={styles.folderHeader}>
                      <span className={styles.folderIcon}>📁</span>
                      <span className={styles.folderDots}>•••</span>
                    </div>
                    <h4>{f.name}</h4>
                    <p>{f.count} files • {f.updated}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* Files Section */}
            <section className={styles.filesSection}>
              <h3>Files</h3>
              <div className={styles.tableWrapper}>
                <table className={styles.filesTable}>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Tags</th>
                      <th>Modified</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {mockFiles.map((file) => {
                      const isSelected = selectedFile?.id === file.id;
                      const fileIcon = file.type === 'PDF' ? '📕' : file.type === 'XLSX' ? '📗' : '📘';
                      
                      return (
                        <tr
                          key={file.id}
                          className={isSelected ? styles.selectedRow : ''}
                          onClick={() => setSelectedFile(file)}
                        >
                          <td>
                            <div className={styles.fileNameCell}>
                              <span className={styles.fileIcon}>{fileIcon}</span>
                              <span className={styles.fileName}>{file.name}</span>
                            </div>
                          </td>
                          <td className={styles.fileType}>{file.type} • {file.size}</td>
                          <td>
                            <span className={`${styles.status} ${styles[file.status]}`}>
                              <span className={styles.statusDot}></span>
                              {file.status}
                            </span>
                          </td>
                          <td>
                            <div className={styles.tagList}>
                              {file.tags.map(t => (
                                <span key={t} className={styles.tag}>{t}</span>
                              ))}
                            </div>
                          </td>
                          <td className={styles.modified}>{file.modified}</td>
                          <td className={styles.actions}>
                            <button
                              type="button"
                              className={styles.playBtn}
                              onClick={(e) => {
                                e.stopPropagation();
                                onNavigate('workflows');
                              }}
                              title="Run workflow"
                            >
                              ▶️
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          {/* Details Sidebar / Drawer */}
          {selectedFile && (
            <aside className={styles.previewDrawer}>
              <div className={styles.drawerHeader}>
                <h3>Preview</h3>
                <button className={styles.closeBtn} onClick={() => setSelectedFile(null)}>×</button>
              </div>
              <div className={styles.previewBox}>
                <div className={styles.previewDocIcon}>
                  {selectedFile.type === 'PDF' ? '📕' : selectedFile.type === 'XLSX' ? '📗' : '📘'}
                </div>
                <h4>{selectedFile.name}</h4>
              </div>
              <div className={styles.metaList}>
                <div className={styles.metaItem}>
                  <span className={styles.metaLabel}>Type</span>
                  <span className={styles.metaValue}>{selectedFile.type}</span>
                </div>
                <div className={styles.metaItem}>
                  <span className={styles.metaLabel}>Size</span>
                  <span className={styles.metaValue}>{selectedFile.size}</span>
                </div>
                <div className={styles.metaItem}>
                  <span className={styles.metaLabel}>Folder</span>
                  <span className={styles.metaValue}>{selectedFile.folder}</span>
                </div>
                <div className={styles.metaItem}>
                  <span className={styles.metaLabel}>Status</span>
                  <span className={`${styles.metaValue} ${styles[selectedFile.status]}`}>{selectedFile.status}</span>
                </div>
              </div>
              <div className={styles.drawerActions}>
                <button
                  className="btn-premium"
                  onClick={() => onNavigate('workflows')}
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  Run Workflow
                </button>
                <button className="btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>
                  Download
                </button>
              </div>
            </aside>
          )}
        </div>
      ) : (
        /* IMPORT WIZARD SUB-VIEW */
        <div className={styles.importContainer}>
          <div className={styles.importHeaderBar}>
            <button className={styles.backBtn} onClick={() => setSubView('library')}>
              ← Back to Library
            </button>
            <h2>Import Documents</h2>
            <p>Choose your source, select files, then continue to build your workflow.</p>
          </div>

          <div className={styles.wizardLayout}>
            {/* Left Connectors Sidebar */}
            <aside className={styles.connectorList}>
              <button
                className={`${styles.connectorTab} ${activeConnector === 'gdrive' ? styles.connectorActive : ''}`}
                onClick={() => setActiveConnector('gdrive')}
              >
                <span className={styles.conIcon}>🤖</span> Google Drive
                <span className={styles.conBadge}>Connected</span>
              </button>
              <button
                className={`${styles.connectorTab} ${activeConnector === 'onedrive' ? styles.connectorActive : ''}`}
                onClick={() => setActiveConnector('onedrive')}
              >
                <span className={styles.conIcon}>☁️</span> OneDrive
                <span className={styles.conBadge}>Connected</span>
              </button>
              <button className={styles.connectorTab}>
                <span className={styles.conIcon}>📦</span> Dropbox
              </button>
              <button className={styles.connectorTab}>
                <span className={styles.conIcon}>🗄️</span> Amazon S3
              </button>
              <button className={styles.connectorTab}>
                <span className={styles.conIcon}>🏢</span> SharePoint
              </button>
            </aside>

            {/* Center File Browser */}
            <section className={styles.fileBrowser}>
              <div className={styles.browserHeader}>
                <span className={styles.folderBreadcrumb}>📁 My Drive &gt; Contracts 2024</span>
                <input type="text" placeholder="Search files..." className={styles.browserSearch} />
              </div>
              
              <div className={styles.browserList}>
                <div className={styles.browserItem}>
                  <input
                    type="checkbox"
                    checked={importSelected['file-1'] || false}
                    onChange={() => toggleImportSelect('file-1')}
                  />
                  <span>📕 ACME_Contract_Jan.pdf</span>
                  <span className={styles.browserSize}>1.2 MB</span>
                </div>
                <div className={styles.browserItem}>
                  <input
                    type="checkbox"
                    checked={importSelected['file-2'] || false}
                    onChange={() => toggleImportSelect('file-2')}
                  />
                  <span>📕 HealthCo_MSA.pdf</span>
                  <span className={styles.browserSize}>840 KB</span>
                </div>
                <div className={styles.browserItem}>
                  <input
                    type="checkbox"
                    checked={importSelected['file-3'] || false}
                    onChange={() => toggleImportSelect('file-3')}
                  />
                  <span>📗 Invoice_Q4.xlsx</span>
                  <span className={styles.browserSize}>120 KB</span>
                </div>
                <div className={styles.browserItem}>
                  <input type="checkbox" disabled />
                  <span>📘 meeting_notes.docx</span>
                  <span className={styles.browserSize}>56 KB</span>
                </div>
              </div>
            </section>

            {/* Right Summary Sidebar */}
            <aside className={styles.importSummary}>
              <h3>Selected Files</h3>
              <div className={styles.selectedFilesList}>
                {importSelected['file-1'] && (
                  <div className={styles.sumFileItem}>
                    <span>ACME_Contract_Jan.pdf</span>
                    <span>1.2 MB</span>
                  </div>
                )}
                {importSelected['file-2'] && (
                  <div className={styles.sumFileItem}>
                    <span>HealthCo_MSA.pdf</span>
                    <span>840 KB</span>
                  </div>
                )}
                {importSelected['file-3'] && (
                  <div className={styles.sumFileItem}>
                    <span>Invoice_Q4.xlsx</span>
                    <span className={styles.progressText}>68%</span>
                  </div>
                )}
              </div>
              
              <div className={styles.totalRow}>
                <span>Total size</span>
                <span>2.2 MB</span>
              </div>

              <div className={styles.importForm}>
                <label>Batch Name</label>
                <input
                  type="text"
                  value={batchName}
                  onChange={(e) => setBatchName(e.target.value)}
                  className={styles.formInput}
                />
                
                <label>Assign to Workflow</label>
                <select className={styles.formSelect}>
                  <option>Invoice Processing Pipeline</option>
                  <option>Contract Classifier</option>
                  <option>Medical Records OCR</option>
                </select>
              </div>

              <button
                className="btn-premium"
                onClick={() => {
                  setSubView('library');
                  onNavigate('workflows');
                }}
                style={{ width: '100%', justifyContent: 'center', marginTop: '20px' }}
              >
                Continue to Workflow →
              </button>
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
