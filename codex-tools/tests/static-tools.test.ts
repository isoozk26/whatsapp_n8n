import assert from "node:assert/strict";
import { test } from "node:test";
import { analyzeCodeNode } from "../src/tools/workflow-check-code-nodes.js";
import { releaseGate } from "../src/tools/release-gate.js";
import { workflowCheckCodeNodes } from "../src/tools/workflow-check-code-nodes.js";

test("undefined identifiers in an n8n Code node are P0", () => {
  const findings = analyzeCodeNode(
    "Prepare AI Failure fixture",
    "const catalogEmoji = catalog.status === 'unique' ? 'ok' : 'x'; return { json: { reply, catalogEmoji } };",
  );
  assert(findings.some((finding) => finding.id === "CODE_NODE_UNDEFINED_IDENTIFIER" && finding.evidence.includes("catalog")));
  assert(findings.some((finding) => finding.id === "CODE_NODE_UNDEFINED_IDENTIFIER" && finding.evidence.includes("reply")));
  assert(findings.every((finding) => finding.severity === "P0"));
});

test("current workflow Code nodes have no undefined identifiers", async () => {
  const result = await workflowCheckCodeNodes({ workflowPath: "workflow.json" });
  assert.equal(result.ok, true, JSON.stringify(result.findings, null, 2));
});

test("current workflow passes the static release gate", async () => {
  const result = await releaseGate({ workflowPath: "workflow.json" });
  assert.equal(result.data?.decision, "PASS", JSON.stringify(result.findings, null, 2));
  assert.equal(result.ok, true);
});
