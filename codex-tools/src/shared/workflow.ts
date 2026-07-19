import { readFile } from "node:fs/promises";
import type { N8nWorkflow } from "../schemas/workflow.js";
import { isWorkflow } from "../schemas/workflow.js";
import { resolveRepositoryPath } from "./paths.js";

export async function readWorkflowText(workflowPath = "workflow.json"): Promise<{ path: string; text: string }> {
  const path = resolveRepositoryPath(workflowPath);
  return { path, text: await readFile(path, "utf8") };
}

export async function loadWorkflow(workflowPath = "workflow.json"): Promise<{ path: string; workflow: N8nWorkflow }> {
  const { path, text } = await readWorkflowText(workflowPath);
  const parsed: unknown = JSON.parse(text);
  if (!isWorkflow(parsed)) throw new Error("Workflow must contain nodes[] and connections{} fields");
  return { path, workflow: parsed };
}
