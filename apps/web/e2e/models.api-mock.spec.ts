import { expect, test, type Page } from "@playwright/test";
import { COL_ID, DOC_ID, installApiMockRoutes } from "./helpers/apiMockRoutes";

async function mockPasswordLogin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Password", { exact: false }).fill("pw");
  await page.getByRole("button", { name: /Continue to dashboard/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test.describe("Knowledge models (API mock)", () => {
  test.beforeEach(async ({ page }) => {
    await installApiMockRoutes(page);
  });

  test("creates a model from collection workspace and opens detail", async ({ page }) => {
    await mockPasswordLogin(page);
    await page.goto(`/collections/${COL_ID}?tab=models`);
    await expect(page.getByRole("heading", { name: "E2E Inbox" })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("tab", { name: "Models" })).toHaveAttribute("aria-selected", "true");

    await page.getByRole("button", { name: "Create model" }).click();
    await expect(page.getByRole("dialog", { name: "Create knowledge model" })).toBeVisible();

    await page.getByRole("button", { name: "Next" }).click();
    await page.getByPlaceholder("e.g. Q1 policy synthesis").fill("E2E Summary Model");
    await page.getByRole("button", { name: "Next" }).click();

    const rowCheckbox = page.getByRole("checkbox", {
      name: /E2E Policy Brief/i,
    });
    await expect(rowCheckbox).toBeVisible({ timeout: 15_000 });
    await rowCheckbox.check();
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Next" }).click();
    await page
      .getByRole("dialog", { name: "Create knowledge model" })
      .getByRole("button", { name: "Create model" })
      .click();

    await expect(page.getByRole("heading", { name: "E2E Summary Model" })).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText(/E2E mock build output/i)).toBeVisible();

    await page.getByRole("tab", { name: "Included documents" }).click();
    await expect(page.getByRole("link", { name: /E2E Policy Brief/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /E2E Policy Brief/i })).toHaveAttribute(
      "href",
      new RegExp(`/documents/${DOC_ID}`),
    );
  });
});
