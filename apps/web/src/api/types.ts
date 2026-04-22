export interface DocumentSummary {
  id: string;
  collection_id: string;
  title: string | null;
  status: string;
  original_filename: string | null;
  content_type: string | null;
  storage_key?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  total: number;
}

export interface DocumentSource {
  id: string;
  document_id: string;
  source_kind: string;
  locator: string;
  mime_type: string | null;
  byte_length: number | null;
  created_at: string;
  updated_at: string;
}

export interface CanonicalScore {
  factuality_score: number | null;
  ai_generation_probability: number | null;
  fallacy_score: number | null;
  confidence_score: number | null;
  scorer_name: string | null;
  scorer_version: string | null;
}

export interface DocumentTag {
  id: string;
  tag: string;
  source: string;
  confidence: number | null;
  created_at: string;
}

export interface DocumentDetail extends DocumentSummary {
  sources: DocumentSource[];
  body_text: string | null;
  canonical_score?: CanonicalScore | null;
  analysis_metadata?: Record<string, unknown>;
  tags?: DocumentTag[];
}

export interface PipelineEvent {
  id: string;
  step_index: number;
  event_type: string;
  stage: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface PipelineRun {
  id: string;
  document_id: string;
  status: string;
  stage: string;
  started_at: string | null;
  completed_at: string | null;
  error_detail: Record<string, unknown> | null;
  run_metadata: Record<string, unknown>;
}

export interface DocumentPipelineResponse {
  document_id: string;
  document_status: string;
  run: PipelineRun | null;
  events: PipelineEvent[];
}

export interface FacetBucket {
  key: string | null;
  count: number;
}

export interface CollectionPostgresStats {
  document_count: number;
  scored_documents: number;
  avg_factuality: number | null;
  avg_ai_probability: number | null;
  suspicious_count: number;
}

export interface CollectionAnalyticsResponse {
  collection_id: string;
  index_total: number;
  index_status: string;
  index_message?: string | null;
  facets: Record<string, FacetBucket[]> | null;
  postgres: CollectionPostgresStats;
}

export interface CollectionRow {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  document_count: number;
  created_at: string;
}

export interface CollectionListResponse {
  collections: CollectionRow[];
}

/** GET /api/v1/collections/{id} — workspace header summary. */
export interface CollectionDetail {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string | null;
  document_count: number;
  last_updated: string | null;
  status_breakdown: Record<string, number>;
  failed_document_count: number;
  in_progress_document_count: number;
  avg_canonical_factuality: number | null;
  created_at: string;
}

/** One row in GET /api/v1/collections/{id}/documents. */
export interface CollectionDocumentItem extends DocumentSummary {
  canonical_score?: CanonicalScore | null;
  primary_source_kind?: string | null;
}

export interface CollectionDocumentsListResponse {
  items: CollectionDocumentItem[];
  total: number;
  limit: number;
  offset: number;
  collection_id: string;
}

export interface CollectionActivityItem {
  id: string;
  document_id: string;
  document_title: string | null;
  pipeline_run_id: string;
  event_type: string;
  stage: string | null;
  step_index: number;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface CollectionActivityResponse {
  items: CollectionActivityItem[];
  collection_id: string;
}

export interface SearchHit {
  document_id: string;
  title: string | null;
  score: number | null;
  snippet: string;
  collection_id?: string;
  ingest_source?: string;
  content_type?: string | null;
  status?: string;
  tags?: string[];
}

export interface SearchResponse {
  query: string;
  limit: number;
  /** 0–1 blend with deterministic pseudo-embeddings when `q` is non-empty. */
  semantic_weight?: number;
  hits: SearchHit[];
  total: number;
  index_status: string;
  message?: string | null;
  /** Present when `include_facets=true` on the API. */
  facets?: Record<string, FacetBucket[]> | null;
}

export interface IntakeResponse {
  document_id: string;
  status: string;
  storage_key: string;
  job_id?: string | null;
  enqueue_error?: string | null;
}

export interface UrlIntakeResponse {
  document_id: string;
  status: string;
  source_url: string;
  job_id?: string | null;
  enqueue_error?: string | null;
}

/** Values match `app.domain.knowledge_model_constants.MODEL_TYPES`. */
export type KnowledgeModelTypeId =
  | "summary"
  | "claims_evidence"
  | "software_service"
  | "test_knowledge";

export interface KnowledgeModelVersionSummary {
  id: string;
  version_number: number;
  build_status: string;
  created_at: string;
  completed_at?: string | null;
  asset_count: number;
  error_message?: string | null;
}

export interface KnowledgeModelListItem {
  id: string;
  collection_id: string;
  name: string;
  description: string | null;
  model_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  latest_version: KnowledgeModelVersionSummary | null;
}

export interface KnowledgeModelListResponse {
  items: KnowledgeModelListItem[];
  collection_id: string;
}

export interface KnowledgeModelVersion {
  id: string;
  knowledge_model_id: string;
  version_number: number;
  build_status: string;
  created_at: string;
  completed_at?: string | null;
  error_message?: string | null;
  asset_count: number;
}

export interface KnowledgeModelDetail {
  id: string;
  collection_id: string;
  name: string;
  description: string | null;
  model_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  latest_version: KnowledgeModelVersionSummary | null;
  summary_json: Record<string, unknown> | null;
}

export interface KnowledgeModelVersionDetail {
  id: string;
  knowledge_model_id: string;
  version_number: number;
  build_status: string;
  source_selection_snapshot_json: Record<string, unknown>;
  build_profile_json: Record<string, unknown>;
  summary_json: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  asset_count: number;
}

export interface KnowledgeModelVersionListResponse {
  items: KnowledgeModelVersion[];
  knowledge_model_id: string;
}

export interface KnowledgeModelAsset {
  id: string;
  document_id: string;
  title: string | null;
  original_filename: string | null;
  inclusion_reason: string | null;
  source_weight: number | null;
  created_at: string;
}

export interface KnowledgeModelAssetListResponse {
  items: KnowledgeModelAsset[];
  model_version_id: string;
}

export interface KnowledgeModelCreateBody {
  name: string;
  description?: string | null;
  model_type: KnowledgeModelTypeId;
  selected_document_ids: string[];
  build_profile?: Record<string, unknown>;
}

export interface KnowledgeModelCreateResponse {
  knowledge_model: KnowledgeModelListItem;
  version: KnowledgeModelVersion;
  build_job_id: string | null;
}

export type ModelWritebackKind =
  | "finding"
  | "risk"
  | "test_artifact"
  | "execution_result"
  | "evidence_note"
  | "contradiction";

export type ModelWritebackVerification =
  | "proposed"
  | "accepted"
  | "rejected"
  | "auto_ingested"
  | "superseded";

export interface ModelWriteback {
  id: string;
  knowledge_model_id: string;
  knowledge_model_version_id: string | null;
  artifact_kind: ModelWritebackKind;
  title: string;
  summary: string | null;
  payload_json: Record<string, unknown>;
  origin_type: string;
  origin_id: string | null;
  verification_state: ModelWritebackVerification;
  confidence_score: number | null;
  reviewer_id: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  supersedes_id: string | null;
  related_document_id: string | null;
  related_asset_id: string | null;
  related_writeback_id: string | null;
  related_entity_id: string | null;
  related_claim_id: string | null;
  evidence_refs_json: unknown[];
  created_at: string;
  updated_at: string;
}

export interface ModelWritebackListResponse {
  items: ModelWriteback[];
  knowledge_model_id: string;
  limit: number;
  offset: number;
}

export interface ModelActivityItem {
  id: string;
  occurred_at: string;
  event_type: string;
  title: string;
  summary?: string | null;
  knowledge_model_version_id?: string | null;
  artifact_kind?: string | null;
  artifact_id?: string | null;
  verification_state?: string | null;
  origin_type?: string | null;
  origin_id?: string | null;
  payload: Record<string, unknown>;
}

export interface ModelActivityResponse {
  items: ModelActivityItem[];
  knowledge_model_id: string;
}
