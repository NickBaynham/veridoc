import { expect, test } from "@playwright/test";
import { loginAsDemoUser } from "./helpers/auth";

test("sign out returns to login", async ({ page }) => {
  await loginAsDemoUser(page);
  await page.getByRole("button", { name: /Sign out/i }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});
