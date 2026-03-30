import { expect, type Page } from "@playwright/test";

/** Demo login: client-side only (see LoginPage). */
export async function loginAsDemoUser(page: Page, password = "demo123") {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Email", { exact: false }).fill("e2e@verifiedsignal.io");
  await page.getByLabel("Password", { exact: false }).fill(password);
  await page.getByRole("button", { name: /Continue to dashboard/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}
