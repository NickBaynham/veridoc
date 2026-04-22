import type { KnowledgeModelTypeId } from "../api/types";

export interface KnowledgeModelTypeOption {
  id: KnowledgeModelTypeId;
  label: string;
}

export const KNOWLEDGE_MODEL_TYPE_OPTIONS: KnowledgeModelTypeOption[] = [
  { id: "summary", label: "Summary" },
  { id: "claims_evidence", label: "Claims & Evidence" },
  { id: "software_service", label: "Software Service" },
  { id: "test_knowledge", label: "Test Knowledge" },
];

export function knowledgeModelTypeLabel(modelType: KnowledgeModelTypeId | string): string {
  const hit = KNOWLEDGE_MODEL_TYPE_OPTIONS.find((x) => x.id === modelType);
  if (hit) return hit.label;
  return String(modelType || "unknown");
}
