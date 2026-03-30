import { expect, test } from "@playwright/test";
import { loginAsDemoUser } from "./helpers/auth";

test.describe("Collections & document reader", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsDemoUser(page);
  });

  test("opens collection analytics from table", async ({ page }) => {
    await page.getByRole("navigation").getByRole("link", { name: "Collections" }).click();
    await expect(page.getByRole("heading", { name: "Collections" })).toBeVisible();
    await page.getByRole("link", { name: "Analytics →" }).first().click();
    await expect(page.getByRole("heading", { name: "Research — 2026 Q1" })).toBeVisible();
    await expect(page.getByText(/Use Case 4/i)).toBeVisible();
  });

  test("opens document reader from dashboard recent list", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await page.getByRole("link", { name: "Policy brief — summer outreach pilot" }).click();
    await expect(page.getByRole("heading", { name: "Policy brief — summer outreach pilot" })).toBeVisible();
    await expect(page.getByText(/Use Case 3/i)).toBeVisible();
  });

  test("shows not found for unknown document id", async ({ page }) => {
    await page.goto("/documents/00000000-0000-4000-8000-000000000099");
    await expect(page.getByRole("heading", { name: "Document not found" })).toBeVisible();
  });
});
