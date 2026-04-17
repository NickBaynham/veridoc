import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({
  getApiBaseUrl: () => "http://api.test",
}));

import {
  createCollection,
  deleteCollection,
  fetchCollectionActivity,
  fetchCollectionDetail,
  fetchCollectionDocuments,
  updateCollection,
} from "./collections";
import { ApiError } from "./http";

describe("collections API helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("createCollection POSTs JSON with Bearer and returns row", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "11111111-1111-4111-8111-111111111111",
          organization_id: "22222222-2222-4222-8222-222222222222",
          name: "My Coll",
          slug: "my-coll",
          document_count: 0,
          created_at: "2026-01-01T00:00:00Z",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const row = await createCollection("access-token", {
      name: "My Coll",
      organization_id: "22222222-2222-4222-8222-222222222222",
    });

    expect(row.slug).toBe("my-coll");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.headers).toBeInstanceOf(Headers);
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer access-token");
    expect(JSON.parse(String(init.body))).toEqual({
      name: "My Coll",
      organization_id: "22222222-2222-4222-8222-222222222222",
    });
  });

  it("createCollection throws ApiError on error response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "forbidden org" }), {
          status: 403,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(createCollection("t", { name: "X" })).rejects.toSatisfy((e: unknown) => {
      return e instanceof ApiError && e.status === 403 && e.message === "forbidden org";
    });
  });

  it("updateCollection PATCHes name", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "11111111-1111-4111-8111-111111111111",
          organization_id: "22222222-2222-4222-8222-222222222222",
          name: "Renamed",
          slug: "renamed",
          document_count: 3,
          created_at: "2026-01-01T00:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const row = await updateCollection("t", "11111111-1111-4111-8111-111111111111", {
      name: "Renamed",
    });
    expect(row.name).toBe("Renamed");
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://api.test/api/v1/collections/11111111-1111-4111-8111-111111111111",
    );
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ name: "Renamed" });
  });

  it("deleteCollection resolves on 204", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(deleteCollection("t", "11111111-1111-4111-8111-111111111111")).resolves.toBeUndefined();
  });

  it("fetchCollectionDetail GETs summary", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "11111111-1111-4111-8111-111111111111",
          organization_id: "22222222-2222-4222-8222-222222222222",
          name: "Inbox",
          slug: "inbox",
          description: null,
          document_count: 3,
          last_updated: "2026-01-02T00:00:00Z",
          status_breakdown: { completed: 2, queued: 1 },
          failed_document_count: 0,
          in_progress_document_count: 1,
          avg_canonical_factuality: 0.71,
          created_at: "2026-01-01T00:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const d = await fetchCollectionDetail("tok", "11111111-1111-4111-8111-111111111111");
    expect(d.name).toBe("Inbox");
    expect(d.document_count).toBe(3);
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/api/v1/collections/11111111-1111-4111-8111-111111111111");
  });

  it("fetchCollectionDocuments adds query string", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          total: 0,
          limit: 25,
          offset: 0,
          collection_id: "11111111-1111-4111-8111-111111111111",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    await fetchCollectionDocuments("tok", "11111111-1111-4111-8111-111111111111", {
      limit: 25,
      offset: 10,
      q: "brief",
      status: "completed",
      sort: "name_asc",
    });
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("limit=25");
    expect(url).toContain("offset=10");
    expect(url).toContain("q=brief");
    expect(url).toContain("status=completed");
    expect(url).toContain("sort=name_asc");
  });

  it("fetchCollectionActivity GETs events list", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          collection_id: "11111111-1111-4111-8111-111111111111",
          items: [
            {
              id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
              document_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
              document_title: "Doc",
              pipeline_run_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
              event_type: "enrich_complete",
              stage: "enrich",
              step_index: 2,
              payload: {},
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const r = await fetchCollectionActivity("tok", "11111111-1111-4111-8111-111111111111", { limit: 50 });
    expect(r.items).toHaveLength(1);
    expect(r.items[0].event_type).toBe("enrich_complete");
    expect(String(fetchMock.mock.calls[0][0])).toContain("limit=50");
  });
});
