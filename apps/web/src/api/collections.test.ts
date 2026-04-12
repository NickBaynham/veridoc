import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({
  getApiBaseUrl: () => "http://api.test",
}));

import { createCollection, deleteCollection, updateCollection } from "./collections";
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
});
