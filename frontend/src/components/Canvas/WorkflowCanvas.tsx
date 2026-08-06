import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type DragEvent,
  type MouseEvent,
  type WheelEvent,
} from 'react';
import { useFlowStore } from '../../store/flowStore';
import { useWorkflowStore } from '../../store/workflowStore';
import { NODE_DEFINITIONS, getNodeDefinition, type NodeDefinition } from '../../config/nodeDefinitions';
import { NodeConfigPanel } from '../ConfigPanel/NodeConfigPanel';
import { fetchBackendNodeDefinitions } from '../../services/backendApi';
import type { AppTheme } from '../../App';
import styles from './WorkflowCanvas.module.css';

interface WorkflowCanvasProps {
  onRunWorkflow: (wfId: string, name: string) => void;
  onBackToWorkflows: () => void;
  theme: AppTheme;
  onToggleTheme: () => void;
}

const NODE_WIDTH = 226;
const NODE_HEIGHT = 118;
const GRID_SIZE = 20;

export function WorkflowCanvas({ onRunWorkflow, onBackToWorkflows, theme, onToggleTheme }: WorkflowCanvasProps) {
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
    setViewport,
    loadFlow,
    loadTemplate,
    resetFlow,
  } = useFlowStore();

  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [nodeSearch, setNodeSearch] = useState('');
  const [backendNodes, setBackendNodes] = useState<NodeDefinition[]>([]);
  const [connectionSource, setConnectionSource] = useState<string | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [workflowName, setWorkflowName] = useState('Untitled Workflow');
  const [saveState, setSaveState] = useState<'saved' | 'saving'>('saved');

  const activeWorkflowId = useWorkflowStore((state) => state.activeWorkflowId);
  const saveWorkflow = useWorkflowStore((state) => state.saveWorkflow);
  const renameWorkflow = useWorkflowStore((state) => state.renameWorkflow);
  const recordRun = useWorkflowStore((state) => state.recordRun);
  const loadedWorkflowRef = useRef<string | null>(null);

  const canvasRef = useRef<HTMLDivElement | null>(null);
  const draggedNodeRef = useRef<{ id: string; offsetX: number; offsetY: number } | null>(null);

  useEffect(() => {
    if (!activeWorkflowId) return;
    const workflow = useWorkflowStore.getState().workflows.find((item) => item.id === activeWorkflowId);
    if (!workflow) return;
    loadFlow(workflow.nodes || [], workflow.edges || [], workflow.viewport || { x: 0, y: 0, zoom: 1 });
    setWorkflowName(workflow.name);
    loadedWorkflowRef.current = activeWorkflowId;
  }, [activeWorkflowId, loadFlow]);

  useEffect(() => {
    if (!activeWorkflowId || loadedWorkflowRef.current !== activeWorkflowId) return;
    setSaveState('saving');
    const timer = window.setTimeout(() => {
      saveWorkflow(activeWorkflowId, { nodes, edges, viewport });
      setSaveState('saved');
    }, 350);
    return () => window.clearTimeout(timer);
  }, [activeWorkflowId, edges, nodes, saveWorkflow, viewport]);


  useEffect(() => {
    let mounted = true;
    fetchBackendNodeDefinitions()
      .then((definitions) => {
        if (mounted) {
          setBackendNodes(definitions);
          setBackendOnline(true);
        }
      })
      .catch(() => {
        if (mounted) {
          setBackendNodes([]);
          setBackendOnline(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setConnectionSource(null);
        selectNode(null);
      }
      if ((event.key === 'Delete' || event.key === 'Backspace') && selectedNodeId) {
        const target = event.target as HTMLElement | null;
        if (target?.matches('input, textarea, select')) return;
        deleteNode(selectedNodeId);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [deleteNode, selectNode, selectedNodeId]);

  const mergedNodes = useMemo(
    () => [
      ...NODE_DEFINITIONS,
      ...backendNodes.filter(
        (nodeDefinition) => !NODE_DEFINITIONS.some((existing) => existing.type === nodeDefinition.type),
      ),
    ],
    [backendNodes],
  );

  const definitionMap = useMemo(
    () => new Map(mergedNodes.map((definition) => [definition.type, definition])),
    [mergedNodes],
  );

  const getDefinition = (type: string) => definitionMap.get(type) || getNodeDefinition(type);

  const categories = useMemo(
    () => Array.from(new Set(mergedNodes.map((node) => node.category))),
    [mergedNodes],
  );

  const filteredNodes = useMemo(() => {
    const search = nodeSearch.trim().toLowerCase();
    return mergedNodes.filter((node) => {
      const matchesSearch = !search
        || node.name.toLowerCase().includes(search)
        || node.description?.toLowerCase().includes(search)
        || node.type.toLowerCase().includes(search);
      return matchesSearch && (!activeCategory || node.category === activeCategory);
    });
  }, [activeCategory, mergedNodes, nodeSearch]);

  const toWorldCoordinates = (clientX: number, clientY: number) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: (clientX - rect.left - viewport.x) / viewport.zoom,
      y: (clientY - rect.top - viewport.y) / viewport.zoom,
    };
  };

  const snap = (value: number) => (snapToGrid ? Math.round(value / GRID_SIZE) * GRID_SIZE : Math.round(value));

  const addNodeAt = (type: string, position: { x: number; y: number }) => {
    addNode(type, { x: snap(position.x), y: snap(position.y) });
  };

  const handleNodeMouseDown = (event: MouseEvent, nodeId: string) => {
    if (
      event.target instanceof HTMLButtonElement
      || (event.target as HTMLElement).closest(`.${styles.port}`)
    ) {
      return;
    }

    event.stopPropagation();
    selectNode(nodeId);
    const node = nodes.find((candidate) => candidate.id === nodeId);
    if (!node) return;

    const world = toWorldCoordinates(event.clientX, event.clientY);
    draggedNodeRef.current = {
      id: nodeId,
      offsetX: world.x - node.position.x,
      offsetY: world.y - node.position.y,
    };
  };

  const handleCanvasMouseMove = (event: MouseEvent) => {
    if (draggedNodeRef.current) {
      const world = toWorldCoordinates(event.clientX, event.clientY);
      updateNodePosition(
        draggedNodeRef.current.id,
        snap(world.x - draggedNodeRef.current.offsetX),
        snap(world.y - draggedNodeRef.current.offsetY),
      );
      return;
    }

    if (connectionSource) {
      setMousePos(toWorldCoordinates(event.clientX, event.clientY));
      return;
    }

    if (isPanning) {
      setViewport({
        x: event.clientX - panStart.x,
        y: event.clientY - panStart.y,
        zoom: viewport.zoom,
      });
    }
  };

  const handleCanvasMouseUp = () => {
    draggedNodeRef.current = null;
    setIsPanning(false);
    setConnectionSource(null);
  };

  const handleCanvasMouseDown = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    if (target === canvasRef.current || target.classList.contains(styles.gridLayer)) {
      selectNode(null);
      setIsPanning(true);
      setPanStart({ x: event.clientX - viewport.x, y: event.clientY - viewport.y });
    }
  };

  const handlePortMouseDown = (event: MouseEvent, nodeId: string) => {
    event.stopPropagation();
    setConnectionSource(nodeId);
    const node = nodes.find((candidate) => candidate.id === nodeId);
    if (node) {
      setMousePos({ x: node.position.x + NODE_WIDTH, y: node.position.y + 46 });
    }
  };

  const handlePortMouseUp = (event: MouseEvent, targetNodeId: string) => {
    event.stopPropagation();
    if (connectionSource && connectionSource !== targetNodeId) {
      connectNodes(connectionSource, targetNodeId);
    }
    setConnectionSource(null);
  };

  const handleZoom = (factor: number) => {
    setViewport({
      ...viewport,
      zoom: Math.min(Math.max(viewport.zoom * factor, 0.45), 2),
    });
  };

  const handleWheel = (event: WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!canvasRef.current) return;

    if (!event.ctrlKey && !event.metaKey) {
      setViewport({
        ...viewport,
        x: viewport.x - event.deltaX,
        y: viewport.y - event.deltaY,
      });
      return;
    }

    const rect = canvasRef.current.getBoundingClientRect();
    const pointerX = event.clientX - rect.left;
    const pointerY = event.clientY - rect.top;
    const worldX = (pointerX - viewport.x) / viewport.zoom;
    const worldY = (pointerY - viewport.y) / viewport.zoom;
    const nextZoom = Math.min(Math.max(viewport.zoom * (event.deltaY > 0 ? 0.9 : 1.1), 0.45), 2);

    setViewport({
      zoom: nextZoom,
      x: pointerX - worldX * nextZoom,
      y: pointerY - worldY * nextZoom,
    });
  };

  const handlePaletteDragStart = (event: DragEvent<HTMLDivElement>, type: string) => {
    event.dataTransfer.setData('application/x-flow-node', type);
    event.dataTransfer.effectAllowed = 'copy';
  };

  const handleCanvasDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const type = event.dataTransfer.getData('application/x-flow-node');
    if (!type) return;
    const world = toWorldCoordinates(event.clientX, event.clientY);
    addNodeAt(type, { x: world.x - NODE_WIDTH / 2, y: world.y - 40 });
  };

  const autoLayout = () => {
    if (!nodes.length) return;
    const levels = new Map<string, number>();
    const unresolved = new Set(nodes.map((node) => node.id));

    for (let pass = 0; pass < nodes.length + 1 && unresolved.size; pass += 1) {
      for (const nodeId of Array.from(unresolved)) {
        const incoming = edges.filter((edge) => edge.target === nodeId);
        if (!incoming.length) {
          levels.set(nodeId, 0);
          unresolved.delete(nodeId);
          continue;
        }
        const parentLevels = incoming.map((edge) => levels.get(edge.source));
        if (parentLevels.every((level) => level !== undefined)) {
          levels.set(nodeId, Math.max(...(parentLevels as number[])) + 1);
          unresolved.delete(nodeId);
        }
      }
    }

    unresolved.forEach((nodeId) => levels.set(nodeId, 0));
    const grouped = new Map<number, string[]>();
    nodes.forEach((node) => {
      const level = levels.get(node.id) || 0;
      grouped.set(level, [...(grouped.get(level) || []), node.id]);
    });

    grouped.forEach((ids, level) => {
      ids.forEach((nodeId, index) => {
        updateNodePosition(nodeId, 100 + level * 310, 100 + index * 180);
      });
    });
    window.setTimeout(() => fitView(), 0);
  };

  const fitView = () => {
    if (!canvasRef.current || !nodes.length) {
      setViewport({ x: 0, y: 0, zoom: 1 });
      return;
    }
    const rect = canvasRef.current.getBoundingClientRect();
    const minX = Math.min(...nodes.map((node) => node.position.x));
    const minY = Math.min(...nodes.map((node) => node.position.y));
    const maxX = Math.max(...nodes.map((node) => node.position.x + NODE_WIDTH));
    const maxY = Math.max(...nodes.map((node) => node.position.y + NODE_HEIGHT));
    const width = Math.max(maxX - minX, 1);
    const height = Math.max(maxY - minY, 1);
    const padding = 90;
    const zoom = Math.min(Math.max(Math.min((rect.width - padding * 2) / width, (rect.height - padding * 2) / height), 0.45), 1.35);
    setViewport({
      zoom,
      x: (rect.width - width * zoom) / 2 - minX * zoom,
      y: (rect.height - height * zoom) / 2 - minY * zoom,
    });
  };


  return (
    <div className={styles.wrapper}>
      <aside className={`${styles.leftSidebar} ${sidebarCollapsed ? styles.leftSidebarCollapsed : ''}`}>
        <button
          className={styles.sidebarToggle}
          onClick={() => setSidebarCollapsed((value) => !value)}
          title={sidebarCollapsed ? 'Open node library' : 'Collapse node library'}
        >
          {sidebarCollapsed ? '›' : '‹'}
        </button>

        {!sidebarCollapsed && (
          <>
            <div className={styles.sidebarHeader}>
              <div className={styles.libraryTitle}>
                <div>
                  <span className={styles.eyebrow}>BUILD</span>
                  <h3>Node library</h3>
                </div>
                <span className={`${styles.connectionBadge} ${backendOnline ? styles.online : styles.offline}`}>
                  <i /> {backendOnline === null ? 'Loading' : backendOnline ? 'Backend' : 'Offline'}
                </span>
              </div>
              <div className={styles.searchWrap}>
                <span>⌕</span>
                <input
                  type="search"
                  placeholder="Search by name or capability…"
                  value={nodeSearch}
                  onChange={(event) => setNodeSearch(event.target.value)}
                  className={styles.nodeSearchInput}
                />
                {nodeSearch && <button onClick={() => setNodeSearch('')}>×</button>}
              </div>
            </div>

            <div className={styles.categoryPills}>
              <button
                className={`${styles.pill} ${!activeCategory ? styles.pillActive : ''}`}
                onClick={() => setActiveCategory(null)}
              >
                All <span>{mergedNodes.length}</span>
              </button>
              {categories.map((category) => (
                <button
                  key={category}
                  className={`${styles.pill} ${activeCategory === category ? styles.pillActive : ''}`}
                  onClick={() => setActiveCategory(category)}
                >
                  {category}
                </button>
              ))}
            </div>

            <div className={styles.nodeList}>
              <p className={styles.listHint}>Drag a node to the canvas or click it to add it.</p>
              {filteredNodes.map((definition) => (
                <div
                  key={definition.type}
                  className={styles.sidebarNodeCard}
                  draggable
                  onDragStart={(event) => handlePaletteDragStart(event, definition.type)}
                  onClick={() => addNodeAt(definition.type, {
                    x: 160 - viewport.x / viewport.zoom,
                    y: 150 - viewport.y / viewport.zoom,
                  })}
                >
                  <div className={styles.cardIconWrap} style={{ color: definition.color, background: `${definition.color}17` }}>
                    <span>{definition.icon}</span>
                  </div>
                  <div className={styles.cardCopy}>
                    <span className={styles.cardName}>{definition.name}</span>
                    <span className={styles.cardDesc}>{definition.description}</span>
                    <div className={styles.cardPorts}>
                      <span>{definition.inputs?.[0]?.type || 'any'} in</span>
                      <span>{definition.outputs?.[0]?.type || 'any'} out</span>
                    </div>
                  </div>
                  <span className={styles.dragHandle}>⋮⋮</span>
                </div>
              ))}
              {!filteredNodes.length && (
                <div className={styles.noResults}>
                  <span>⌕</span>
                  <strong>No nodes found</strong>
                  <button onClick={() => { setNodeSearch(''); setActiveCategory(null); }}>Reset filters</button>
                </div>
              )}
            </div>

            <div className={styles.templatesBlock}>
              <div className={styles.templatesHeader}>
                <span>Starter workflows</span>
                <small>1-click load</small>
              </div>
              <div className={styles.templateButtons}>
                <button onClick={() => loadTemplate('invoice')}><span>🧾</span>Invoice OCR</button>
                <button onClick={() => loadTemplate('enhance')}><span>☀️</span>Image cleanup</button>
                <button onClick={() => loadTemplate('parser')}><span>📄</span>Parse documents</button>
                <button onClick={() => loadTemplate('clustering')}><span>🧠</span>Topic clustering</button>
                <button onClick={() => loadTemplate('comparison')}><span>⚖️</span>Compare documents</button>
                <button onClick={() => loadTemplate('rag')}><span>🔎</span>RAG Search</button>
              </div>
            </div>
          </>
        )}
      </aside>

      <div className={styles.editorArea}>
        <header className={styles.toolbar}>
          <div className={styles.wfNameBlock}>
            <button className={styles.backToHistory} onClick={onBackToWorkflows} title="Back to workflow history" aria-label="Back to workflow history">
              <span aria-hidden="true">←</span>
            </button>
            <div className={styles.workflowIcon} aria-hidden="true">⌘</div>
            <div className={styles.workflowIdentity}>
              <div className={styles.titleLine}>
                <input
                  className={styles.workflowNameInput}
                  value={workflowName}
                  onChange={(event) => {
                    setWorkflowName(event.target.value);
                    setSaveState('saving');
                  }}
                  onBlur={() => {
                    if (!activeWorkflowId) return;
                    const cleanedName = workflowName.trim() || 'New workflow';
                    setWorkflowName(cleanedName);
                    renameWorkflow(activeWorkflowId, cleanedName);
                    setSaveState('saved');
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') event.currentTarget.blur();
                  }}
                  aria-label="Workflow name"
                  title="Click to rename"
                />
                <span className={`${styles.savedStatus} ${saveState === 'saving' ? styles.savingStatus : ''}`}>
                  <i /> {saveState === 'saving' ? 'Saving…' : 'Saved'}
                </span>
              </div>
              <div className={styles.workflowMeta}>
                <span>{nodes.length} node{nodes.length === 1 ? '' : 's'}</span>
                <span>{edges.length} connection{edges.length === 1 ? '' : 's'}</span>
                <span>{Math.round(viewport.zoom * 100)}% zoom</span>
              </div>
            </div>
          </div>

          <div className={styles.toolbarActions}>
            <div className={styles.toolGroup} aria-label="Canvas tools">
              <button
                onClick={() => setSnapToGrid((value) => !value)}
                className={snapToGrid ? styles.toolActive : ''}
                title="Toggle snap to grid"
                aria-pressed={snapToGrid}
              >
                <span className={styles.toolIcon}>#</span><span>Snap</span>
              </button>
              <button onClick={autoLayout} title="Automatically arrange nodes">
                <span className={styles.toolIcon}>⌁</span><span>Arrange</span>
              </button>
              <button onClick={fitView} title="Fit all nodes in view">
                <span className={styles.toolIcon}>⛶</span><span>Fit</span>
              </button>
            </div>

            <div className={styles.toolGroup} aria-label="Workspace actions">
              <button
                onClick={onToggleTheme}
                title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
                aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
              >
                <span className={styles.toolIcon}>{theme === 'light' ? '☀' : '◐'}</span><span>Theme</span>
              </button>
              <button
                onClick={() => {
                  if (!nodes.length || window.confirm('Clear all nodes and connections from this workflow?')) resetFlow();
                }}
                className={styles.dangerAction}
                title="Clear workflow"
              >
                <span className={styles.toolIcon}>⌫</span><span>Clear</span>
              </button>
            </div>

            <button
              onClick={() => {
                if (!activeWorkflowId) return;
                saveWorkflow(activeWorkflowId, { nodes, edges, viewport });
                setSaveState('saved');
                recordRun(activeWorkflowId);
                onRunWorkflow(activeWorkflowId, workflowName);
              }}
              className={styles.runButton}
              disabled={!nodes.length}
            >
              <span className={styles.runIcon}>▶</span>
              <span className={styles.runCopy}><strong>Run workflow</strong><small>{nodes.length ? `${nodes.length} nodes ready` : 'Add a node first'}</small></span>
            </button>
          </div>
        </header>
        <div
          ref={canvasRef}
          className={styles.canvasContainer}
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
          onMouseLeave={handleCanvasMouseUp}
          onMouseDown={handleCanvasMouseDown}
          onWheel={handleWheel}
          onDrop={handleCanvasDrop}
          onDragOver={(event) => event.preventDefault()}
        >
          <div className={styles.canvasGlow} />
          <svg
            className={styles.svgOverlay}
            style={{
              transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
              transformOrigin: '0 0',
            }}
          >
            <defs>
              <linearGradient id="wire-gradient" x1="0" x2="1">
                <stop offset="0%" stopColor="#8b5cf6" />
                <stop offset="100%" stopColor="#22d3ee" />
              </linearGradient>
              <filter id="wire-glow">
                <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>
            {edges.map((edge) => {
              const sourceNode = nodes.find((node) => node.id === edge.source);
              const targetNode = nodes.find((node) => node.id === edge.target);
              if (!sourceNode || !targetNode) return null;

              const x1 = sourceNode.position.x + NODE_WIDTH;
              const y1 = sourceNode.position.y + 46;
              const x2 = targetNode.position.x;
              const y2 = targetNode.position.y + 46;
              const controlOffset = Math.max(70, Math.abs(x2 - x1) * 0.42);
              const path = `M ${x1} ${y1} C ${x1 + controlOffset} ${y1}, ${x2 - controlOffset} ${y2}, ${x2} ${y2}`;

              return (
                <g key={edge.id} className={styles.wireGroup}>
                  <path d={path} className={styles.wireShadow} />
                  <path d={path} className={styles.wire} />
                  <path d={path} className={styles.wireHotspot} onClick={() => deleteEdge(edge.id)} />
                  <circle
                    cx={(x1 + x2) / 2}
                    cy={(y1 + y2) / 2}
                    r="8"
                    className={styles.wireDeleteNode}
                    onClick={() => deleteEdge(edge.id)}
                  />
                  <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 + 3} className={styles.wireDeleteText}>×</text>
                </g>
              );
            })}

            {connectionSource && (() => {
              const sourceNode = nodes.find((node) => node.id === connectionSource);
              if (!sourceNode) return null;
              const x1 = sourceNode.position.x + NODE_WIDTH;
              const y1 = sourceNode.position.y + 46;
              const x2 = mousePos.x;
              const y2 = mousePos.y;
              const offset = Math.max(70, Math.abs(x2 - x1) * 0.42);
              return (
                <path
                  d={`M ${x1} ${y1} C ${x1 + offset} ${y1}, ${x2 - offset} ${y2}, ${x2} ${y2}`}
                  className={`${styles.wire} ${styles.wirePreview}`}
                />
              );
            })()}
          </svg>

          <div
            className={styles.gridLayer}
            style={{
              transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
              transformOrigin: '0 0',
              backgroundPosition: `${-GRID_SIZE / 2}px ${-GRID_SIZE / 2}px`,
            }}
          >
            {nodes.map((node) => {
              const definition = getDefinition(node.type);
              const isSelected = selectedNodeId === node.id;
              if (!definition) return null;
              const primaryInput = definition.inputs?.[0];
              const primaryOutput = definition.outputs?.[0];

              return (
                <div
                  key={node.id}
                  className={`${styles.nodeCard} ${isSelected ? styles.nodeSelected : ''} ${styles[`status_${node.status}`] || ''}`}
                  style={{
                    left: `${node.position.x}px`,
                    top: `${node.position.y}px`,
                    '--node-color': definition.color,
                  } as CSSProperties}
                  onMouseDown={(event) => handleNodeMouseDown(event, node.id)}
                  onDoubleClick={() => selectNode(node.id)}
                >
                  <div
                    className={`${styles.port} ${styles.portInput}`}
                    onMouseUp={(event) => handlePortMouseUp(event, node.id)}
                    title={`${primaryInput?.label || 'Input'} · ${primaryInput?.type || 'any'}`}
                  >
                    <span className={styles.portDot} />
                    <span className={styles.portLabel}>{primaryInput?.type || 'in'}</span>
                  </div>

                  <div
                    className={`${styles.port} ${styles.portOutput}`}
                    onMouseDown={(event) => handlePortMouseDown(event, node.id)}
                    title={`${primaryOutput?.label || 'Output'} · ${primaryOutput?.type || 'any'}`}
                  >
                    <span className={styles.portLabel}>{primaryOutput?.type || 'out'}</span>
                    <span className={styles.portDot} />
                  </div>

                  <div className={styles.nodeAccent} />
                  <div className={styles.nodeHeader}>
                    <div className={styles.nodeIcon} style={{ background: `${definition.color}18`, color: definition.color }}>
                      {definition.icon}
                    </div>
                    <div className={styles.nodeTitle}>
                      <h4>{definition.name}</h4>
                      <span>{definition.category}</span>
                    </div>
                    <button
                      className={styles.deleteNodeBtn}
                      onClick={(event) => {
                        event.stopPropagation();
                        deleteNode(node.id);
                      }}
                      title="Delete node"
                    >
                      ×
                    </button>
                  </div>

                  <div className={styles.nodeContent}>
                    <p>{definition.description}</p>
                    <div className={styles.nodeFooter}>
                      <span className={`${styles.nodeStatusBadge} ${styles[node.status]}`}>
                        <i /> {node.status}
                      </span>
                      <span className={styles.configCount}>{Object.keys(node.config || {}).length} settings</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {!nodes.length && (
            <div className={styles.emptyCanvas}>
              <div className={styles.emptyIcon}>＋</div>
              <h3>Build your document workflow</h3>
              <p>Drag nodes from the library, connect their ports, configure them and run the pipeline.</p>
              <button onClick={() => loadTemplate('invoice')}>Load invoice starter</button>
            </div>
          )}

          <div className={styles.canvasHelp}>
            <span><kbd>Drag</kbd> move</span>
            <span><kbd>Ctrl</kbd> + wheel zoom</span>
            <span><kbd>Del</kbd> remove</span>
          </div>

          <div className={styles.minimap}>
            <div className={styles.minimapHeader}><span>MINIMAP</span><small>{nodes.length}</small></div>
            <div className={styles.minimapCanvas}>
              {nodes.map((node) => {
                const definition = getDefinition(node.type);
                return (
                  <span
                    key={node.id}
                    style={{
                      left: `${Math.max(2, Math.min(92, node.position.x / 16))}%`,
                      top: `${Math.max(3, Math.min(84, node.position.y / 12))}%`,
                      background: definition?.color,
                    }}
                  />
                );
              })}
            </div>
          </div>

          <div className={styles.viewportControls}>
            <button onClick={() => handleZoom(0.85)} title="Zoom out">−</button>
            <button className={styles.zoomValue} onClick={() => setViewport({ ...viewport, zoom: 1 })}>{Math.round(viewport.zoom * 100)}%</button>
            <button onClick={() => handleZoom(1.18)} title="Zoom in">＋</button>
            <i />
            <button onClick={fitView} title="Fit view">⛶</button>
          </div>
        </div>
      </div>

      {selectedNodeId && <NodeConfigPanel />}
    </div>
  );
}
