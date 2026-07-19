export type Severity = "P0" | "P1" | "P2" | "INFO";

export type FindingCategory =
  | "syntax"
  | "graph"
  | "security"
  | "database"
  | "concurrency"
  | "integration"
  | "policy"
  | "operations";

export interface Finding {
  id: string;
  severity: Severity;
  category: FindingCategory;
  title: string;
  evidence: string;
  location?: {
    node?: string;
    file?: string;
    function?: string;
    line?: number;
  };
  impact: string;
  recommendation: string;
}

export interface ToolResult<T> {
  ok: boolean;
  summary: string;
  data?: T;
  findings: Finding[];
  metrics?: Record<string, number | string | boolean>;
}

export function toolResult<T>(
  summary: string,
  data: T,
  findings: Finding[],
  metrics?: Record<string, number | string | boolean>,
): ToolResult<T> {
  return {
    ok: !findings.some((finding) => finding.severity === "P0"),
    summary,
    data,
    findings,
    ...(metrics ? { metrics } : {}),
  };
}

export const severityWeight: Record<Severity, number> = {
  P0: 25,
  P1: 10,
  P2: 3,
  INFO: 0,
};
