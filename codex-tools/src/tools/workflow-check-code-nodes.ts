import ts from "typescript";
import type { Finding, ToolResult } from "../schemas/finding.js";
import { toolResult } from "../schemas/finding.js";
import { loadWorkflow } from "../shared/workflow.js";

export interface WorkflowCodeInput {
  workflowPath?: string;
}

interface CodeCheckData {
  codeNodeCount: number;
  checkedNodeCount: number;
  diagnosticCount: number;
}

const prelude = `
declare const $json: any;
declare const $input: any;
declare const $item: any;
declare const $items: any;
declare const $node: any;
declare const $workflow: any;
declare const $execution: any;
declare const $runIndex: number;
declare const $mode: string;
declare const $vars: Record<string, any>;
declare const $env: Record<string, string | undefined>;
declare function $getWorkflowStaticData(scope: string): any;
declare const Buffer: any;
declare const crypto: any;
declare const fetch: any;
declare function $(name: string): any;
async function __n8nCodeNode() {
`;
const postlude = "\n}\n";
const preludeLineCount = prelude.split(/\r?\n/).length - 1;

function diagnosticText(diagnostic: ts.Diagnostic): string {
  return ts.flattenDiagnosticMessageText(diagnostic.messageText, " ");
}

export function analyzeCodeNode(nodeName: string, code: string, file = "workflow.json"): Finding[] {
  const virtualName = `n8n-${nodeName.replace(/[^a-z0-9]+/gi, "-")}.ts`;
  const sourceText = `${prelude}${code}${postlude}`;
  const options: ts.CompilerOptions = {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.NodeNext,
    strict: false,
    noImplicitAny: false,
    noEmit: true,
    skipLibCheck: true,
    types: [],
  };
  const defaultHost = ts.createCompilerHost(options, true);
  const source = ts.createSourceFile(virtualName, sourceText, options.target!, true, ts.ScriptKind.TS);
  const getSourceFile = defaultHost.getSourceFile.bind(defaultHost);
  const fileExists = defaultHost.fileExists.bind(defaultHost);
  const readFile = defaultHost.readFile.bind(defaultHost);
  defaultHost.getSourceFile = (name, languageVersion, onError, shouldCreateNewSourceFile) =>
    name === virtualName ? source : getSourceFile(name, languageVersion, onError, shouldCreateNewSourceFile);
  defaultHost.fileExists = (name) => name === virtualName || fileExists(name);
  defaultHost.readFile = (name) => name === virtualName ? sourceText : readFile(name);

  const program = ts.createProgram([virtualName], options, defaultHost);
  const diagnostics = ts.getPreEmitDiagnostics(program, source)
    .filter((diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error)
    .filter((diagnostic) => diagnostic.file?.fileName === virtualName)
    .filter((diagnostic) => diagnostic.code === 2304 || diagnostic.code === 2552 || diagnostic.code === 18004 || diagnostic.code < 2000);

  return diagnostics.map((diagnostic, index) => {
    const position = diagnostic.start === undefined ? undefined : source.getLineAndCharacterOfPosition(diagnostic.start);
    const sourceLine = position ? Math.max(1, position.line + 1 - preludeLineCount) : undefined;
    const message = diagnosticText(diagnostic);
    const undefinedReference = diagnostic.code === 2304 || diagnostic.code === 2552 || diagnostic.code === 18004;
    return {
      id: undefinedReference ? "CODE_NODE_UNDEFINED_IDENTIFIER" : "CODE_NODE_SYNTAX_ERROR",
      severity: "P0",
      category: "syntax",
      title: undefinedReference ? "Code node tanımsız identifier kullanıyor" : "Code node JavaScript sözdizimi hatası",
      evidence: `TS${diagnostic.code}: ${message}`,
      location: { file, node: nodeName, line: sourceLine },
      impact: undefinedReference
        ? "İlgili execution yolu çalışma zamanında ReferenceError ile kesilebilir."
        : "Code node hiç çalıştırılamaz.",
      recommendation: undefinedReference
        ? "Identifier'ı aynı node kapsamında tanımlayın veya yanlış node'a taşınmış kodu asıl kapsamına alın."
        : "Code node sözdizimini düzeltip davranış testini yeniden çalıştırın.",
    } satisfies Finding;
  });
}

export async function workflowCheckCodeNodes(input: WorkflowCodeInput = {}): Promise<ToolResult<CodeCheckData>> {
  const findings: Finding[] = [];
  let loaded;
  try {
    loaded = await loadWorkflow(input.workflowPath);
  } catch (error) {
    findings.push({
      id: "CODE_WORKFLOW_UNREADABLE", severity: "P0", category: "syntax", title: "Code node'lar okunamadı",
      evidence: error instanceof Error ? error.message : String(error), location: { file: input.workflowPath || "workflow.json" },
      impact: "Code node statik analizi yapılamaz.", recommendation: "Önce workflow JSON hatalarını düzeltin.",
    });
    return toolResult("Code node analizi çalışmadı", { codeNodeCount: 0, checkedNodeCount: 0, diagnosticCount: findings.length }, findings);
  }

  const codeNodes = loaded.workflow.nodes.filter((node) => typeof node.parameters?.jsCode === "string");
  for (const node of codeNodes) {
    findings.push(...analyzeCodeNode(node.name, String(node.parameters?.jsCode || ""), loaded.path));
  }
  const data = { codeNodeCount: codeNodes.length, checkedNodeCount: codeNodes.length, diagnosticCount: findings.length };
  return toolResult(findings.length ? "Code node analizinde bloklayıcı bulgular var" : "Tüm Code node'lar statik analizden geçti", data, findings, data);
}
