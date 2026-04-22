-- Pipeline-written analysis JSON + normalized tags (see docs/document-metadata-design.md).

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS analysis_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN documents.analysis_metadata IS
  'Pipeline sections (extract, enrich, tagging); not end-user editable via PATCH.';

CREATE INDEX IF NOT EXISTS ix_documents_analysis_metadata_gin
  ON documents USING gin (analysis_metadata jsonb_path_ops);

CREATE TABLE document_tags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
  tag text NOT NULL,
  tag_normalized text NOT NULL,
  source text NOT NULL,
  pipeline_run_id uuid REFERENCES pipeline_runs (id) ON DELETE SET NULL,
  confidence numeric(6, 5),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT document_tags_tag_nonempty_chk CHECK (length(trim(tag)) > 0),
  CONSTRAINT document_tags_tag_normalized_nonempty_chk CHECK (length(trim(tag_normalized)) > 0),
  CONSTRAINT document_tags_source_chk CHECK (
    source IN ('user', 'pipeline', 'rule', 'import')
  ),
  CONSTRAINT document_tags_confidence_chk CHECK (
    confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
  )
);

CREATE UNIQUE INDEX uq_document_tags_doc_norm_source
  ON document_tags (document_id, tag_normalized, source);

CREATE INDEX ix_document_tags_document_id ON document_tags (document_id);
CREATE INDEX ix_document_tags_tag_normalized ON document_tags (tag_normalized);

CREATE TRIGGER trg_document_tags_updated_at
  BEFORE UPDATE ON document_tags
  FOR EACH ROW EXECUTE PROCEDURE verifiedsignal_set_updated_at();

COMMENT ON TABLE document_tags IS
  'Filterable labels per document with source (user vs pipeline) and optional confidence.';
