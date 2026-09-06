/**
 * Smoke spec — confirms the app shell renders, hits the backend, and
 * pulls cached pipeline + geometry for the first drawing. The overlay
 * must stay hidden until Replay or Run Live is triggered.
 */
import { expect, test } from "@playwright/test";

test.describe("App shell", () => {
  test("renders header, sidebar with 2 drawings, raw drawing only (no overlay)",
    async ({ page }) => {
      await page.goto("/");

      await expect(
        page.getByRole("heading", { name: "P&ID Agentic Demo", level: 1 }),
      ).toBeVisible();

      const sidebar = page.getByRole("complementary", { name: "P&ID drawings" });
      await expect(sidebar).toBeVisible();

      // 2 cached drawings are present (01, 01b).
      const drawingButtons = sidebar.getByRole("button", {
        name: /Select drawing /,
      });
      await expect(drawingButtons).toHaveCount(2);

      // Drawing 01 is auto-selected.
      const first = sidebar.getByRole("button", {
        name: /Select drawing 01,/,
      });
      await expect(first).toHaveAttribute("aria-pressed", "true");

      // Initial state: NO overlay (raw drawing only).
      await expect(
        page.locator('svg[aria-label="Overlay for drawing 01"]'),
      ).toHaveCount(0);

      // Replay + Run Live buttons are visible.
      await expect(page.getByRole("button", { name: /Replay extraction/ })).toBeVisible();
      await expect(page.getByRole("button", { name: /Run live extraction/ })).toBeVisible();
    });

  test("theme toggle flips html class", async ({ page }) => {
    await page.goto("/");
    const html = page.locator("html");
    const initial = await html.getAttribute("class");
    expect(initial === "dark" || initial === "light").toBe(true);
    const toggle = page.getByRole("button", { name: /Switch to (dark|light) theme/ });
    await toggle.click();
    const next = await html.getAttribute("class");
    expect(next).not.toBe(initial);
  });

  test("memory backend label is shown in header", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/memory:/)).toBeVisible();
  });
});
