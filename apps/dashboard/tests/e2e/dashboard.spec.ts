import { expect, test } from "@playwright/test";

test("loads the dashboard cockpit", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "SLT Portuguese Control" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Control", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Decision", exact: true })).toBeVisible();
  await expect(page.getByLabel("Job template")).toBeVisible();
  await expect(page.getByLabel("Max wall-clock hours")).toBeVisible();
  await expect(page.getByLabel("Max epochs")).toBeVisible();
  await page.getByRole("tab", { name: "Figures" }).click();
  await expect(page.getByRole("heading", { name: "Figure 1a target loss and BPB" })).toBeVisible();
});
