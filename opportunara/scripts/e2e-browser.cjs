// Real-browser end-to-end walkthrough + screenshots for the demo.
// Run with: node e2e-browser.cjs   (Playwright installed in %TEMP%\pwtest)

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const OUT = path.resolve(__dirname, "..", "docs", "screenshots");

const errors = [];
const failedRequests = [];

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const page = await context.newPage();

  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("requestfailed", (request) =>
    failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText}`),
  );

  const shot = async (name, fullPage = false) => {
    await page.screenshot({ path: path.join(OUT, name), fullPage });
    console.log("  screenshot:", name, fullPage ? "(full page)" : "(viewport)");
  };

  // 1. Home hero + upload
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.getByRole("heading", { level: 1 }).waitFor({ timeout: 15000 });
  console.log("HOME h1:", (await page.getByRole("heading", { level: 1 }).innerText()).replace(/\n/g, " "));
  await shot("01-home.png", true);

  // 2. Use sample profile -> editable profile card
  await page.getByRole("button", { name: /Use sample profile/i }).click();
  await page.getByRole("link", { name: /Rank my matches/i }).waitFor({ timeout: 30000 });
  console.log("PARSE ok: profile card rendered");
  await shot("02-profile.png", true);

  const skillsShown = await page.locator("text=CampusHire").count();
  console.log("profile shows project CampusHire:", skillsShown > 0);

  // 3. Matches screen
  await page.getByRole("link", { name: /Rank my matches/i }).click();
  await page.waitForURL("**/matches", { timeout: 20000 });
  await page.locator('a[href^="/kit/"]').first().waitFor({ timeout: 60000 });
  const cards = await page.locator('a[href^="/kit/"]').count();
  console.log("MATCHES cards:", cards);
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot("03-matches.png");

  // 4. Expand a high-risk trust badge
  const riskyBadge = page.getByRole("button", { name: /High risk/i }).first();
  if (await riskyBadge.count()) {
    await riskyBadge.click();
    await page.waitForTimeout(400);
    const reason = await page.locator("li", { hasText: /pts\)/ }).first().innerText().catch(() => "");
    console.log("RISK FLAG:", reason.replace(/\n/g, " ").slice(0, 120));
    await riskyBadge.scrollIntoViewIfNeeded();
    await shot("04-risk-badge.png");
  } else {
    console.log("RISK BADGE: none visible on the first screen");
  }

  // 5. "Check a listing" modal with pasted scam text
  await page.getByRole("button", { name: /Check a listing/i }).click();
  const textarea = page.locator("textarea").first();
  await textarea.waitFor({ timeout: 10000 });
  await textarea.fill(
    "URGENT internship - apply within 2 hours. Pay a refundable security deposit of Rs 1,999. " +
      "Contact hr.quickjobs@gmail.com or WhatsApp only for the application form. " +
      "Guaranteed placement with no interview. Register at https://bit.ly/xyz",
  );
  await page.getByRole("button", { name: /Check trust signals/i }).click();
  await page.waitForTimeout(2500);
  await shot("05-verify-modal.png");
  const modalText = await page.locator('[role="dialog"]').innerText().catch(() => "");
  console.log("VERIFY MODAL:", modalText.replace(/\n/g, " ").slice(0, 220));

  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);

  // 6. Calendar download from up to 3 selections
  const checkboxes = page.locator('input[type="checkbox"]');
  const checkboxCount = await checkboxes.count();
  console.log("selection checkboxes:", checkboxCount);
  if (checkboxCount > 0) {
    for (let index = 0; index < Math.min(3, checkboxCount); index += 1) {
      await checkboxes.nth(index).check({ force: true }).catch(() => {});
    }
    await page.waitForTimeout(300);
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 15000 }).catch(() => null),
      page.getByRole("button", { name: /Download calendar/i }).click().catch(() => {}),
    ]);
    console.log("CALENDAR download:", download ? download.suggestedFilename() : "no download event");
  }

  // 7. Application kit for the first match
  await page.locator('a[href^="/kit/"]').first().click();
  await page.waitForURL("**/kit/**", { timeout: 20000 });
  await page.getByRole("tab", { name: /Gap analysis/i }).waitFor({ timeout: 30000 });
  console.log("KIT url:", page.url());
  await shot("06-kit-gaps.png", true);

  await page.getByRole("tab", { name: /Resume bullets/i }).click();
  await page.waitForTimeout(400);
  await shot("07-kit-bullets.png");

  await page.getByRole("tab", { name: /Cover note/i }).click();
  await page.waitForTimeout(400);
  await shot("08-kit-cover.png");

  // 8. Mobile layout (reuse the desktop storage so the profile/matches persist)
  const storageState = await context.storageState();
  await context.close();
  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    storageState,
  });
  const mobilePage = await mobile.newPage();
  await mobilePage.goto(`${BASE}/matches`, { waitUntil: "networkidle" });
  await mobilePage.locator('a[href^="/kit/"]').first().waitFor({ timeout: 30000 }).catch(() => {});
  await mobilePage.waitForTimeout(1200);
  await mobilePage.screenshot({ path: path.join(OUT, "09-mobile-matches.png") });
  console.log("  screenshot: 09-mobile-matches.png");
  await mobile.close();

  // 9. Empty state (no profile in storage)
  const emptyCtx = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const emptyPage = await emptyCtx.newPage();
  await emptyPage.goto(`${BASE}/matches`, { waitUntil: "networkidle" });
  await emptyPage.waitForTimeout(900);
  await emptyPage.screenshot({ path: path.join(OUT, "10-empty-state.png") });
  console.log("  screenshot: 10-empty-state.png");
  await emptyCtx.close();

  // 10. Error state (API unreachable) — toast + retry panel
  const errorCtx = await browser.newContext({ viewport: { width: 1440, height: 960 }, storageState });
  const errorPage = await errorCtx.newPage();
  const errorConsole = [];
  errorPage.on("console", (m) => { if (m.type() === "error") errorConsole.push(m.text()); });
  await errorPage.route("**/api/match", (route) => route.abort("failed"));
  await errorPage.goto(`${BASE}/matches`, { waitUntil: "networkidle" });
  await errorPage.waitForTimeout(1500);
  await errorPage.screenshot({ path: path.join(OUT, "11-error-state.png") });
  const errorCopy = await errorPage.locator('[role="alert"], [role="status"]').first().innerText().catch(() => "");
  console.log("  screenshot: 11-error-state.png | alert:", errorCopy.replace(/\n/g, " ").slice(0, 140));
  await errorCtx.close();

  await browser.close();

  console.log("\nCONSOLE ERRORS:", errors.length);
  errors.slice(0, 10).forEach((error) => console.log("  -", error.slice(0, 240)));
  console.log("FAILED REQUESTS:", failedRequests.length);
  failedRequests.slice(0, 10).forEach((line) => console.log("  -", line.slice(0, 240)));
  console.log("SCREENSHOT DIR:", OUT);
}

main().catch(async (error) => {
  console.error("E2E FAILED:", error.message);
  process.exitCode = 1;
});
