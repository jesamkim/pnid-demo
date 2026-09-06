/**
 * Playwright config for the P&ID demo UI.
 *
 * Strategy:
 *   - Run only Chromium (we ship Chromium-only via Playwright cache).
 *   - `webServer` fields below are NOT used; instead, the test runner
 *     expects an externally-booted backend (uvicorn) + frontend (vite dev).
 *     The verify script `scripts/verify_e2e.sh` handles bring-up.
 *   - baseURL points to the dev server. Override with PLAYWRIGHT_BASE_URL
 *     when running against a deployed environment.
 */
import { defineConfig, devices } from "@playwright/test";

const PORT = process.env.PLAYWRIGHT_PORT ?? "18006";
const BASE_URL =
  process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1600, height: 1000 },
      },
    },
  ],
  outputDir: "./e2e/.output",
});
