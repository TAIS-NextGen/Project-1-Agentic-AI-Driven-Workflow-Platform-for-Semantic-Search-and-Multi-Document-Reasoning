export type AppRoute =
  | 'dashboard'
  | 'workflows'
  | 'documents'
  | 'executions'
  | 'qa-chat'
  | 'settings';

export interface SidebarUser {
  name: string;
  avatarUrl?: string;
}

export type NodeStatus = 'idle' | 'running' | 'success' | 'error' | 'ready';

export interface FlowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  config: Record<string, unknown>;
  status: NodeStatus;
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  sourcePort?: string;
  targetPort?: string;
  condition?: string;
  kind?: 'data' | 'control';
}

export interface WorkflowViewport {
  x: number;
  y: number;
  zoom: number;
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  nodeCount: number;
  runCount: number;
  lastRunAt?: string;
  createdAt: string;
  updatedAt: string;
  nodes: FlowNode[];
  edges: FlowEdge[];
  viewport: WorkflowViewport;
}

export interface DocumentRecord {
  file_id: string;
  filename: string;
  relative_path?: string;
  stored_name?: string;
  size_bytes: number;
  mime_type: string;
  extension: string;
  path?: string;
  source: 'local' | 'cloud-url' | string;
  uploaded_at: string;
  download_url: string;
}

export interface CanvasViewport {
  zoom: number;
  pan: { x: number; y: number };
}
