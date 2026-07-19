export interface N8nConnectionTarget {
  node: string;
  type?: string;
  index?: number;
}

export interface N8nNode {
  id?: string;
  name: string;
  type: string;
  typeVersion?: number;
  parameters?: Record<string, unknown>;
  credentials?: Record<string, unknown>;
}

export interface N8nWorkflow {
  name?: string;
  active?: boolean;
  nodes: N8nNode[];
  connections: Record<string, Record<string, Array<Array<N8nConnectionTarget>>>>;
  settings?: Record<string, unknown>;
}

export function isWorkflow(value: unknown): value is N8nWorkflow {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<N8nWorkflow>;
  return Array.isArray(candidate.nodes) && Boolean(candidate.connections) && typeof candidate.connections === "object";
}
