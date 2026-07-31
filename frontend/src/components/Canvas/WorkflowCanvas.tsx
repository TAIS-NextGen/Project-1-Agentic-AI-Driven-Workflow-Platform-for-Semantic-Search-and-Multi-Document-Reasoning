import { useEffect, useState, useRef, type MouseEvent } from 'react';
import { useFlowStore } from '../../store/flowStore';
import { useExecutionStore } from '../../store/executionStore';
import { NODE_DEFINITIONS, getNodeDefinition, type NodeDefinition } from '../../config/nodeDefinitions';
import { NodeConfigPanel } from '../ConfigPanel/NodeConfigPanel';
import { fetchBackendNodeDefinitions } from '../../services/backendApi';
import styles from './WorkflowCanvas.module.css';

interface WorkflowCanvasProps {
  onRunWorkflow: (wfId: string, name: string) => void;
}

export function WorkflowCanvas({ onRunWorkflow }: WorkflowCanvasProps) {
  const {
    nodes,
    edges,
    selectedNodeId,
    viewport,
    addNode,
    updateNodePosition,
    selectNode,
    connectNodes,
    deleteEdge,
    deleteNode,
    setNodes,
    setEdges,
    setViewport,
    loadTemplate,
    resetFlow
  } = useFlowStore();

  const { executionResults } = useExecutionStore();

  const formatOutputPreview = (nodeId: string): string | null => {
    if (!executionResults) return null;
    const result = executionResults[nodeId];
    if (!result || result.status !== 'success') return null;

    const outputs = result.outputs;
    if (!outputs || typeof outputs !== 'object') return null;

    const lines: string[] = [];
    for (const [key, value] of Object.entries(outputs)) {
      if (typeof value === 'string' && value.length < 60) {
        lines.push(key + ': ' + value.trim().slice(0, 40));
      } else if (typeof value === 'number') {
        lines.push(key + ': ' + value);
      } else if (typeof value === 'object' && value !== null) {
        const inner = value as Record<string, unknown>;
        if (inner.polarity !== undefined || inner.score !== undefined) {
          const parts = [inner.polarity, inner.score];
          lines.push(parts.filter(Boolean).join(' '));
        } else if (inner.confidence_score !== undefined) {
          const flag = inner.is_supported ? '\u2713' : '\u2717';
          const conf = Number(inner.confidence_score).toFixed(2);
          lines.push(flag + ' supported, conf: ' + conf);
        } else if (typeof inner.text === 'string') {
          lines.push(inner.text.trim().slice(0, 50));
        } else {
          const keys = Object.keys(inner).slice(0, 2);
          if (keys.length > 0) lines.push(keys.join(', '));
        }
      }
      if (lines.length >= 3) break;
    }

    return lines.length > 0 ? lines.join(' \u00B7 ') : null;
  };

  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [nodeSearch, setNodeSearch] = useState('');
  const [backendNodes, setBackendNodes] = useState<NodeDefinition[]>([]);

  const [connectionSource, setConnectionSource] = useState<{ nodeId: string; portName: string } | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const dropPosRef = useRef({ x: 100, y: 150 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [selectAll, setSelectAll] = useState(false);
  const [clipboard, setClipboard] = useState<{ type: string; config: Record<string, unknown> } | null>(null);
  const [undoStack, setUndoStack] = useState<{ nodes: typeof nodes; edges: typeof edges }[]>([]);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  const pushUndo = () => {
    setUndoStack(prev => {
      const next = [...prev, { nodes: [...nodes], edges: [...edges] }];
      void undoStack;
      return next.length > 50 ? next.slice(-50) : next;
    });
  };

  const canvasRef = useRef<HTMLDivElement>(null);
  const draggedNodeRef = useRef<{ id: string; startX: number; startY: number } | null>(null);

  useEffect(() => {
    let mounted = true;
    fetchBackendNodeDefinitions()
      .then((definitions) => {
        if (mounted) {
          setBackendNodes(definitions);
        }
      })
      .catch(() => {
        if (mounted) {
          setBackendNodes([]);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setConnectionSource(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const mergedNodes = [...NODE_DEFINITIONS, ...backendNodes.filter((nodeDefinition) => !NODE_DEFINITIONS.some((existing) => existing.type === nodeDefinition.type))];

  const handleNodeMouseDown = (e: MouseEvent, nodeId: string) => {
    if (e.target instanceof HTMLButtonElement || (e.target as HTMLElement).closest('.' + styles.port)) {
      return;
    }
    e.stopPropagation();
    setSelectAll(false);
    setSelectedEdgeId(null);
    selectNode(nodeId);

    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;

    pushUndo();
    draggedNodeRef.current = {
      id: nodeId,
      startX: e.clientX / viewport.zoom - node.position.x,
      startY: e.clientY / viewport.zoom - node.position.y,
    };
  };

  const handleCanvasMouseMove = (e: MouseEvent) => {
    if (draggedNodeRef.current) {
      const { id, startX, startY } = draggedNodeRef.current;
      const x = Math.round(e.clientX / viewport.zoom - startX);
      const y = Math.round(e.clientY / viewport.zoom - startY);
      updateNodePosition(id, x, y);
      return;
    }

    if (connectionSource && canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      setMousePos({
        x: (e.clientX - rect.left - viewport.x) / viewport.zoom,
        y: (e.clientY - rect.top - viewport.y) / viewport.zoom,
      });
      return;
    }

    if (isPanning) {
      setViewport({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
        zoom: viewport.zoom,
      });
    }
  };

  const handleCanvasMouseUp = () => {
    draggedNodeRef.current = null;
    setIsPanning(false);
  };

  const handleCanvasMouseDown = (e: MouseEvent) => {
    if (e.target === canvasRef.current || (e.target as HTMLElement).classList.contains(styles.gridLayer)) {
      setSelectAll(false);
      setSelectedEdgeId(null);
      setConnectionSource(null);
      setIsPanning(true);
      setPanStart({
        x: e.clientX - viewport.x,
        y: e.clientY - viewport.y,
      });
    }
  };

  const handlePortMouseDown = (e: MouseEvent, nodeId: string, portName: string) => {
    e.stopPropagation();

    if (connectionSource && connectionSource.nodeId === nodeId && connectionSource.portName === portName) {
      setConnectionSource(null);
      return;
    }

    setConnectionSource({ nodeId, portName });

    if (canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      setMousePos({
        x: (e.clientX - rect.left - viewport.x) / viewport.zoom,
        y: (e.clientY - rect.top - viewport.y) / viewport.zoom,
      });
    }
  };

  const handlePortMouseUp = (e: MouseEvent, targetNodeId: string, targetPortName: string) => {
    e.stopPropagation();
    if (connectionSource && connectionSource.nodeId !== targetNodeId) {
      pushUndo();
      connectNodes(connectionSource.nodeId, connectionSource.portName, targetNodeId, targetPortName);
    }
    setConnectionSource(null);
  };

  const handleZoom = (factor: number) => {
    setViewport({
      ...viewport,
      zoom: Math.min(Math.max(viewport.zoom * factor, 0.5), 1.8),
    });
  };

  const getPortY = (nodeId: string, portName: string, isOutput: boolean) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return 0;
    const def = getNodeDefinition(node.type);
    const ports = isOutput ? (def?.outputs || []) : (def?.inputs || []);
    const idx = ports.findIndex(p => p.name === portName);
    return 35 + (idx >= 0 ? idx * 28 : 0) + 8;
  };

  const categories = Array.from(new Set(mergedNodes.map(n => n.category)));
  const filteredNodes = mergedNodes.filter(
    n =>
      n.name.toLowerCase().includes(nodeSearch.toLowerCase()) &&
      (!activeCategory || n.category === activeCategory)
  );

  return (
    <div className={styles.wrapper}>
      <aside className={styles.leftSidebar}>
        <div className={styles.sidebarHeader}>
          <h3>Nodes</h3>
          <input
            type="text"
            placeholder="Search nodes..."
            value={nodeSearch}
            onChange={(e) => setNodeSearch(e.target.value)}
            className={styles.nodeSearchInput}
          />
        </div>

        <div className={styles.categoryPills}>
          <button
            className={`${styles.pill} ${!activeCategory ? styles.pillActive : ''}`}
            onClick={() => setActiveCategory(null)}
          >
            All
          </button>
          {categories.map(cat => (
            <button
              key={cat}
              className={`${styles.pill} ${activeCategory === cat ? styles.pillActive : ''}`}
              onClick={() => setActiveCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>

        <div className={styles.nodeList}>
          {filteredNodes.map(def => (
            <div
              key={def.type}
              className={styles.sidebarNodeCard}
              onClick={() => { pushUndo(); const pos = { x: dropPosRef.current.x + 30, y: dropPosRef.current.y + 30 }; dropPosRef.current = pos; addNode(def.type, pos); }}
            >
              <div className={styles.cardIndicator} style={{ backgroundColor: def.color }}></div>
              <span className={styles.cardIcon}>{def.icon}</span>
              <div>
                <span className={styles.cardName}>{def.name}</span>
                <span className={styles.cardDesc}>{def.description}</span>
              </div>
            </div>
          ))}
        </div>

        <div className={styles.templatesBlock}>
          <h4>Load Template</h4>
          <div className={styles.templateButtons}>
            <button onClick={() => { pushUndo(); loadTemplate('invoice'); }} className="btn-secondary">Invoice OCR</button>
            <button onClick={() => { pushUndo(); loadTemplate('rag'); }} className="btn-secondary">RAG Embeds</button>
          </div>
          <button onClick={() => { pushUndo(); resetFlow(); }} className={styles.clearBtn}>Clear Canvas</button>
        </div>
      </aside>

      <div className={styles.editorArea}>
        <header className={styles.toolbar}>
          <div className={styles.wfNameBlock}>
            <h2>Invoice Processing Pipeline</h2>
            <span className={styles.savedStatus}>Saved</span>
          </div>
          <div className={styles.toolbarActions}>
            <button className="btn-secondary">Versions</button>
            <button className="btn-secondary">Share</button>
            <button
              onClick={() => onRunWorkflow('wf-1', 'Invoice Processing Pipeline')}
              className="btn-premium"
            >
              🚀 Run Workflow
            </button>
          </div>
        </header>

        <div
          ref={canvasRef}
          className={styles.canvasContainer}
          tabIndex={0}
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
          onMouseDown={handleCanvasMouseDown}
          onKeyDown={(e) => {
            if (e.ctrlKey && e.key === 'z') {
              e.preventDefault();
              setUndoStack(prev => {
                if (prev.length === 0) return prev;
                const snapshot = prev[prev.length - 1];
                setNodes([...snapshot.nodes]);
                setEdges([...snapshot.edges]);
                selectNode(null);
                setSelectedEdgeId(null);
                setSelectAll(false);
                return prev.slice(0, -1);
              });
            } else if (e.key === 'Delete' || e.key === 'Backspace') {
              e.preventDefault();
              if (selectedEdgeId) {
                pushUndo();
                deleteEdge(selectedEdgeId);
                setSelectedEdgeId(null);
              } else if (selectAll) {
                pushUndo();
                setNodes([]);
                setEdges([]);
                setSelectAll(false);
                selectNode(null);
              } else if (selectedNodeId) {
                pushUndo();
                deleteNode(selectedNodeId);
                selectNode(null);
              }
            } else if (e.ctrlKey && e.key === 'c') {
              e.preventDefault();
              const node = nodes.find(n => n.id === selectedNodeId);
              if (node) setClipboard({ type: node.type, config: { ...node.config } });
            } else if (e.ctrlKey && e.key === 'v') {
              e.preventDefault();
              if (clipboard) {
                pushUndo();
                addNode(clipboard.type, { x: mousePos.x, y: mousePos.y });
              }
            } else if (e.ctrlKey && e.key === 'd') {
              e.preventDefault();
              const node = nodes.find(n => n.id === selectedNodeId);
              if (node) {
                pushUndo();
                addNode(node.type, { x: node.position.x + 40, y: node.position.y + 40 });
              }
            } else if (e.ctrlKey && e.key === 'a') {
              e.preventDefault();
              setSelectAll(true);
            } else if (e.key === 'Escape') {
              selectNode(null);
              setConnectionSource(null);
              setSelectAll(false);
              setSelectedEdgeId(null);
            }
          }}
        >
          <svg
            className={styles.svgOverlay}
            style={{
              transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
              transformOrigin: '0 0',
            }}
          >
            {edges.map((edge) => {
              const srcNode = nodes.find(n => n.id === edge.source);
              const tgtNode = nodes.find(n => n.id === edge.target);

              if (!srcNode || !tgtNode) return null;

              const x1 = srcNode.position.x + 200;
              const y1 = srcNode.position.y + getPortY(srcNode.id, edge.sourcePort || 'output', true);
              const x2 = tgtNode.position.x;
              const y2 = tgtNode.position.y + getPortY(tgtNode.id, edge.targetPort || 'input', false);

              const cx1 = x1 + Math.abs(x2 - x1) * 0.4;
              const cy1 = y1;
              const cx2 = x2 - Math.abs(x2 - x1) * 0.4;
              const cy2 = y2;

              return (
                <g key={edge.id} className={`${styles.wireGroup} ${selectedEdgeId === edge.id ? styles.wireSelected : ''}`}>
                  <path
                    d={`M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`}
                    className={styles.wire}
                  />
                  <path
                    d={`M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`}
                    className={styles.wireHotspot}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedEdgeId(edge.id);
                      selectNode(null);
                      setSelectAll(false);
                    }}
                  />
                  <circle cx={(x1+x2)/2} cy={(y1+y2)/2} r="6" className={styles.wireDeleteNode} onClick={() => { pushUndo(); deleteEdge(edge.id); }} />
                </g>
              );
            })}

            {connectionSource && (
              (() => {
                const srcNode = nodes.find(n => n.id === connectionSource.nodeId);
                if (!srcNode) return null;
                const x1 = srcNode.position.x + 200;
                const y1 = srcNode.position.y + getPortY(srcNode.id, connectionSource.portName, true);
                const x2 = mousePos.x;
                const y2 = mousePos.y;
                const cx1 = x1 + Math.abs(x2 - x1) * 0.4;
                const cy1 = y1;
                const cx2 = x2 - Math.abs(x2 - x1) * 0.4;
                const cy2 = y2;

                return (
                  <path
                    d={`M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`}
                    className={`${styles.wire} ${styles.wirePreview}`}
                  />
                );
              })()
            )}
          </svg>

          <div
            className={styles.gridLayer}
            style={{
              transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
              transformOrigin: '0 0',
              backgroundImage: 'radial-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px)',
              backgroundSize: '20px 20px',
            }}
          >
            {nodes.map((node) => {
              const definition = getNodeDefinition(node.type);
              const isSelected = selectedNodeId === node.id || selectAll;

              if (!definition) return null;

              return (
                <div
                  key={node.id}
                  className={`${styles.nodeCard} ${isSelected ? styles.nodeSelected : ''}`}
                  style={{
                    left: `${node.position.x}px`,
                    top: `${node.position.y}px`,
                    minHeight: `${35 + Math.max(
                      (definition.inputs?.length || 1),
                      (definition.outputs?.length || 1),
                    ) * 28 + 20}px`,
                    borderColor: isSelected ? definition.color : 'rgba(255, 255, 255, 0.05)',
                    boxShadow: isSelected ? `0 0 20px ${definition.color}33` : undefined,
                  }}
                  onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                >
                  {(definition.inputs && definition.inputs.length > 0
                    ? definition.inputs.map((input, idx) => (
                        <div
                          key={`in-${input.name}`}
                          className={`${styles.port} ${styles.portInput}`}
                          style={{ top: `${35 + idx * 28}px` }}
                          onMouseUp={(e) => handlePortMouseUp(e, node.id, input.name!)}
                          title={`${input.label || input.name} (${input.type || 'any'})`}
                        >
                          <span className={styles.portDot}></span>
                        </div>
                      ))
                    : (
                      <div
                        className={`${styles.port} ${styles.portInput}`}
                        onMouseUp={(e) => handlePortMouseUp(e, node.id, 'input')}
                        title="Input port"
                      >
                        <span className={styles.portDot}></span>
                      </div>
                    )
                  )}

                  {(definition.outputs && definition.outputs.length > 0
                    ? definition.outputs.map((output, idx) => (
                        <div
                          key={`out-${output.name}`}
                          className={`${styles.port} ${styles.portOutput}`}
                          style={{ top: `${35 + idx * 28}px` }}
                          onMouseDown={(e) => handlePortMouseDown(e, node.id, output.name!)}
                          title={`${output.label || output.name} (${output.type || 'any'})`}
                        >
                          <span className={styles.portDot}></span>
                        </div>
                      ))
                    : (
                      <div
                        className={`${styles.port} ${styles.portOutput}`}
                        onMouseDown={(e) => handlePortMouseDown(e, node.id, 'output')}
                        title="Output port"
                      >
                        <span className={styles.portDot}></span>
                      </div>
                    )
                  )}

                  <div className={styles.nodeHeader} style={{ background: `linear-gradient(90deg, ${definition.color}15 0%, transparent 100%)` }}>
                    <span className={styles.nodeIcon}>{definition.icon}</span>
                    <div>
                      <h4 className={styles.nodeName}>{definition.name}</h4>
                      <span className={styles.nodeCat}>{definition.category}</span>
                    </div>
                    <button
                      className={styles.deleteNodeBtn}
                      onClick={(e) => {
                        e.stopPropagation();
                        pushUndo();
                        deleteNode(node.id);
                      }}
                      title="Delete node"
                    >
                      ×
                    </button>
                  </div>

                  <div className={styles.nodeContent}>
                    <span className={`${styles.nodeStatusBadge} ${styles[node.status]}`}>
                      {node.status}
                    </span>
                    {(() => {
                      const preview = formatOutputPreview(node.id);
                      return preview ? <div className={styles.nodeOutputPreview}>{preview}</div> : null;
                    })()}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className={styles.viewportControls}>
          <button onClick={() => handleZoom(1.25)} title="Zoom In">+</button>
          <span>{Math.round(viewport.zoom * 100)}%</span>
          <button onClick={() => handleZoom(0.8)} title="Zoom Out">-</button>
          <button onClick={() => setViewport({ x: 0, y: 0, zoom: 1 })} title="Reset View">⟲</button>
        </div>
      </div>

      {selectedNodeId && <NodeConfigPanel />}
    </div>
  );
}