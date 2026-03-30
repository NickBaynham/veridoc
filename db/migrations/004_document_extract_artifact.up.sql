-- Full extracted plain text may also live in object storage (UTF-8 .txt) for reprocessing / audit.
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS extract_artifact_key TEXT;

COMMENT ON COLUMN documents.extract_artifact_key IS
  'S3/MinIO key for derived extracted text (e.g. artifacts/{document_id}/extracted.txt); nullable if extract skipped or failed.';
