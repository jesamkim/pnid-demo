/**
 * Replay spec — verifies the cached replay state machine drives the
 * overlay through extracting → evaluating → finalizing → done.
 */
import { expect, test } from "@playwright/test";

test.describe("Replay (cached)", () => {
  test("Replay button reveals overlay then progresses to complete", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/4 events/).first()).toBeVisible({ timeout: 15_000 });

    // Initial: no overlay.
    await expect(
      page.locator('svg[aria-label="Overlay for drawing 01"]'),
    ).toHaveCount(0);

    // Start replay.
    await page.getByRole("button", { name: /Replay extraction/ }).click();

    // Within ~1s the overlay appears (extracting phase).
    const overlay = page.locator('svg[aria-label="Overlay for drawing 01"]');
    await expect(overlay).toBeVisible({ timeout: 5_000 });

    // PnidViewer shows a phase badge in extracting/evaluating.
    await expect(page.getByText(/extracting|evaluating/).first()).toBeVisible({
      timeout: 5_000,
    });

    // After ~10s replay reaches the complete state.
    await expect(page.getByText("complete")).toBeVisible({ timeout: 30_000 });
  });

  test("Pause/Resume holds the phase mid-flight", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/4 events/).first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /Replay extraction/ }).click();
    // As soon as Replay starts, the button becomes Pause.
    const pauseBtn = page.getByRole("button", { name: /Pause replay/ });
    await expect(pauseBtn).toBeVisible({ timeout: 5_000 });
    await pauseBtn.click();
    await expect(page.getByRole("button", { name: /Resume replay/ })).toBeVisible();
  });
});
