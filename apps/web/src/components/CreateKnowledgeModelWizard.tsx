import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { fetchCollectionDocuments } from "../api/collections";
import { createCollectionKnowledgeModel } from "../api/knowledgeModels";
import { ApiError } from "../api/http";
import type { CollectionDocumentItem, KnowledgeModelTypeId } from "../api/types";
import {
  KNOWLEDGE_MODEL_TYPE_OPTIONS,
  type KnowledgeModelTypeOption,
} from "../lib/knowledgeModelUi";

// Backend currently validates list limits at <= 200.
const DOC_PAGE_SIZE = 200;

export interface CreateKnowledgeModelWizardProps {
  open: boolean;
  onClose: () => void;
  collectionId: string;
  accessToken: string;
  onCreated: (modelId: string) => void;
}

export function CreateKnowledgeModelWizard({
  open,
  onClose,
  collectionId,
  accessToken,
  onCreated,
}: CreateKnowledgeModelWizardProps) {
  const [step, setStep] = useState(1);
  const [modelType, setModelType] = useState<KnowledgeModelTypeId>("summary");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [buildProfileRaw, setBuildProfileRaw] = useState("");
  const [docs, setDocs] = useState<CollectionDocumentItem[] | null>(null);
  const [docsError, setDocsError] = useState<string | null>(null);
  const [docsLoading, setDocsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStep(1);
    setModelType("summary");
    setName("");
    setDescription("");
    setSelected(new Set());
    setBuildProfileRaw("");
    setDocs(null);
    setDocsError(null);
    setSubmitError(null);
  }, [open, collectionId]);

  useEffect(() => {
    if (!open || step !== 3) return;
    let cancelled = false;
    setDocsLoading(true);
    setDocsError(null);
    void fetchCollectionDocuments(accessToken, collectionId, { limit: DOC_PAGE_SIZE, offset: 0 })
      .then((r) => {
        if (!cancelled) setDocs(r.items);
      })
      .catch((e) => {
        if (!cancelled) {
          setDocs(null);
          setDocsError(e instanceof ApiError ? e.message : "Failed to load documents");
        }
      })
      .finally(() => {
        if (!cancelled) setDocsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, step, accessToken, collectionId]);

  const canNext = useMemo(() => {
    if (step === 1) return true;
    if (step === 2) return name.trim().length > 0;
    if (step === 3) return selected.size > 0;
    if (step === 4) {
      const t = buildProfileRaw.trim();
      if (!t) return true;
      try {
        const o = JSON.parse(t) as unknown;
        return typeof o === "object" && o !== null && !Array.isArray(o);
      } catch {
        return false;
      }
    }
    return true;
  }, [step, name, selected, buildProfileRaw]);

  function toggleDoc(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submit() {
    setSubmitError(null);
    let build_profile: Record<string, unknown> = {};
    const raw = buildProfileRaw.trim();
    if (raw) {
      try {
        build_profile = JSON.parse(raw) as Record<string, unknown>;
      } catch {
        setSubmitError("Build profile must be valid JSON.");
        return;
      }
    }
    setSubmitting(true);
    try {
      const res = await createCollectionKnowledgeModel(accessToken, collectionId, {
        name: name.trim(),
        description: description.trim() || null,
        model_type: modelType,
        selected_document_ids: [...selected],
        build_profile,
      });
      onCreated(res.knowledge_model.id);
      onClose();
    } catch (e) {
      setSubmitError(e instanceof ApiError ? e.message : "Create failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  const inputStyle: CSSProperties = {
    width: "100%",
    padding: "0.45rem 0.5rem",
    borderRadius: 6,
    border: "1px solid var(--border)",
    background: "var(--bg-elevated)",
    color: "var(--text)",
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="km-wizard-title"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.35)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 60,
        padding: 16,
      }}
    >
      <div
        className="card"
        style={{
          maxWidth: 520,
          width: "100%",
          maxHeight: "90vh",
          overflow: "auto",
          padding: "1rem",
        }}
      >
        <h2 id="km-wizard-title" style={{ marginTop: 0, fontSize: "1rem" }}>
          Create knowledge model
        </h2>
        <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: 0 }}>
          Step {step} of 5 — version 1 is created and a build runs from your selected documents.
        </p>

        {step === 1 ? (
          <fieldset style={{ border: "none", padding: 0, margin: "0.75rem 0" }}>
            <legend style={{ fontSize: "0.85rem", marginBottom: 8 }}>Model type</legend>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {KNOWLEDGE_MODEL_TYPE_OPTIONS.map((opt) => (
                <label
                  key={opt.id}
                  style={{ display: "flex", gap: 8, alignItems: "center", cursor: "pointer" }}
                >
                  <input
                    type="radio"
                    name="km-type"
                    checked={modelType === opt.id}
                    onChange={() => setModelType(opt.id)}
                  />
                  <span>{opt.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
        ) : null}

        {step === 2 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <label>
              <span style={{ display: "block", fontSize: "0.85rem", marginBottom: 4 }}>Name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Q1 policy synthesis"
                style={inputStyle}
              />
            </label>
            <label>
              <span style={{ display: "block", fontSize: "0.85rem", marginBottom: 4 }}>
                Description (optional)
              </span>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="What this model is for"
                style={{ ...inputStyle, resize: "vertical" }}
              />
            </label>
          </div>
        ) : null}

        {step === 3 ? (
          <div>
            {docsLoading ? <p className="page-sub">Loading documents…</p> : null}
            {docsError ? <p className="error-text">{docsError}</p> : null}
            {docs && docs.length === 0 && !docsLoading ? (
              <p className="page-sub">No documents in this collection yet.</p>
            ) : null}
            {docs && docs.length > 0 ? (
              <ul
                style={{
                  listStyle: "none",
                  padding: 0,
                  margin: "0.5rem 0 0",
                  maxHeight: 280,
                  overflow: "auto",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                }}
              >
                {docs.map((d) => (
                  <li
                    key={d.id}
                    style={{
                      display: "flex",
                      gap: 8,
                      alignItems: "flex-start",
                      padding: "0.5rem 0.65rem",
                      borderBottom: "1px solid var(--border)",
                      fontSize: "0.9rem",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(d.id)}
                      onChange={() => toggleDoc(d.id)}
                      aria-label={`Include ${d.title ?? d.original_filename ?? d.id}`}
                    />
                    <span>{d.title || d.original_filename || d.id.slice(0, 8)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {step === 4 ? (
          <label>
            <span style={{ display: "block", fontSize: "0.85rem", marginBottom: 4 }}>
              Build profile (optional JSON object)
            </span>
            <textarea
              value={buildProfileRaw}
              onChange={(e) => setBuildProfileRaw(e.target.value)}
              rows={6}
              placeholder='e.g. { "max_bullets": 8 }'
              style={{ ...inputStyle, fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}
            />
          </label>
        ) : null}

        {step === 5 ? (
          <div style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>
            <p style={{ marginTop: 0 }}>
              <strong style={{ color: "var(--text)" }}>Type:</strong>{" "}
              {KNOWLEDGE_MODEL_TYPE_OPTIONS.find((o: KnowledgeModelTypeOption) => o.id === modelType)
                ?.label ?? modelType}
            </p>
            <p>
              <strong style={{ color: "var(--text)" }}>Name:</strong> {name.trim()}
            </p>
            {description.trim() ? (
              <p>
                <strong style={{ color: "var(--text)" }}>Description:</strong> {description.trim()}
              </p>
            ) : null}
            <p>
              <strong style={{ color: "var(--text)" }}>Documents:</strong> {selected.size} selected
            </p>
          </div>
        ) : null}

        {submitError ? <p className="error-text">{submitError}</p> : null}

        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginTop: "1rem" }}>
          <button type="button" className="btn" disabled={submitting} onClick={onClose}>
            Cancel
          </button>
          <div style={{ display: "flex", gap: 8 }}>
            {step > 1 ? (
              <button
                type="button"
                className="btn"
                disabled={submitting}
                onClick={() => setStep((s) => s - 1)}
              >
                Back
              </button>
            ) : null}
            {step < 5 ? (
              <button
                type="button"
                className="btn btn-primary"
                disabled={!canNext || submitting}
                onClick={() => setStep((s) => s + 1)}
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-primary"
                disabled={submitting}
                onClick={() => void submit()}
              >
                {submitting ? "Creating…" : "Create model"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
