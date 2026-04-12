import { randomUUID } from "node:crypto";
import type { Page } from "@playwright/test";
import { E2E_MOCK_API_ORIGIN } from "../../playwright.api-mock.config";

const DOC_ID = "11111111-1111-4111-8111-111111111111";
const COL_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

type MockCollectionRow = {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  document_count: number;
  created_at: string;
};

function slugBaseFromName(name: string): string {
  const base = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return (base || "collection").slice(0, 80);
}

function nextUniqueSlug(name: string, taken: Set<string>): string {
  let base = slugBaseFromName(name);
  let candidate = base;
  let n = 0;
  while (taken.has(candidate)) {
    n += 1;
    candidate = `${base}-${n}`;
  }
  return candidate;
}

/** JSON detail for list + get document (matches FastAPI shapes). */
const listPayload = {
  items: [
    {
      id: DOC_ID,
      collection_id: COL_ID,
      title: "E2E Policy Brief",
      status: "indexed",
      original_filename: "brief.txt",
      content_type: "text/plain",
      storage_key: `raw/${DOC_ID}/brief.txt`,
      created_at: "2026-01-02T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    },
  ],
  total: 1,
  user_id: "e2e-sub",
};

const detailPayload = {
  ...listPayload.items[0],
  sources: [],
  body_text: "Hello from API mock document.",
  canonical_score: {
    factuality_score: 0.72,
    ai_generation_probability: 0.18,
    fallacy_score: 0.52,
    confidence_score: 0.35,
    scorer_name: "verifiedsignal_heuristic",
    scorer_version: "1.0.0",
  },
};

/**
 * Intercept calls to {@link E2E_MOCK_API_ORIGIN} so the SPA can run in API mode without a real backend.
 */
export async function installApiMockRoutes(page: Page) {
  const origin = E2E_MOCK_API_ORIGIN;
  let e2eDocDeleted = false;

  let mockCollections: MockCollectionRow[] = [
    {
      id: COL_ID,
      organization_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      name: "E2E Inbox",
      slug: "inbox",
      document_count: 2,
      created_at: "2026-01-01T00:00:00Z",
    },
    {
      id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      organization_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      name: "Other collection",
      slug: "other",
      document_count: 0,
      created_at: "2026-01-01T00:00:00Z",
    },
  ];

  /** Any UUID document DELETE (folder sync removes / replaces paths). */
  await page.route(
    (url) => {
      if (url.toString().split("?")[0] === `${origin}/api/v1/documents/${DOC_ID}`) return false;
      const base = url.toString().split("?")[0];
      return (
        base.startsWith(`${origin}/api/v1/documents/`) &&
        !base.includes("/file") &&
        !base.includes("/pipeline") &&
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(base.split("/").pop() ?? "")
      );
    },
    async (route) => {
      if (route.request().method() === "DELETE") {
        await route.fulfill({ status: 204, body: "" });
        return;
      }
      await route.fallback();
    },
  );

  await page.route(
    (url) => url.toString().split("?")[0] === `${origin}/api/v1/events/stream`,
    async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
        },
        body: 'data: {"type":"connected","payload":{}}\n\n',
      });
    },
  );

  await page.route(
    (url) => {
      const u = url.toString().split("?")[0];
      return u.startsWith(`${origin}/api/v1/collections/`) && u.endsWith("/analytics");
    },
    async (route) => {
      const base = route.request().url().split("?")[0];
      const collectionId =
        base.replace(/\/analytics$/i, "").split("/").pop() ?? COL_ID;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          collection_id: collectionId,
          index_total: 1,
          index_status: "fake",
          index_message: null,
          facets: {
            status: [{ key: "indexed", count: 1 }],
            ingest_source: [{ key: "upload", count: 1 }],
          },
          postgres: {
            document_count: 2,
            scored_documents: 1,
            avg_factuality: 0.72,
            avg_ai_probability: 0.18,
            suspicious_count: 0,
          },
        }),
      });
    },
  );

  await page.route(
    (url) => {
      const u = url.toString();
      return u.includes(`${origin}/api/v1/documents/`) && u.includes("/pipeline");
    },
    async (route) => {
      const u = route.request().url();
      const docPart = u.split("/documents/")[1]?.split("/pipeline")[0] ?? DOC_ID;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          document_id: docPart,
          document_status: "completed",
          run: {
            id: "22222222-2222-4222-8222-222222222222",
            document_id: docPart,
            status: "succeeded",
            stage: "finalize",
            started_at: "2026-01-02T00:00:00Z",
            completed_at: "2026-01-02T00:01:00Z",
            error_detail: null,
            run_metadata: {},
          },
          events: [
            {
              id: "33333333-3333-4333-8333-333333333333",
              step_index: 0,
              event_type: "pipeline_started",
              stage: null,
              payload: {},
              created_at: "2026-01-02T00:00:00Z",
            },
            {
              id: "44444444-4444-4444-8444-444444444444",
              step_index: 1,
              event_type: "index_complete",
              stage: "index",
              payload: {},
              created_at: "2026-01-02T00:00:30Z",
            },
          ],
        }),
      });
    },
  );

  await page.route(`${origin}/auth/signup`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ message: "Account created (mock)." }),
    });
  });

  await page.route(`${origin}/auth/login`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "e2e-mock-access-token",
        expires_in: 3600,
        token_type: "bearer",
      }),
    });
  });

  await page.route(`${origin}/auth/refresh`, async (route) => {
    await route.fulfill({ status: 401, contentType: "application/json", body: "{}" });
  });

  await page.route(`${origin}/auth/logout`, async (route) => {
    await route.fulfill({ status: 204, body: "" });
  });

  await page.route(`${origin}/api/v1/users/me`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user_id: "e2e-sub",
        database_user_id: "00000000-0000-4000-8000-000000000099",
        email: "e2e@verifiedsignal.io",
        display_name: "e2e",
      }),
    });
  });

  await page.route(
    (url) => url.toString().split("?")[0] === `${origin}/api/v1/collections`,
    async (route) => {
      const method = route.request().method();
      if (method === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ collections: mockCollections }),
        });
        return;
      }
      if (method === "POST") {
        let body: { name?: string; organization_id?: string | null };
        try {
          body = route.request().postDataJSON() as {
            name?: string;
            organization_id?: string | null;
          };
        } catch {
          await route.fulfill({
            status: 400,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Invalid JSON body" }),
          });
          return;
        }
        const name = typeof body?.name === "string" ? body.name.trim() : "";
        if (!name) {
          await route.fulfill({
            status: 400,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Collection name is required" }),
          });
          return;
        }
        const organization_id =
          typeof body.organization_id === "string" && body.organization_id
            ? body.organization_id
            : (mockCollections[0]?.organization_id ??
              "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb");
        const taken = new Set(mockCollections.map((c) => c.slug));
        const slug = nextUniqueSlug(name, taken);
        const row: MockCollectionRow = {
          id: randomUUID(),
          organization_id,
          name,
          slug,
          document_count: 0,
          created_at: new Date().toISOString(),
        };
        mockCollections = [...mockCollections, row];
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify(row),
        });
        return;
      }
      await route.fallback();
    },
  );

  await page.route(
    (url) => {
      const base = url.toString().split("?")[0];
      if (!base.startsWith(`${origin}/api/v1/collections/`)) return false;
      if (base.endsWith("/analytics")) return false;
      const rest = base.slice(`${origin}/api/v1/collections/`.length);
      return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        rest,
      );
    },
    async (route) => {
      const base = route.request().url().split("?")[0];
      const collectionId = base.slice(`${origin}/api/v1/collections/`.length);
      const method = route.request().method();

      if (method === "PATCH") {
        let body: { name?: string };
        try {
          body = route.request().postDataJSON() as { name?: string };
        } catch {
          await route.fulfill({
            status: 400,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Invalid JSON body" }),
          });
          return;
        }
        const name = typeof body?.name === "string" ? body.name.trim() : "";
        if (!name) {
          await route.fulfill({
            status: 400,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Collection name is required" }),
          });
          return;
        }
        const idx = mockCollections.findIndex((c) => c.id === collectionId);
        if (idx === -1) {
          await route.fulfill({
            status: 404,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Collection not found" }),
          });
          return;
        }
        const taken = new Set(
          mockCollections
            .filter((c) => c.id !== collectionId)
            .map((c) => c.slug),
        );
        const slug = nextUniqueSlug(name, taken);
        const updated: MockCollectionRow = {
          ...mockCollections[idx],
          name,
          slug,
        };
        mockCollections = mockCollections.map((c) =>
          c.id === collectionId ? updated : c,
        );
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(updated),
        });
        return;
      }

      if (method === "DELETE") {
        const exists = mockCollections.some((c) => c.id === collectionId);
        if (!exists) {
          await route.fulfill({
            status: 404,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Collection not found" }),
          });
          return;
        }
        mockCollections = mockCollections.filter((c) => c.id !== collectionId);
        await route.fulfill({ status: 204, body: "" });
        return;
      }

      await route.fallback();
    },
  );

  await page.route(
    (url) => {
      const base = url.toString().split("?")[0];
      return base === `${origin}/api/v1/documents/${DOC_ID}/file`;
    },
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      if (e2eDocDeleted) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Document not found" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/plain",
          "Content-Disposition": 'attachment; filename="brief.txt"',
          "Access-Control-Allow-Origin": "http://127.0.0.1:5173",
          "Access-Control-Allow-Credentials": "true",
          "Access-Control-Expose-Headers": "Content-Disposition",
        },
        body: "e2e mock original bytes",
      });
    },
  );

  await page.route(
    (url) => {
      const base = url.toString().split("?")[0];
      return base === `${origin}/api/v1/documents/${DOC_ID}`;
    },
    async (route) => {
      const method = route.request().method();
      if (method === "DELETE") {
        e2eDocDeleted = true;
        await route.fulfill({ status: 204, body: "" });
        return;
      }
      if (method === "GET") {
        if (e2eDocDeleted) {
          await route.fulfill({
            status: 404,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Document not found" }),
          });
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(detailPayload),
        });
        return;
      }
      await route.fallback();
    },
  );

  await page.route(
    (url) => {
      const u = url.toString();
      if (!u.startsWith(`${origin}/api/v1/documents/`)) return false;
      if (u.startsWith(`${origin}/api/v1/documents/from-url`)) return false;
      return true;
    },
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      const u = route.request().url();
      const path = u.slice(`${origin}/api/v1/documents/`.length).split("?")[0];
      if (path.includes("/")) {
        await route.fallback();
        return;
      }
      if (path === DOC_ID) {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Document not found" }),
      });
    },
  );

  await page.route(
    (url) => {
      const base = url.toString().split("?")[0];
      return base === `${origin}/api/v1/documents`;
    },
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            e2eDocDeleted
              ? { items: [], total: 0, user_id: "e2e-sub" }
              : listPayload,
          ),
        });
        return;
      }
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            document_id: randomUUID(),
            status: "queued",
            storage_key: `mock/key/${randomUUID()}`,
            job_id: "job-e2e",
          }),
        });
        return;
      }
      await route.fallback();
    },
  );

  await page.route(`${origin}/api/v1/documents/from-url`, async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        document_id: "00000000-0000-4000-8000-0000000000e3",
        status: "created",
        source_url: "https://example.com/x",
        job_id: "job-url",
      }),
    });
  });

  await page.route(
    (url) => url.toString().startsWith(`${origin}/api/v1/search`),
    async (route) => {
      const u = new URL(route.request().url());
      const col = u.searchParams.get("collection_id");
      const wantFacets = u.searchParams.get("include_facets") === "true";
      const baseHit = {
        document_id: DOC_ID,
        title: "E2E Policy Brief",
        score: 1,
        snippet: "Hello from API mock document.",
        status: "indexed",
      };
      let hits = e2eDocDeleted || (col != null && col !== COL_ID) ? [] : [baseHit];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query: u.searchParams.get("q") ?? "",
          limit: Number(u.searchParams.get("limit")) || 25,
          hits,
          total: hits.length,
          index_status: "fake",
          message: null,
          facets: wantFacets
            ? {
                status: [{ key: "indexed", count: hits.length }],
                ingest_source: [{ key: "upload", count: hits.length }],
              }
            : null,
        }),
      });
    },
  );
}

export { DOC_ID, COL_ID };
