import { expect, test } from "@playwright/test";
import { loginAsDemoUser } from "./helpers/auth";

test.describe("Reports & account pages", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsDemoUser(page);
  });

  test("report builder generates mock preview", async ({ page }) => {
    await page.getByRole("navigation").getByRole("link", { name: "Reports" }).click();
    await expect(page.getByRole("heading", { name: "New report" })).toBeVisible();
    await page.getByRole("button", { name: /Generate \(mock\)/i }).click();
    await expect(page.getByRole("heading", { name: "Executive summary" })).toBeVisible();
    await expect(page.getByText(/Mock narrative/i)).toBeVisible();
  });

  test("billing page shows plan content", async ({ page }) => {
    await page.getByRole("navigation").getByRole("link", { name: "Billing" }).click();
    await expect(page.getByRole("heading", { name: "Billing" })).toBeVisible();
    await expect(page.getByText(/Use Case 7/i)).toBeVisible();
  });

  test("security page shows session controls", async ({ page }) => {
    await page.getByRole("navigation").getByRole("link", { name: "Security" }).click();
    await expect(page.getByRole("heading", { name: "Security" })).toBeVisible();
    await expect(page.getByText(/Change password/i)).toBeVisible();
  });
});
