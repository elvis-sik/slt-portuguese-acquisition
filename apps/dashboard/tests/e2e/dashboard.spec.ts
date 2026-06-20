import { expect, test } from "@playwright/test";

test("loads the dashboard cockpit", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "SLT Portuguese Control" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Control", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Decision", exact: true })).toBeVisible();
});
