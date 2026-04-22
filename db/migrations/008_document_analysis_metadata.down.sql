DROP TRIGGER IF EXISTS trg_document_tags_updated_at ON document_tags;

DROP INDEX IF EXISTS ix_document_tags_tag_normalized;
DROP INDEX IF EXISTS ix_document_tags_document_id;
DROP INDEX IF EXISTS uq_document_tags_doc_norm_source;

DROP TABLE IF EXISTS document_tags;

DROP INDEX IF EXISTS ix_documents_analysis_metadata_gin;

ALTER TABLE documents DROP COLUMN IF EXISTS analysis_metadata;
