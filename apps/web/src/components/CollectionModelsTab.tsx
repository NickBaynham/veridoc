import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listCollectionKnowledgeModels } from "../api/knowledgeModels";
import { ApiError } from "../api/http";
import type { KnowledgeModelListItem } from "../api/types";
import { knowledgeModelTypeLabel } from "../lib/knowledgeModelUi";
import { statusBadgeClass } from "../lib/statusBadge";
import { CreateKnowledgeModelWizard } from "./CreateKnowledgeModelWizard";

export interface CollectionModelsTabProps {
  collectionId: string;
  accessToken: string | null;
  api: boolean;
  createOpen: boolean;
  onCloseCreate: () => void;
  onOpenCreate: () => void;
}

export function CollectionModelsTab({
  collectionId,
  accessToken,
  api,
  createOpen,
  onCloseCreate,
  onOpenCreate,
}: CollectionModelsTabProps) {
  const navigate = useNavigate();
  const [items, setItems] = useState<KnowledgeModelListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(() => {
    if (!api || !accessToken) return;
    setLoading(true);
    setError(null);
    void listCollectionKnowledgeModels(accessToken, collectionId)
      .then((r) => setItems(r.items))
      .catch((e) => {
        setItems(null);
        setError(e instanceof ApiError ? e.message : "Failed to load models");
      })
      .finally(() => setLoading(false));
  }, [api, accessToken, collectionId]);

  useEffect(() => {
    reload();
  }, [reload]);

  if (!api) {
    return (
      <section className="card" style={{ padding: "1rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Models</h2>
        <p style={{ color: "var(--text-muted)", marginBottom: 0 }}>
          Knowledge models are available when the app runs in API mode (<code>VITE_API_URL</code>
          ). Demo mode uses local sample documents only.
        </p>
      </section>
    );
  }

  if (!accessToken) {
    return (
      <section className="card" style={{ padding: "1rem" }}>
        <p className="page-sub">Sign in to manage models.</p>
      </section>
    );
  }

  return (
    <>
      <section className="card" style={{ padding: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div>
            <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Models</h2>
            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: 0, maxWidth: 560 }}>
              Versioned knowledge built from documents you select. Builds run asynchronously (or inline when{" "}
              <code>USE_FAKE_QUEUE</code> is on).
            </p>
          </div>
          <button type="button" className="btn btn-primary" onClick={onOpenCreate}>
            Create model
          </button>
        </div>

        {error ? <p className="error-text" style={{ marginTop: "0.75rem" }}>{error}</p> : null}
        {loading && !items ? <p className="page-sub" style={{ marginTop: "0.75rem" }}>Loading…</p> : null}

        {items && items.length === 0 && !loading ? (
          <p style={{ color: "var(--text-muted)", marginTop: "1rem", marginBottom: 0 }}>
            No models yet. Create one from selected collection documents.
          </p>
        ) : null}

        {items && items.length > 0 ? (
          <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: 10 }}>
            {items.map((m) => {
              const v = m.latest_version;
              const updated =
                v?.completed_at ?? v?.created_at ?? m.updated_at ?? m.created_at;
              return (
                <div
                  key={m.id}
                  className="card"
                  style={{
                    padding: "0.85rem 1rem",
                    boxShadow: "none",
                    border: "1px solid var(--border)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <div>
                      <Link
                        to={`/models/${m.id}`}
                        style={{ fontWeight: 600, fontSize: "1rem" }}
                      >
                        {m.name}
                      </Link>
                      <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: 4 }}>
                        {knowledgeModelTypeLabel(m.model_type)}
                        {v ? (
                          <>
                            {" "}
                            · v{v.version_number}
                            {v.asset_count != null ? ` · ${v.asset_count} documents` : null}
                          </>
                        ) : null}
                      </div>
                    </div>
                    <div style={{ textAlign: "right", fontSize: "0.85rem" }}>
                      {v ? (
                        <span className={statusBadgeClass(v.build_status)}>{v.build_status}</span>
                      ) : (
                        <span className="vs-badge">no version</span>
                      )}
                      <div style={{ color: "var(--text-muted)", marginTop: 6 }}>
                        {new Date(updated).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}
      </section>

      <CreateKnowledgeModelWizard
        open={createOpen}
        onClose={onCloseCreate}
        collectionId={collectionId}
        accessToken={accessToken}
        onCreated={(modelId) => {
          reload();
          navigate(`/models/${modelId}`);
        }}
      />
    </>
  );
}
