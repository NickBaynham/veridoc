import { expect, test } from "@playwright/test";
import { loginAsDemoUser } from "./helpers/auth";

const navCases: { link: string; heading: string | RegExp }[] = [
  { link: "Dashboard", heading: "Dashboard" },
  { link: "Upload", heading: "Upload" },
  { link: "Collections", heading: "Collections" },
  { link: "Search", heading: "Search" },
  { link: "Reports", heading: "New report" },
  { link: "Billing", heading: "Billing" },
  { link: "Security", heading: "Security" },
];

test.describe("Sidebar navigation", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsDemoUser(page);
  });

  for (const { link, heading } of navCases) {
    test(`opens ${link}`, async ({ page }) => {
      await page.getByRole("navigation").getByRole("link", { name: link }).click();
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    });
  }
});
