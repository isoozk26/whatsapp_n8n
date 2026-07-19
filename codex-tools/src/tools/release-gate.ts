import type { Finding, ToolResult } from "../schemas/finding.js";
import { severityWeight, toolResult } from "../schemas/finding.js";
import { workflowCheckCodeNodes } from "./workflow-check-code-nodes.js";
import { workflowCheckExpressions } from "./workflow-check-expressions.js";
import { workflowValidateGraph } from "./workflow-validate-graph.js";
import { workflowValidateJson } from "./workflow-validate-json.js";

export interface ReleaseGateInput {
  workflowPath?: string;
  strict?: boolean;
}

export interface ReleaseGateData {
  decision: "PASS" | "PASS WITH WARNINGS" | "BLOCKED";
  score: number;
  p0: number;
  p1: number;
  p2: number;
  checks: Array<{ tool: string; ok: boolean; findingCount: number }>;
}

export async function releaseGate(input: ReleaseGateInput = {}): Promise<ToolResult<ReleaseGateData>> {
  const toolInput = { workflowPath: input.workflowPath };
  const results = await Promise.all([
    workflowValidateJson({ ...toolInput, strict: input.strict }),
    workflowValidateGraph(toolInput),
    workflowCheckCodeNodes(toolInput),
    workflowCheckExpressions(toolInput),
  ]);
  const names = ["workflow_validate_json", "workflow_validate_graph", "workflow_check_code_nodes", "workflow_check_expressions"];
  const findings: Finding[] = results.flatMap((result) => result.findings);
  const counts = {
    p0: findings.filter((finding) => finding.severity === "P0").length,
    p1: findings.filter((finding) => finding.severity === "P1").length,
    p2: findings.filter((finding) => finding.severity === "P2").length,
  };
  const score = Math.max(0, 100 - findings.reduce((sum, finding) => sum + severityWeight[finding.severity], 0));
  const decision: ReleaseGateData["decision"] = counts.p0 ? "BLOCKED" : findings.length ? "PASS WITH WARNINGS" : "PASS";
  const data: ReleaseGateData = {
    decision,
    score,
    ...counts,
    checks: results.map((result, index) => ({ tool: names[index], ok: result.ok, findingCount: result.findings.length })),
  };
  return toolResult(`Release kararı: ${decision} (${score}/100)`, data, findings, { score, ...counts });
}
