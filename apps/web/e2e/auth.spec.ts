import { expect, test } from "@playwright/test";
import { loginAsDemoUser } from "./helpers/auth";

test.describe("Authentication (demo)", () => {
  test("redirects protected routes to login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  });

  test("rejects password shorter than 3 characters", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Password", { exact: false }).fill("ab");
    await page.getByRole("button", { name: /Continue to dashboard/i }).click();
    await expect(page.getByText(/at least 3 characters/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test("logs in and lands on dashboard", async ({ page }) => {
    await loginAsDemoUser(page);
    await expect(page.getByText(/UI demo/i)).toBeVisible();
  });
});
