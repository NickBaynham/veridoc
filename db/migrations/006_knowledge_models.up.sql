-- Knowledge models: versioned, curated representations built from collection documents.
-- V1: canonical metadata, assets, and build runs in Postgres; search/index projections are future work.

CREATE TABLE knowledge_models (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collection_id   UUID NOT NULL REFERENCES collections (id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  description     TEXT,
  model_type      VARCHAR(64) NOT NULL,
  status          VARCHAR(32) NOT NULL DEFAULT 'active',
  created_by      UUID REFERENCES users (id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT knowledge_models_name_nonempty_chk CHECK (length(trim(name)) > 0),
  CONSTRAINT knowledge_models_model_type_chk CHECK (
    model_type IN ('summary', 'claims_evidence', 'software_service', 'test_knowledge')
  ),
  CONSTRAINT knowledge_models_status_chk CHECK (status IN ('active', 'archived'))
);

CREATE INDEX ix_knowledge_models_collection_id ON knowledge_models (collection_id);
CREATE INDEX ix_knowledge_models_created_at ON knowledge_models (created_at DESC);

CREATE TRIGGER trg_knowledge_models_updated_at
  BEFORE UPDATE ON knowledge_models
  FOR EACH ROW EXECUTE PROCEDURE verifiedsignal_set_updated_at();

COMMENT ON TABLE knowledge_models IS
  'Long-lived model identity within a collection; processing varies by model_type.';
COMMENT ON COLUMN knowledge_models.model_type IS
  'V1: summary | claims_evidence | software_service | test_knowledge';


CREATE TABLE knowledge_model_versions (
  id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  knowledge_model_id              UUID NOT NULL REFERENCES knowledge_models (id) ON DELETE CASCADE,
  version_number                  INT NOT NULL,
  build_status                    VARCHAR(32) NOT NULL DEFAULT 'queued',
  source_selection_snapshot_json  JSONB NOT NULL DEFAULT '{}'::jsonb,
  build_profile_json              JSONB NOT NULL DEFAULT '{}'::jsonb,
  summary_json                    JSONB,
  error_message                   TEXT,
  created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at                    TIMESTAMPTZ,
  CONSTRAINT knowledge_model_versions_version_positive_chk CHECK (version_number >= 1),
  CONSTRAINT knowledge_model_versions_build_status_chk CHECK (
    build_status IN ('queued', 'building', 'completed', 'failed')
  ),
  CONSTRAINT uq_knowledge_model_versions_model_version UNIQUE (knowledge_model_id, version_number)
);

CREATE INDEX ix_knowledge_model_versions_model_id ON knowledge_model_versions (knowledge_model_id);
CREATE INDEX ix_knowledge_model_versions_build_status ON knowledge_model_versions (build_status);

COMMENT ON TABLE knowledge_model_versions IS
  'Immutable version snapshot; assets and build runs attach here.';
COMMENT ON COLUMN knowledge_model_versions.source_selection_snapshot_json IS
  'Audit copy of selection inputs (e.g. document ids, filters) at build time.';


CREATE TABLE knowledge_model_assets (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_version_id UUID NOT NULL REFERENCES knowledge_model_versions (id) ON DELETE CASCADE,
  document_id      UUID NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
  inclusion_reason TEXT,
  source_weight    NUMERIC(6, 5),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_knowledge_model_assets_version_doc UNIQUE (model_version_id, document_id)
);

CREATE INDEX ix_knowledge_model_assets_version_id ON knowledge_model_assets (model_version_id);
CREATE INDEX ix_knowledge_model_assets_document_id ON knowledge_model_assets (document_id);


CREATE TABLE model_build_runs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_version_id UUID NOT NULL REFERENCES knowledge_model_versions (id) ON DELETE CASCADE,
  status           VARCHAR(32) NOT NULL DEFAULT 'queued',
  started_at       TIMESTAMPTZ,
  completed_at     TIMESTAMPTZ,
  metrics_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
  error_message    TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT model_build_runs_status_chk CHECK (
    status IN ('queued', 'running', 'completed', 'failed')
  )
);

CREATE INDEX ix_model_build_runs_version_id ON model_build_runs (model_version_id);
CREATE INDEX ix_model_build_runs_status ON model_build_runs (status);

CREATE TRIGGER trg_model_build_runs_updated_at
  BEFORE UPDATE ON model_build_runs
  FOR EACH ROW EXECUTE PROCEDURE verifiedsignal_set_updated_at();

COMMENT ON TABLE model_build_runs IS
  'Operational build attempt for a model version; auditable alongside version row.';
