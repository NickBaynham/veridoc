import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({
  getApiBaseUrl: () => "http://api.test",
}));

import { copyDocument, moveDocument } from "./documents";
import { ApiError } from "./http";

const summary = {
  id: "11111111-1111-4111-8111-111111111111",
  collection_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  title: "Brief",
  status: "indexed",
  original_filename: "b.txt",
  content_type: "text/plain",
  storage_key: "raw/x",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("documents transfer helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("moveDocument POSTs to /move", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(summary), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const out = await moveDocument("tok", summary.id, summary.collection_id);
    expect(out.collection_id).toBe(summary.collection_id);
    expect(fetchMock.mock.calls[0][0]).toBe(
      `http://api.test/api/v1/documents/${summary.id}/move`,
    );
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ collection_id: summary.collection_id });
  });

  it("copyDocument POSTs to /copy and accepts 201", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...summary, id: "22222222-2222-4222-8222-222222222222" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const out = await copyDocument("tok", summary.id, summary.collection_id);
    expect(out.id).toBe("22222222-2222-4222-8222-222222222222");
    expect(fetchMock.mock.calls[0][0]).toBe(
      `http://api.test/api/v1/documents/${summary.id}/copy`,
    );
  });

  it("moveDocument surfaces ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "nope" }), {
          status: 403,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await expect(moveDocument("t", summary.id, summary.collection_id)).rejects.toSatisfy(
      (e: unknown) => e instanceof ApiError && e.status === 403,
    );
  });
});
