import { expect, test, type Page } from "@playwright/test";
import { COL_ID, DOC_ID, installApiMockRoutes } from "./helpers/apiMockRoutes";

/** Prefilled dev email + `pw`; wait for dashboard so `page.goto` does not race login. */
async function mockPasswordLogin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Password", { exact: false }).fill("pw");
  await page.getByRole("button", { name: /Continue to dashboard/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test.describe("API mode (mocked HTTP)", () => {
  test.beforeEach(async ({ page }) => {
    await installApiMockRoutes(page);
  });

  test("signs in against mocked /auth/login and shows API banner", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email", { exact: false }).fill("e2e@verifiedsignal.io");
    await page.getByLabel("Password", { exact: false }).fill("any-password");
    await page.getByRole("button", { name: /Continue to dashboard/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByText(/API mode/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "E2E Policy Brief" })).toBeVisible();
  });

  test("sign up uses mocked /auth/signup then /auth/login", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "Sign up" }).click();
    await page.getByLabel("Email", { exact: false }).fill("newuser@verifiedsignal.io");
    await page.getByLabel("Password", { exact: false }).fill("any-password");
    await page.getByRole("button", { name: /Create account & sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByText(/API mode/i)).toBeVisible();
  });

  test("opens document from dashboard", async ({ page }) => {
    await mockPasswordLogin(page);
    await page.getByRole("link", { name: "E2E Policy Brief" }).click();
    await expect(page.getByRole("heading", { name: "E2E Policy Brief" })).toBeVisible();
    await expect(page.getByText(/Hello from API mock document/i)).toBeVisible();
  });

  test("search lists mocked hits", async ({ page }) => {
    await mockPasswordLogin(page);
    await page.getByRole("navigation").getByRole("link", { name: "Search" }).click();
    await expect(page.getByRole("link", { name: "E2E Policy Brief" })).toBeVisible({ timeout: 20_000 });
  });

  test("collections and analytics use API metadata", async ({ page }) => {
    await mockPasswordLogin(page);
    await page.getByRole("navigation").getByRole("link", { name: "Collections" }).click();
    await expect(page.getByRole("cell", { name: "E2E Inbox", exact: true })).toBeVisible();
    await page.getByRole("row", { name: /E2E Inbox/ }).getByRole("link", { name: "Analytics →" }).click();
    await expect(page.getByRole("heading", { name: "E2E Inbox" })).toBeVisible();
    await expect(page.getByText(/OpenSearch facet buckets/i)).toBeVisible();
  });

  test("collections page create rename delete (mock API)", async ({ page }) => {
    const created = "E2E CRUD Collection";
    const renamed = "E2E CRUD Collection Renamed";

    await mockPasswordLogin(page);
    await page.getByRole("navigation").getByRole("link", { name: "Collections" }).click();
    await expect(page.getByRole("cell", { name: "E2E Inbox", exact: true })).toBeVisible();

    await page.getByLabel("New collection name").fill(created);
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByRole("cell", { name: created, exact: true })).toBeVisible({ timeout: 15_000 });

    await page.getByRole("row", { name: new RegExp(created) }).getByRole("button", { name: "Rename" }).click();
    await page.getByLabel(`Rename ${created}`).fill(renamed);
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByRole("cell", { name: renamed, exact: true })).toBeVisible({ timeout: 15_000 });

    page.once("dialog", (d) => {
      expect(d.message()).toContain(renamed);
      d.accept();
    });
    await page.getByRole("row", { name: new RegExp(renamed) }).getByRole("button", { name: "Delete" }).click();
    await expect(page.getByRole("cell", { name: renamed, exact: true })).not.toBeVisible({ timeout: 15_000 });
  });

  test("unknown document id shows not found", async ({ page }) => {
    await mockPasswordLogin(page);
    await page.goto(`/documents/${COL_ID}`);
    await expect(page.getByRole("heading", { name: "Document not found" })).toBeVisible();
  });

  test("known document id loads", async ({ page }) => {
    await mockPasswordLogin(page);
    await page.goto(`/documents/${DOC_ID}`);
    await expect(page.getByRole("heading", { name: "E2E Policy Brief" })).toBeVisible();
  });

  test("document reader move to other collection (mock API)", async ({ page }) => {
    await mockPasswordLogin(page);
    await page.goto(`/documents/${DOC_ID}`);
    await expect(page.getByRole("heading", { name: "E2E Policy Brief" })).toBeVisible();
    await page.getByLabel("Target collection").selectOption("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb");
    await page.getByRole("button", { name: "Move here" }).click();
    await expect(page.getByText(/Current collection:/)).toContainText("Other collection", {
      timeout: 15_000,
    });
  });

  test("document reader shows canonical score dimensions", async ({ page }) => {
    await mockPasswordLogin(page);
    await page.goto(`/documents/${DOC_ID}`);
    await expect(page.getByText(/Fallacy \/ rhetoric risk/i)).toBeVisible();
    await expect(page.getByText(/Confidence/i)).toBeVisible();
  });

  test("download original completes without error", async ({ page }) => {
    await mockPasswordLogin(page);
    await page.goto(`/documents/${DOC_ID}`);
    await page.getByRole("button", { name: "Download original" }).click();
    await expect(page.getByRole("button", { name: "Download original" })).toBeEnabled({ timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Error" })).not.toBeVisible();
  });

  test("search optional facets and collection filter", async ({ page }) => {
    await mockPasswordLogin(page);
    await page.getByRole("navigation").getByRole("link", { name: "Search" }).click();
    await page.getByRole("checkbox", { name: /Include facet counts/i }).check();
    await expect(page.getByRole("heading", { name: "Facets" })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("cell", { name: "indexed", exact: true })).toBeVisible();

    await page.getByLabel("Collection").selectOption(COL_ID);
    await expect(page.getByRole("link", { name: "E2E Policy Brief" })).toBeVisible({ timeout: 20_000 });

    await page.getByLabel("Collection").selectOption("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb");
    await expect(page.getByRole("link", { name: "E2E Policy Brief" })).not.toBeVisible({ timeout: 20_000 });
  });

  test("delete document returns to dashboard and clears list", async ({ page }) => {
    page.once("dialog", (d) => d.accept());
    await mockPasswordLogin(page);
    await page.goto(`/documents/${DOC_ID}`);
    await page.getByRole("button", { name: "Delete document" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("link", { name: "E2E Policy Brief" })).not.toBeVisible();
  });
});
