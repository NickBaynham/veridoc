import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({
  getApiBaseUrl: () => "http://api.test",
}));

import {
  createCollectionKnowledgeModel,
  fetchKnowledgeModelDetail,
  listCollectionKnowledgeModels,
  listKnowledgeModelVersions,
} from "./knowledgeModels";
import { ApiError } from "./http";

describe("knowledgeModels API helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("listCollectionKnowledgeModels GETs with Bearer", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], collection_id: "col-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const r = await listCollectionKnowledgeModels("tok", "col-1");
    expect(r.items).toEqual([]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/collections/col-1/models");
    expect(init.headers).toBeInstanceOf(Headers);
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer tok");
  });

  it("createCollectionKnowledgeModel POSTs selected_document_ids", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          knowledge_model: {
            id: "m1",
            collection_id: "c1",
            name: "N",
            description: null,
            model_type: "summary",
            status: "active",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            latest_version: null,
          },
          version: {
            id: "v1",
            knowledge_model_id: "m1",
            version_number: 1,
            build_status: "completed",
            created_at: "2026-01-01T00:00:00Z",
            completed_at: "2026-01-01T00:00:00Z",
            error_message: null,
            asset_count: 1,
          },
          build_job_id: null,
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const out = await createCollectionKnowledgeModel("tok", "c1", {
      name: "N",
      model_type: "summary",
      selected_document_ids: ["d1", "d2"],
      build_profile: { k: 1 },
    });
    expect(out.knowledge_model.id).toBe("m1");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      name: "N",
      model_type: "summary",
      selected_document_ids: ["d1", "d2"],
      build_profile: { k: 1 },
    });
  });

  it("fetchKnowledgeModelDetail throws ApiError on 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Model not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await expect(fetchKnowledgeModelDetail("t", "mid")).rejects.toSatisfy((e: unknown) => {
      return e instanceof ApiError && e.status === 404;
    });
  });

  it("listKnowledgeModelVersions returns items", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            items: [
              {
                id: "v1",
                knowledge_model_id: "m1",
                version_number: 1,
                build_status: "completed",
                created_at: "2026-01-01T00:00:00Z",
                completed_at: "2026-01-01T00:00:00Z",
                error_message: null,
                asset_count: 2,
              },
            ],
            knowledge_model_id: "m1",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const r = await listKnowledgeModelVersions("t", "m1");
    expect(r.items).toHaveLength(1);
    expect(r.items[0].asset_count).toBe(2);
  });
});
