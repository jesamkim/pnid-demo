/**
 * Timeline spec — confirms the cached pipeline trace renders with
 * stage labels and the self-correction group on drawing 01b.
 *
 * The new synthetic cache uses a single self-correction iteration that
 * recovers PSV-101 after one focused re-extract.
 */
import { expect, test } from "@playwright/test";

test.describe("Agent timeline (cached)", () => {
  test("drawing 01b shows iter 1 + Re-extract + Self-correction Done", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Select drawing 01b,/ }).click();

    // 9 events / ~70s total in the new cache.
    await expect(page.getByText(/9 events \//)).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText(/^iter 1$/).first()).toBeVisible();

    // Self-correction group entries (one of each in a single iteration).
    await expect(page.getByText("Error Analyzer", { exact: true })).toHaveCount(1);
    await expect(page.getByText("Re-extract", { exact: true })).toHaveCount(1);
    await expect(page.getByText("Re-evaluate", { exact: true })).toHaveCount(1);
    await expect(page.getByText("Self-correction Done", { exact: true })).toBeVisible();

    await expect(page.getByText("Finalize", { exact: true })).toBeVisible();
  });

  test("drawing 01 shows the 4-stage path with no self-correction group", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Select drawing 01,/ }).click();

    await expect(page.getByText("Render", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Extract (Vision)", { exact: true })).toBeVisible();
    await expect(page.getByText("Evaluate (Critic)", { exact: true })).toBeVisible();
    await expect(page.getByText("Finalize", { exact: true })).toBeVisible();

    await expect(page.getByText("Error Analyzer", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Self-correction Done", { exact: true })).toHaveCount(0);
  });
});
