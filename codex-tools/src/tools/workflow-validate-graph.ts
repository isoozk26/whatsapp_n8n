import type { Finding, ToolResult } from "../schemas/finding.js";
import { toolResult } from "../schemas/finding.js";
import { loadWorkflow } from "../shared/workflow.js";

export interface WorkflowGraphInput {
  workflowPath?: string;
}

interface WorkflowGraphData {
  nodeCount: number;
  reachableNodeCount: number;
  mainEdgeCount: number;
  criticalPaths: Record<string, boolean>;
}

const requiredPaths: Array<[string, string[]]> = [
  ["webhook", ["Webhook1", "Normalize Payload", "Validate Webhook Secret", "Webhook Auth", "Load Admin Filter Settings", "Apply Admin Number Filter", "Is Admin Number?", "Valid Event?", "Ingest Message", "Respond Accepted"]],
  ["aiWorker", ["Schedule Trigger", "OpenAI Circuit Gate", "OpenAI Circuit Open?", "Claim Ready Batches", "Store Context", "AI Agent", "Parse AI Output", "AI Output Valid?", "Complete AI Batch"]],
  ["deliveryWorker", ["Schedule Trigger", "Evolution Circuit Gate", "Evolution Circuit Open?", "Claim Deliveries", "Prepare Delivery", "Send Delivery", "Record Delivery Result"]],
];

export async function workflowValidateGraph(input: WorkflowGraphInput = {}): Promise<ToolResult<WorkflowGraphData>> {
  const findings: Finding[] = [];
  let loaded;
  try {
    loaded = await loadWorkflow(input.workflowPath);
  } catch (error) {
    findings.push({
      id: "GRAPH_WORKFLOW_UNREADABLE", severity: "P0", category: "graph", title: "Workflow grafiği okunamadı",
      evidence: error instanceof Error ? error.message : String(error), location: { file: input.workflowPath || "workflow.json" },
      impact: "Node bağlantıları doğrulanamaz.", recommendation: "Önce workflow_validate_json bulgularını düzeltin.",
    });
    return toolResult("Workflow grafiği doğrulanamadı", { nodeCount: 0, reachableNodeCount: 0, mainEdgeCount: 0, criticalPaths: {} }, findings);
  }

  const { workflow, path } = loaded;
  const names = new Set(workflow.nodes.map((node) => node.name));
  const adjacency = new Map<string, string[]>();
  let edgeCount = 0;
  for (const [source, groups] of Object.entries(workflow.connections)) {
    if (!names.has(source)) {
      findings.push({
        id: "GRAPH_MISSING_SOURCE", severity: "P0", category: "graph", title: "Olmayan kaynak node referansı",
        evidence: source, location: { file: path, node: source }, impact: "Execution yolu çalışamaz.",
        recommendation: "Connection kaynağını mevcut node adıyla eşleştirin.",
      });
    }
    for (const outputs of Object.values(groups)) {
      outputs.forEach((targets, outputIndex) => {
        for (const target of targets || []) {
          edgeCount += 1;
          adjacency.set(source, [...(adjacency.get(source) || []), target.node]);
          if (!names.has(target.node)) {
            findings.push({
              id: "GRAPH_MISSING_TARGET", severity: "P0", category: "graph", title: "Olmayan hedef node referansı",
              evidence: `${source}[${outputIndex}] -> ${target.node}`, location: { file: path, node: source },
              impact: "Execution hedef node'a ilerleyemez.", recommendation: "Connection hedefini mevcut node adıyla eşleştirin.",
            });
          }
          if ((target.index ?? 0) < 0) {
            findings.push({
              id: "GRAPH_INVALID_OUTPUT_INDEX", severity: "P0", category: "graph", title: "Geçersiz bağlantı index'i",
              evidence: `${source} -> ${target.node}: ${target.index}`, location: { file: path, node: source },
              impact: "n8n bağlantıyı çalıştıramaz.", recommendation: "Bağlantı index'ini sıfır veya geçerli giriş index'i yapın.",
            });
          }
        }
      });
    }
  }

  const reachable = new Set<string>();
  const queue = ["Webhook1", "Schedule Trigger"].filter((name) => names.has(name));
  while (queue.length) {
    const current = queue.shift()!;
    if (reachable.has(current)) continue;
    reachable.add(current);
    for (const next of adjacency.get(current) || []) if (!reachable.has(next)) queue.push(next);
  }
  for (const node of workflow.nodes) {
    if (!reachable.has(node.name) && node.type !== "@n8n/n8n-nodes-langchain.lmChatOpenAi") {
      findings.push({
        id: "GRAPH_UNREACHABLE_NODE", severity: "P1", category: "graph", title: "Ana trigger'lardan erişilemeyen node",
        evidence: node.name, location: { file: path, node: node.name }, impact: "Node hiçbir ana execution yolunda çalışmaz.",
        recommendation: "Node'u doğru hatta bağlayın veya kullanılmıyorsa builder'dan kaldırın.",
      });
    }
  }

  const canReach = (start: string, end: string) => {
    const visited = new Set<string>();
    const pending = [start];
    while (pending.length) {
      const current = pending.shift()!;
      if (current === end) return true;
      if (visited.has(current)) continue;
      visited.add(current);
      for (const next of adjacency.get(current) || []) if (!visited.has(next)) pending.push(next);
    }
    return false;
  };
  const hasPath = (pathNodes: string[]) =>
    pathNodes.every((nodeName) => names.has(nodeName))
    && pathNodes.every((nodeName, index) => index === pathNodes.length - 1 || canReach(nodeName, pathNodes[index + 1]));
  const criticalPaths = Object.fromEntries(requiredPaths.map(([name, nodes]) => [name, hasPath(nodes)]));
  for (const [name, valid] of Object.entries(criticalPaths)) {
    if (!valid) findings.push({
      id: `GRAPH_CRITICAL_PATH_${name.toUpperCase()}`, severity: "P0", category: "graph", title: "Kritik workflow yolu kesik",
      evidence: `${name}: ${requiredPaths.find(([key]) => key === name)?.[1].join(" -> ")}`, location: { file: path },
      impact: "Çekirdek müşteri veya worker akışı tamamlanamaz.", recommendation: "Eksik bağlantıyı builder kaynak dosyasında düzeltin.",
    });
  }

  const byName = new Map(workflow.nodes.map((node) => [node.name, node]));
  const aiOutputs = workflow.connections["AI Agent"]?.main || [];
  if (!aiOutputs[1]?.some((target) => target.node === "Prepare AI Failure")) findings.push({
    id: "GRAPH_AI_ERROR_UNHANDLED", severity: "P0", category: "graph", title: "AI hata çıkışı işlenmiyor",
    evidence: "AI Agent output[1] -> Prepare AI Failure bağlantısı yok", location: { file: path, node: "AI Agent" },
    impact: "AI hataları kayıt ve retry mekanizmasına ulaşmaz.", recommendation: "AI Agent hata çıkışını Prepare AI Failure node'una bağlayın.",
  });
  const sendOutputs = workflow.connections["Send Delivery"]?.main || [];
  if (!sendOutputs[1]?.length) findings.push({
    id: "GRAPH_DELIVERY_ERROR_UNHANDLED", severity: "P0", category: "graph", title: "Delivery hata çıkışı işlenmiyor",
    evidence: "Send Delivery output[1] boş", location: { file: path, node: "Send Delivery" }, impact: "Başarısız gönderimler kayda alınmaz.",
    recommendation: "Hata çıkışını Tag Delivery Error ve Record Delivery Result yoluna bağlayın.",
  });
  const adminOutputs = workflow.connections["Is Admin Number?"]?.main || [];
  if (!adminOutputs[0]?.some((target) => target.node === "Respond Admin Filtered")
    || !adminOutputs[1]?.some((target) => target.node === "Valid Event?")) findings.push({
    id: "GRAPH_ADMIN_FILTER_UNHANDLED", severity: "P0", category: "graph", title: "Admin numara filtresi webhook hattında eksik",
    evidence: "Is Admin Number? true -> Respond Admin Filtered ve false -> Valid Event? bağlantısı bekleniyor",
    location: { file: path, node: "Is Admin Number?" }, impact: "0536 hattından gelen mesajlar ingest veya delivery hattına sızabilir.",
    recommendation: "Admin filtresini auth sonrasında, ingest öncesinde tutun ve true dalını sessiz response ile sonlandırın.",
  });
  const respondCount = workflow.nodes.filter((node) => node.type === "n8n-nodes-base.respondToWebhook").length;
  if (!byName.has("Webhook1") || respondCount === 0) findings.push({
    id: "GRAPH_WEBHOOK_NO_RESPONSE", severity: "P0", category: "graph", title: "Webhook response yolu eksik",
    evidence: `respondToWebhook node count: ${respondCount}`, location: { file: path }, impact: "Evolution timeout ve duplicate retry üretebilir.",
    recommendation: "Her webhook sonucunu açık bir Respond to Webhook node'uyla tamamlayın.",
  });

  const data = { nodeCount: workflow.nodes.length, reachableNodeCount: reachable.size, mainEdgeCount: edgeCount, criticalPaths };
  return toolResult(findings.length ? "Workflow grafiğinde bulgular var" : "Workflow grafiği geçerli", data, findings, {
    nodeCount: data.nodeCount,
    reachableNodeCount: data.reachableNodeCount,
    mainEdgeCount: data.mainEdgeCount,
    webhookPathValid: data.criticalPaths.webhook || false,
    aiWorkerPathValid: data.criticalPaths.aiWorker || false,
    deliveryWorkerPathValid: data.criticalPaths.deliveryWorker || false,
  });
}
