import { useState, useRef, type MouseEvent } from 'react';
import { useFlowStore } from '../../store/flowStore';
import { NODE_DEFINITIONS } from '../../config/nodeDefinitions';
import { NodeConfigPanel } from '../ConfigPanel/NodeConfigPanel';
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
    setViewport,
    loadTemplate,
    resetFlow
  } = useFlowStore();

  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [nodeSearch, setNodeSearch] = useState('');
  
  // Connection states
  const [connectionSource, setConnectionSource] = useState<string | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  const canvasRef = useRef<HTMLDivElement>(null);
  const draggedNodeRef = useRef<{ id: string; startX: number; startY: number } | null>(null);

  // Handle Dragging Nodes
  const handleNodeMouseDown = (e: MouseEvent, nodeId: string) => {
    if (e.target instanceof HTMLButtonElement || (e.target as HTMLElement).closest('.' + styles.port)) {
      return; // Ignore ports or buttons
    }
    e.stopPropagation();
    selectNode(nodeId);
    
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;

    // Convert client coordinates to zoom space
    draggedNodeRef.current = {
      id: nodeId,
      startX: e.clientX / viewport.zoom - node.position.x,
      startY: e.clientY / viewport.zoom - node.position.y,
    };
  };

  const handleCanvasMouseMove = (e: MouseEvent) => {
    // 1. Handle Node Dragging
    if (draggedNodeRef.current) {
      const { id, startX, startY } = draggedNodeRef.current;
      const x = Math.round(e.clientX / viewport.zoom - startX);
      const y = Math.round(e.clientY / viewport.zoom - startY);
      updateNodePosition(id, x, y);
      return;
    }

    // 2. Handle Connection Drawing
    if (connectionSource && canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      setMousePos({
        x: (e.clientX - rect.left - viewport.x) / viewport.zoom,
        y: (e.clientY - rect.top - viewport.y) / viewport.zoom,
      });
      return;
    }

    // 3. Handle Canvas Panning
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
    setConnectionSource(null);
  };

  // Canvas Panning start
  const handleCanvasMouseDown = (e: MouseEvent) => {
    if (e.target === canvasRef.current || (e.target as HTMLElement).classList.contains(styles.gridLayer)) {
      setIsPanning(true);
      setPanStart({
        x: e.clientX - viewport.x,
        y: e.clientY - viewport.y,
      });
    }
  };

  // Start Connection
  const handlePortMouseDown = (e: MouseEvent, nodeId: string) => {
    e.stopPropagation();
    setConnectionSource(nodeId);
    
    const node = nodes.find(n => n.id === nodeId);
    if (connectionSource && canvasRef.current) {
      setMousePos({
        x: node!.position.x + 180, // Approximate port position (right side)
        y: node!.position.y + 35,
      });
    }
  };

  // End Connection
  const handlePortMouseUp = (e: MouseEvent, targetNodeId: string) => {
    e.stopPropagation();
    if (connectionSource && connectionSource !== targetNodeId) {
      connectNodes(connectionSource, targetNodeId);
    }
    setConnectionSource(null);
  };

  // Zoom Operations
  const handleZoom = (factor: number) => {
    setViewport({
      ...viewport,
      zoom: Math.min(Math.max(viewport.zoom * factor, 0.5), 1.8),
    });
  };

  // Group nodes by category
  const categories = Array.from(new Set(NODE_DEFINITIONS.map(n => n.category)));
  const filteredNodes = NODE_DEFINITIONS.filter(
    n =>
      n.name.toLowerCase().includes(nodeSearch.toLowerCase()) &&
      (!activeCategory || n.category === activeCategory)
  );

  return (
    <div className={styles.wrapper}>
      {/* Left Sidebar - Nodes list */}
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
        
        {/* Category pills */}
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

        {/* Dynamic node cards list */}
        <div className={styles.nodeList}>
          {filteredNodes.map(def => (
            <div
              key={def.type}
              className={styles.sidebarNodeCard}
              onClick={() => addNode(def.type, {
                x: 100 - viewport.x / viewport.zoom,
                y: 150 - viewport.y / viewport.zoom
              })}
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

        {/* Templates quick loader */}
        <div className={styles.templatesBlock}>
          <h4>Load Template</h4>
          <div className={styles.templateButtons}>
            <button onClick={() => loadTemplate('invoice')} className="btn-secondary">Invoice OCR</button>
            <button onClick={() => loadTemplate('rag')} className="btn-secondary">RAG Embeds</button>
          </div>
          <button onClick={resetFlow} className={styles.clearBtn}>Clear Canvas</button>
        </div>
      </aside>

      {/* Main Canvas Editor Area */}
      <div className={styles.editorArea}>
        {/* Top toolbar */}
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

        {/* Grid Canvas container */}
        <div
          ref={canvasRef}
          className={styles.canvasContainer}
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
          onMouseDown={handleCanvasMouseDown}
        >
          {/* SVG Overlay layer for connection wires */}
          <svg
            className={styles.svgOverlay}
            style={{
              transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
              transformOrigin: '0 0',
            }}
          >
            {/* Draw existing connections */}
            {edges.map((edge) => {
              const srcNode = nodes.find(n => n.id === edge.source);
              const tgtNode = nodes.find(n => n.id === edge.target);
              
              if (!srcNode || !tgtNode) return null;

              // Calculate connection path points
              const x1 = srcNode.position.x + 200; // Output port (right edge)
              const y1 = srcNode.position.y + 35;  // Middle height
              const x2 = tgtNode.position.x;       // Input port (left edge)
              const y2 = tgtNode.position.y + 35;

              // Bezier control coordinates
              const cx1 = x1 + Math.abs(x2 - x1) * 0.4;
              const cy1 = y1;
              const cx2 = x2 - Math.abs(x2 - x1) * 0.4;
              const cy2 = y2;

              return (
                <g key={edge.id} className={styles.wireGroup}>
                  <path
                    d={`M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`}
                    className={styles.wire}
                  />
                  {/* Small trigger line to allow deleting connection */}
                  <path
                    d={`M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`}
                    className={styles.wireHotspot}
                    onClick={() => deleteEdge(edge.id)}
                  />
                  <circle cx={(x1+x2)/2} cy={(y1+y2)/2} r="6" className={styles.wireDeleteNode} onClick={() => deleteEdge(edge.id)} />
                </g>
              );
            })}

            {/* Connection Preview Wire */}
            {connectionSource && (
              (() => {
                const srcNode = nodes.find(n => n.id === connectionSource);
                if (!srcNode) return null;
                const x1 = srcNode.position.x + 200;
                const y1 = srcNode.position.y + 35;
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

          {/* Interactive node elements layer */}
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
              const definition = NODE_DEFINITIONS.find(def => def.type === node.type);
              const isSelected = selectedNodeId === node.id;
              
              if (!definition) return null;

              return (
                <div
                  key={node.id}
                  className={`${styles.nodeCard} ${isSelected ? styles.nodeSelected : ''}`}
                  style={{
                    left: `${node.position.x}px`,
                    top: `${node.position.y}px`,
                    borderColor: isSelected ? definition.color : 'rgba(255, 255, 255, 0.05)',
                    boxShadow: isSelected ? `0 0 20px ${definition.color}33` : undefined,
                  }}
                  onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                >
                  {/* Left Input Port */}
                  <div
                    className={`${styles.port} ${styles.portInput}`}
                    onMouseUp={(e) => handlePortMouseUp(e, node.id)}
                    title="Input port"
                  >
                    <span className={styles.portDot}></span>
                  </div>

                  {/* Right Output Port */}
                  <div
                    className={`${styles.port} ${styles.portOutput}`}
                    onMouseDown={(e) => handlePortMouseDown(e, node.id)}
                    title="Output port"
                  >
                    <span className={styles.portDot}></span>
                  </div>

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
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Floating zoom controls */}
        <div className={styles.viewportControls}>
          <button onClick={() => handleZoom(1.25)} title="Zoom In">+</button>
          <span>{Math.round(viewport.zoom * 100)}%</span>
          <button onClick={() => handleZoom(0.8)} title="Zoom Out">-</button>
          <button onClick={() => setViewport({ x: 0, y: 0, zoom: 1 })} title="Reset View">⟲</button>
        </div>
      </div>

      {/* Right Sidebar - Config fields */}
      {selectedNodeId && <NodeConfigPanel />}
    </div>
  );
}
