#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import type { ToolResult } from "./schemas/finding.js";
import { releaseGate } from "./tools/release-gate.js";
import { workflowCheckCodeNodes } from "./tools/workflow-check-code-nodes.js";
import { workflowCheckExpressions } from "./tools/workflow-check-expressions.js";
import { workflowValidateGraph } from "./tools/workflow-validate-graph.js";
import { workflowValidateJson } from "./tools/workflow-validate-json.js";

const server = new McpServer(
  { name: "whatsapp-ai-mcp", version: "2.1.0" },
  {
    instructions:
      "Read-only static validation tools for the FiltreOto n8n workflow. Run release_gate before proposing a deploy. These tools never deploy, mutate production data, or send messages.",
  },
);

const workflowPath = z.string().default("workflow.json").describe("Repository-relative n8n workflow JSON path");

function response(result: ToolResult<unknown>) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
    isError: !result.ok,
  };
}

server.registerTool(
  "workflow_validate_json",
  { description: "Validate n8n workflow JSON shape, unique node IDs/names and credential references.", inputSchema: { workflowPath, strict: z.boolean().optional() } },
  async (input) => response(await workflowValidateJson(input)),
);
server.registerTool(
  "workflow_validate_graph",
  { description: "Validate node connections and the webhook, AI worker and delivery worker paths.", inputSchema: { workflowPath } },
  async (input) => response(await workflowValidateGraph(input)),
);
server.registerTool(
  "workflow_check_code_nodes",
  { description: "Statically check all n8n Code nodes for syntax errors and undefined identifiers.", inputSchema: { workflowPath } },
  async (input) => response(await workflowCheckCodeNodes(input)),
);
server.registerTool(
  "workflow_check_expressions",
  { description: "Validate n8n node references and PostgreSQL placeholder/replacement counts.", inputSchema: { workflowPath } },
  async (input) => response(await workflowCheckExpressions(input)),
);
server.registerTool(
  "release_gate",
  { description: "Combine all static checks and return PASS, PASS WITH WARNINGS or BLOCKED.", inputSchema: { workflowPath, strict: z.boolean().optional() } },
  async (input) => response(await releaseGate(input)),
);

const transport = new StdioServerTransport();
await server.connect(transport);
