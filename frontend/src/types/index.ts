export type AppRoute =
  | 'dashboard'
  | 'workflows'
  | 'documents'
  | 'executions'
  | 'settings';

export interface SidebarUser {
  name: string;
  avatarUrl?: string;
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
}

export interface CanvasViewport {
  zoom: number;
  pan: { x: number; y: number };
}
