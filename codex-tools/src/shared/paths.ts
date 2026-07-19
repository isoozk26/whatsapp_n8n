import { resolve, sep } from "node:path";

export function repositoryRoot(): string {
  return resolve(process.env.WHATSAPP_AI_REPO_ROOT || process.cwd());
}

export function resolveRepositoryPath(inputPath = "workflow.json"): string {
  const root = repositoryRoot();
  const target = resolve(root, inputPath);
  if (target !== root && !target.startsWith(`${root}${sep}`)) {
    throw new Error(`Path escapes repository root: ${inputPath}`);
  }
  return target;
}
