import assert from "node:assert/strict";
import { resolve } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const root = resolve(import.meta.dirname, "../..");
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [resolve(root, "node_modules/tsx/dist/cli.mjs"), resolve(root, "codex-tools/src/index.ts")],
  cwd: root,
  stderr: "pipe",
});
const client = new Client({ name: "whatsapp-ai-mcp-smoke", version: "2.1.0" });

try {
  await client.connect(transport);
  const listed = await client.listTools();
  const names = listed.tools.map((tool) => tool.name).sort();
  assert.deepEqual(names, [
    "release_gate",
    "workflow_check_code_nodes",
    "workflow_check_expressions",
    "workflow_validate_graph",
    "workflow_validate_json",
  ]);
  const called = await client.callTool({ name: "release_gate", arguments: { workflowPath: "workflow.json" } });
  assert.equal(called.isError, false, JSON.stringify(called.content));
  const text = called.content.find((item) => item.type === "text");
  assert(text && text.type === "text");
  const result = JSON.parse(text.text) as { data?: { decision?: string }; ok?: boolean };
  assert.equal(result.ok, true);
  assert.equal(result.data?.decision, "PASS");
  process.stdout.write(`[PASS] MCP listed ${names.length} tools and release_gate returned PASS\n`);
} finally {
  await client.close();
}
