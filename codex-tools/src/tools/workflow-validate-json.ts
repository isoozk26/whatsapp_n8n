import type { Finding, ToolResult } from "../schemas/finding.js";
import { toolResult } from "../schemas/finding.js";
import { isWorkflow } from "../schemas/workflow.js";
import { readWorkflowText } from "../shared/workflow.js";

export interface WorkflowValidateInput {
  workflowPath?: string;
  strict?: boolean;
}

export interface WorkflowValidateData {
  validJson: boolean;
  workflowName?: string;
  nodeCount: number;
  connectionCount: number;
}

export async function workflowValidateJson(input: WorkflowValidateInput = {}): Promise<ToolResult<WorkflowValidateData>> {
  const findings: Finding[] = [];
  let parsed: unknown;
  let filePath = input.workflowPath || "workflow.json";

  try {
    const loaded = await readWorkflowText(filePath);
    filePath = loaded.path;
    parsed = JSON.parse(loaded.text);
  } catch (error) {
    findings.push({
      id: "WORKFLOW_JSON_INVALID",
      severity: "P0",
      category: "syntax",
      title: "Workflow JSON okunamadı",
      evidence: error instanceof Error ? error.message : String(error),
      location: { file: filePath },
      impact: "n8n workflow artifact'i import veya analiz edilemez.",
      recommendation: "JSON üretimini düzeltin ve builder'dan artifact'i yeniden oluşturun.",
    });
    return toolResult("Workflow JSON geçersiz", { validJson: false, nodeCount: 0, connectionCount: 0 }, findings);
  }

  if (!isWorkflow(parsed)) {
    findings.push({
      id: "WORKFLOW_SHAPE_INVALID",
      severity: "P0",
      category: "syntax",
      title: "Zorunlu workflow alanları eksik",
      evidence: "nodes[] veya connections{} alanı bulunamadı",
      location: { file: filePath },
      impact: "Artifact geçerli n8n workflow sözleşmesini karşılamıyor.",
      recommendation: "Builder çıktısına nodes ve connections alanlarını ekleyin.",
    });
    return toolResult("Workflow yapısı geçersiz", { validJson: true, nodeCount: 0, connectionCount: 0 }, findings);
  }

  const ids = new Map<string, string>();
  const names = new Set<string>();
  for (const node of parsed.nodes) {
    if (!node.name || !node.type) {
      findings.push({
        id: "WORKFLOW_NODE_SHAPE",
        severity: "P0",
        category: "syntax",
        title: "Node adı veya tipi eksik",
        evidence: JSON.stringify({ name: node.name, type: node.type }),
        location: { file: filePath, node: node.name },
        impact: "n8n node'u yükleyemez veya çalıştıramaz.",
        recommendation: "Her node için benzersiz name ve geçerli type tanımlayın.",
      });
    }
    if (names.has(node.name)) {
      findings.push({
        id: "WORKFLOW_DUPLICATE_NODE_NAME",
        severity: "P0",
        category: "graph",
        title: "Tekrarlanan node adı",
        evidence: node.name,
        location: { file: filePath, node: node.name },
        impact: "Expression ve connection referansları belirsiz hale gelir.",
        recommendation: "Node adlarını benzersiz yapın.",
      });
    }
    names.add(node.name);
    if (node.id) {
      const previous = ids.get(node.id);
      if (previous) {
        findings.push({
          id: "WORKFLOW_DUPLICATE_NODE_ID",
          severity: "P0",
          category: "graph",
          title: "Tekrarlanan node ID",
          evidence: `${node.id}: ${previous}, ${node.name}`,
          location: { file: filePath, node: node.name },
          impact: "n8n import ve execution eşleştirmesi bozulabilir.",
          recommendation: "Builder içinde deterministik fakat benzersiz ID üretin.",
        });
      }
      ids.set(node.id, node.name);
    }
    for (const [credentialType, credential] of Object.entries(node.credentials || {})) {
      if (!credential || typeof credential !== "object" || !("name" in credential) || !("id" in credential)) {
        findings.push({
          id: "WORKFLOW_CREDENTIAL_REFERENCE",
          severity: input.strict ? "P0" : "P1",
          category: "security",
          title: "Eksik credential referansı",
          evidence: `${node.name}: ${credentialType}`,
          location: { file: filePath, node: node.name },
          impact: "Node canlı execution sırasında credential hatası verebilir.",
          recommendation: "Credential name ve id referanslarını deploy aşamasında çözümleyin.",
        });
      }
    }
  }

  const connectionCount = Object.values(parsed.connections).reduce(
    (total, groups) => total + Object.values(groups).reduce(
      (groupTotal, outputs) => groupTotal + outputs.reduce((sum, output) => sum + (output?.length || 0), 0),
      0,
    ),
    0,
  );
  const data = {
    validJson: true,
    workflowName: parsed.name,
    nodeCount: parsed.nodes.length,
    connectionCount,
  };
  return toolResult(findings.length ? "Workflow JSON bulgularla doğrulandı" : "Workflow JSON geçerli", data, findings, {
    validJson: data.validJson,
    workflowName: data.workflowName || "unknown",
    nodeCount: data.nodeCount,
    connectionCount: data.connectionCount,
  });
}
