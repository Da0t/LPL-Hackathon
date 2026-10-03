/* Opt-in AWS acceptance: requires running authenticated backend and frontend.
 * Uses private ignored demo sign-ins; creates one fictional request/reply loop.
 * NODE_PATH=/path/to/playwright/node_modules node tests/portal/upgrades.cjs
 */
const { chromium } = require("playwright");
const fs = require("node:fs");
const assert = require("node:assert/strict");
const users = JSON.parse(
  fs.readFileSync(process.env.PORTAL_ACCESS_FILE || "var/demo-access.json"),
);
const base = process.env.PORTAL_URL || "http://127.0.0.1:3200";
async function login(browser, role) {
  const [email, user] = Object.entries(users).find(([, u]) => u.role === role);
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1100 },
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base + "/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(user.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL("**/" + (role === "staff" ? "dashboard" : "workspace"));
  return { context, page, user, errors };
}
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const client = await login(browser, "client");
    const { page, context } = client;
    await page
      .getByRole("button", { name: "Larger text", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Stronger contrast", exact: true })
      .click();
    await page.reload();
    await page.locator(".large-text.strong-contrast").waitFor();
    assert.equal(
      await page
        .getByRole("button", { name: "Larger text", exact: true })
        .getAttribute("aria-pressed"),
      "true",
    );
    await page.setViewportSize({ width: 390, height: 844 });
    for (const route of [
      "/workspace",
      "/workspace/profile",
      "/workspace/finances",
      "/workspace/requests/new",
    ]) {
      await page.goto(base + route);
      await page.locator("h1").waitFor();
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
        "large text mobile overflow " + route,
      );
    }
    await page.screenshot({
      path: "/tmp/coherent-accessible-mobile.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 1600, height: 1100 });
    await page
      .getByRole("button", { name: "Larger text", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Stronger contrast", exact: true })
      .click();
    await page
      .getByLabel("Your request", { exact: true })
      .fill(
        "I would like to discuss withdrawing $6,000 from my old workplace retirement account.",
      );
    await page
      .getByRole("button", { name: "Read question and options", exact: true })
      .waitFor({ timeout: 90000 });
    const speech = page.waitForResponse((r) =>
      r.url().endsWith("/portal/speech"),
    );
    await page
      .getByRole("button", { name: "Read question and options", exact: true })
      .click();
    const audio = await speech;
    assert.equal(audio.status(), 200);
    assert.equal(audio.headers()["content-type"], "audio/mpeg");
    assert(Number(audio.headers()["content-length"]) > 1000);
    await page
      .getByRole("button", { name: "Stop reading", exact: true })
      .first()
      .waitFor();
    await page
      .getByRole("button", { name: "Stop reading", exact: true })
      .first()
      .click();
    await page
      .getByLabel("Account to discuss", { exact: true })
      .selectOption("ACCT-201");
    await page
      .getByLabel("Amount to discuss, in dollars (optional)", { exact: true })
      .fill("6000");
    await page
      .getByLabel("Request description", { exact: true })
      .fill(
        "Please discuss a possible $6,000 withdrawal from my old workplace rollover IRA. No transaction is authorized.",
      );
    const archived = page.waitForResponse(
      (r) => r.url().endsWith("/archive") && r.request().method() === "POST",
      { timeout: 120000 },
    );
    await page
      .getByRole("button", { name: "Confirm and send request", exact: true })
      .click();
    const document = await (await archived).json();
    assert(document.case_id);
    const id = document.case_id;
    await page
      .getByRole("heading", { name: "Request sent", exact: true })
      .waitFor();
    const staff = await login(browser, "staff");
    await staff.page.goto(base + "/dashboard?case=" + id);
    await staff.page
      .getByLabel("Independent record audit")
      .waitFor({ timeout: 120000 });
    assert.match(
      await staff.page.getByLabel("Independent record audit").innerText(),
      /bedrock\+deterministic/,
    );
    await staff.page
      .getByRole("tab", { name: "Compliance & history", exact: true })
      .click();
    await staff.page
      .getByRole("button", { name: "Run review", exact: true })
      .click();
    await staff.page
      .getByLabel("Retrieved compliance guidance")
      .waitFor({ timeout: 120000 });
    assert.match(
      await staff.page.getByLabel("Retrieved compliance guidance").innerText(),
      /SEC-REG-BI-CARE/,
    );
    await staff.page.screenshot({
      path: "/tmp/coherent-cited-compliance.png",
      fullPage: true,
    });
    const clarification =
      "What timing would work for a conversation with your advisor?";
    const response = await staff.context.request.post(
      base + "/api/staff/cases/" + id + "/action",
      { data: { action: "clarify", text: clarification }, timeout: 120000 },
    );
    assert.equal(response.status(), 200, await response.text());
    await page.goto(base + "/workspace/requests");
    const card = page
      .locator(".request-card")
      .filter({ hasText: `Reference ${id}` });
    await card.getByText(clarification, { exact: true }).waitFor();
    await card
      .getByLabel("Your answer")
      .fill("Tomorrow afternoon works for a conversation.");
    await card
      .getByRole("button", { name: "Send answer", exact: true })
      .click();
    await card
      .getByText("Tomorrow afternoon works for a conversation.", {
        exact: true,
      })
      .waitFor();
    const updated = await (
      await staff.context.request.get(base + "/api/staff/cases/" + id)
    ).json();
    assert(updated.history.some((e) => e.event === "client_replied"));
    assert.deepEqual(client.errors, []);
    assert.deepEqual(staff.errors, []);
    console.log(
      "PASS live Polly, persistent accessibility at 390px, Bedrock audit, cited KB review, and client/advisor reply loop",
      id,
    );
  } catch (error) {
    for (const context of browser.contexts())
      for (const page of context.pages()) {
        await page.screenshot({
          path: "/tmp/coherent-upgrades-failed.png",
          fullPage: true,
        });
      }
    throw error;
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
