import { releaseGate } from "./tools/release-gate.js";
import { workflowCheckCodeNodes } from "./tools/workflow-check-code-nodes.js";
import { workflowCheckExpressions } from "./tools/workflow-check-expressions.js";
import { workflowValidateGraph } from "./tools/workflow-validate-graph.js";
import { workflowValidateJson } from "./tools/workflow-validate-json.js";

const command = process.argv[2] || "release_gate";
const workflowPath = process.argv[3] || "workflow.json";
const strict = process.argv.includes("--strict");

const commands = {
  workflow_validate_json: () => workflowValidateJson({ workflowPath, strict }),
  workflow_validate_graph: () => workflowValidateGraph({ workflowPath }),
  workflow_check_code_nodes: () => workflowCheckCodeNodes({ workflowPath }),
  workflow_check_expressions: () => workflowCheckExpressions({ workflowPath }),
  release_gate: () => releaseGate({ workflowPath, strict }),
};

if (!(command in commands)) {
  throw new Error(`Unknown command: ${command}. Available: ${Object.keys(commands).join(", ")}`);
}

const result = await commands[command as keyof typeof commands]();
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
process.exitCode = result.ok ? 0 : 1;
