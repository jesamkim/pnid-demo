/**
 * Interaction spec — drawing switching, anomaly highlight after replay,
 * and example chips presence.
 */
import { expect, test } from "@playwright/test";

test.describe("Sidebar + drawing switch", () => {
  test("switching to drawing 01b shows the right header", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Select drawing 01b,/ }).click();
    await expect(
      page.getByRole("region", { name: /P&ID viewer for drawing 01b/ }),
    ).toBeVisible();
  });
});

test.describe("Anomaly + replay highlight", () => {
  test("after Replay completes, V-102 anomaly tag is highlighted", async ({ page }) => {
    await page.goto("/");

    // Wait for cached pipeline (events) to land so Replay can start.
    await expect(page.getByText(/4 events/).first()).toBeVisible({ timeout: 15_000 });

    // Trigger Replay (cached).
    await page.getByRole("button", { name: /Replay extraction/ }).click();

    // Overlay appears within the first second.
    const overlay = page.locator('svg[aria-label="Overlay for drawing 01"]');
    await expect(overlay).toBeVisible({ timeout: 5_000 });

    // After ~10s the replay reaches finalizing/done with the anomaly badge.
    await expect(page.getByText("complete")).toBeVisible({ timeout: 30_000 });

    // Click V-102 anomaly chip → overlay group flips to selected.
    const chip = page.getByRole("button", { name: /Highlight V-102 on the drawing/ });
    await chip.click();
    const selected = overlay.locator('g[aria-label="equipment V-102 (selected)"]');
    await expect(selected).toHaveCount(1);
  });
});

test.describe("Query examples", () => {
  test("four example chips are rendered", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: "PSV protecting V-101" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Downstream of P-101A/B" })).toBeVisible();
    await expect(page.getByRole("button", { name: "High-pressure PSV lines" })).toBeVisible();
    await expect(page.getByRole("button", { name: "한국어 — V-101 보호" })).toBeVisible();
  });
});
