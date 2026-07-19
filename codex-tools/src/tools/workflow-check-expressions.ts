import type { Finding, ToolResult } from "../schemas/finding.js";
import { toolResult } from "../schemas/finding.js";
import { loadWorkflow } from "../shared/workflow.js";

export interface WorkflowExpressionInput {
  workflowPath?: string;
}

interface ExpressionCheckData {
  expressionCount: number;
  nodeReferenceCount: number;
  postgresNodeCount: number;
}

function collectExpressions(value: unknown, location = "parameters", output: Array<{ location: string; expression: string }> = []) {
  if (typeof value === "string" && value.includes("={{")) output.push({ location, expression: value });
  else if (Array.isArray(value)) value.forEach((item, index) => collectExpressions(item, `${location}[${index}]`, output));
  else if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, item]) => collectExpressions(item, `${location}.${key}`, output));
  }
  return output;
}

function countTopLevelArrayItems(expression: string): number | undefined {
  const arrayStart = expression.indexOf("[");
  const arrayEnd = expression.lastIndexOf("]");
  if (arrayStart < 0 || arrayEnd <= arrayStart) return undefined;
  const content = expression.slice(arrayStart + 1, arrayEnd).trim();
  if (!content) return 0;
  let square = 0;
  let round = 0;
  let curly = 0;
  let quote = "";
  let escaped = false;
  let count = 1;
  for (const char of content) {
    if (escaped) { escaped = false; continue; }
    if (quote) {
      if (char === "\\") escaped = true;
      else if (char === quote) quote = "";
      continue;
    }
    if (char === "'" || char === '"' || char === "`") { quote = char; continue; }
    if (char === "[") square += 1;
    else if (char === "]") square -= 1;
    else if (char === "(") round += 1;
    else if (char === ")") round -= 1;
    else if (char === "{") curly += 1;
    else if (char === "}") curly -= 1;
    else if (char === "," && square === 0 && round === 0 && curly === 0) count += 1;
  }
  return count;
}

export async function workflowCheckExpressions(input: WorkflowExpressionInput = {}): Promise<ToolResult<ExpressionCheckData>> {
  const findings: Finding[] = [];
  let loaded;
  try {
    loaded = await loadWorkflow(input.workflowPath);
  } catch (error) {
    findings.push({
      id: "EXPRESSION_WORKFLOW_UNREADABLE", severity: "P0", category: "syntax", title: "Workflow expression'ları okunamadı",
      evidence: error instanceof Error ? error.message : String(error), location: { file: input.workflowPath || "workflow.json" },
      impact: "Expression ve SQL parametreleri doğrulanamaz.", recommendation: "Önce workflow JSON hatalarını düzeltin.",
    });
    return toolResult("Expression analizi çalışmadı", { expressionCount: 0, nodeReferenceCount: 0, postgresNodeCount: 0 }, findings);
  }

  const names = new Set(loaded.workflow.nodes.map((node) => node.name));
  let expressionCount = 0;
  let nodeReferenceCount = 0;
  let postgresNodeCount = 0;
  for (const node of loaded.workflow.nodes) {
    const expressions = collectExpressions(node.parameters || {});
    expressionCount += expressions.length;
    for (const entry of expressions) {
      for (const match of entry.expression.matchAll(/\$\(\s*['"]([^'"]+)['"]\s*\)/g)) {
        nodeReferenceCount += 1;
        if (!names.has(match[1])) findings.push({
          id: "EXPRESSION_MISSING_NODE", severity: "P0", category: "graph", title: "Expression olmayan node'a referans veriyor",
          evidence: `${entry.location}: ${match[1]}`, location: { file: loaded.path, node: node.name },
          impact: "Expression çalışma zamanında node verisini çözemeyebilir.", recommendation: "Expression içindeki node adını mevcut node adıyla eşleştirin.",
        });
      }
    }

    if (node.type === "n8n-nodes-base.postgres") {
      postgresNodeCount += 1;
      const query = String(node.parameters?.query || "");
      const replacements = String((node.parameters?.options as Record<string, unknown> | undefined)?.queryReplacement || node.parameters?.queryReplacement || "");
      const placeholders = [...query.matchAll(/\$(\d+)/g)].map((match) => Number(match[1]));
      const expected = placeholders.length ? Math.max(...placeholders) : 0;
      const actual = countTopLevelArrayItems(replacements);
      const contiguous = expected === 0 || Array.from({ length: expected }, (_, index) => index + 1).every((value) => placeholders.includes(value));
      if (!contiguous || actual === undefined || actual !== expected) findings.push({
        id: "EXPRESSION_SQL_PARAMETER_MISMATCH", severity: "P0", category: "database", title: "PostgreSQL placeholder ve replacement sayısı uyuşmuyor",
        evidence: `${node.name}: expected=${expected}, replacements=${actual ?? "unparsed"}, placeholders=${[...new Set(placeholders)].join(",")}`,
        location: { file: loaded.path, node: node.name }, impact: "SQL node çalışma zamanında parametre hatası verir veya yanlış değeri bağlar.",
        recommendation: "$1…$n placeholder dizisini kesintisiz yapın ve queryReplacement dizisini aynı sayıda tutun.",
      });
    }
  }

  const data = { expressionCount, nodeReferenceCount, postgresNodeCount };
  return toolResult(findings.length ? "Expression analizinde bulgular var" : "Workflow expression'ları geçerli", data, findings, data);
}
