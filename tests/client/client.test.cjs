const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
const { chromium } = require("playwright");
const root = path.resolve(__dirname, "../..");
const url = "http://127.0.0.1:18003/client";
const api = "http://127.0.0.1:18001";
let browser, server;
const artifacts = path.join(__dirname, "artifacts");

before(async () => {
  fs.mkdirSync(artifacts, { recursive: true });
  server = spawn(
    "python3",
    ["tests/client/preview.py", "--port", "18003", "--api-port", "18001"],
    { cwd: root, stdio: "ignore" },
  );
  for (let i = 0; i < 80; i++) {
    try {
      if ((await fetch(url)).ok) break;
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  browser = await chromium.launch({ headless: true });
});
after(async () => {
  await browser?.close();
  server?.kill();
});

async function pageFor(client = "CLIENT-017", init) {
  const context = await browser.newContext({
    viewport: { width: 1366, height: 768 },
  });
  if (init) await context.addInitScript(init);
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(url);
  await page.locator("#start").waitFor();
  await page.selectOption("#client", client);
  await page.locator("#start").click();
  await page.locator("#words").waitFor({ state: "visible" });
  return { page, context, errors };
}
async function typeRequest(page, words) {
  await page.fill("#words", words);
  await page.locator("#suggestion-section").waitFor({ state: "visible" });
}
async function selectedReview(page) {
  await page.locator(".suggestion-card").first().click();
  await page.waitForFunction(() => !document.querySelector("#review").disabled);
  await page.locator("#review").click();
  await page.locator("#summary").waitFor({ state: "visible" });
}

test("keyboard IRA mismatch -> corrected account and amount -> matching staff case", async () => {
  const { page, context, errors } = await pageFor();
  let confirmations = 0;
  page.on("request", (req) => {
    if (req.url().endsWith("/confirm")) confirmations++;
  });
  await typeRequest(
    page,
    "I need six thousand dollars from the Roth thing from my old job.",
  );
  assert.match(await page.textContent("#question"), /don.t see a Roth IRA/);
  assert.equal(await page.locator(".suggestion-card").count(), 2);
  await page.getByText("What is a rollover IRA?").click();
  assert.match(
    await page.textContent("#definitions"),
    /money moved from an earlier workplace/,
  );
  await page.screenshot({
    path: path.join(artifacts, "01-clarification.png"),
    fullPage: true,
  });
  await page.locator(".suggestion-card").first().focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => !document.querySelector("#review").disabled);
  await page.locator("#review").focus();
  await page.keyboard.press("Enter");
  await page.locator("#summary").waitFor({ state: "visible" });
  assert.equal(await page.inputValue("#account"), "ACCT-201");
  assert.equal(await page.inputValue("#amount"), "");
  assert.match(await page.textContent("#account"), /4821/);
  const corrected =
    "I want to discuss using $6,000 from my retirement account from my former employer for care expenses.";
  await page.fill("#summary", corrected);
  await page.fill("#amount", "6,000");
  assert.equal(confirmations, 0);
  await page.screenshot({
    path: path.join(artifacts, "02-review.png"),
    fullPage: true,
  });
  await page.locator("#confirm").focus();
  await page.keyboard.press("Enter");
  await page.locator("#success-screen").waitFor({ state: "visible" });
  const caseId = await page.textContent("#case-id");
  const response = await fetch(api + "/staff/cases/" + caseId, {
    headers: { "X-Demo-Role": "staff" },
  });
  const record = await response.json();
  assert.equal(record.confirmed_plain_language_request, corrected);
  assert.equal(record.selected_account_id, "ACCT-201");
  assert.equal(record.amount_requested, 6000);
  assert.match(record.original_words, /Roth thing/);
  assert.equal(confirmations, 1);
  await page.screenshot({
    path: path.join(artifacts, "03-submitted.png"),
    fullPage: true,
  });
  assert.deepEqual(errors, []);
  await context.close();
});

test("plain request, editable account, amount validation, explicit null amount", async () => {
  const { page, context } = await pageFor("CLIENT-022");
  await typeRequest(
    page,
    "I have a question about my Roth retirement account.",
  );
  assert.doesNotMatch(await page.textContent("#question"), /don.t see a Roth/);
  await selectedReview(page);
  await page.fill("#amount", "6,00");
  await page.click("#confirm");
  assert.match(await page.textContent("#error"), /positive dollar amount/);
  await page.fill("#amount", "");
  const request = page.waitForRequest((req) => req.url().endsWith("/confirm"));
  await page.click("#confirm");
  const payload = (await request).postDataJSON();
  assert.equal(payload.amount_requested, null);
  assert.equal(payload.selected_account_id, "ACCT-301");
  await page.locator("#success-screen").waitFor({ state: "visible" });
  await context.close();
});

test("refresh restores words without starting, interpreting, or confirming automatically", async () => {
  const { page, context } = await pageFor();
  await page.click("#pause");
  await page.fill("#words", "Please help me update my beneficiary.");
  let posts = 0;
  page.on("request", (r) => {
    if (r.method() === "POST") posts++;
  });
  await page.reload();
  await page.locator("#restored").waitFor({ state: "visible" });
  await page.waitForTimeout(1500);
  assert.equal(posts, 0);
  await page.click("#start");
  await page.locator("#words").waitFor({ state: "visible" });
  assert.equal(
    await page.inputValue("#words"),
    "Please help me update my beneficiary.",
  );
  await page.waitForTimeout(1500);
  assert.equal(posts, 1);
  await context.close();
});

test("stale responses never replace newer words; turns are paced; None clears selection", async () => {
  const { page, context } = await pageFor();
  const timings = [];
  let delayed = true;
  await page.route("**/intake/*/turn", async (route) => {
    timings.push(Date.now());
    const response = await route.fetch();
    if (delayed) {
      delayed = false;
      await new Promise((r) => setTimeout(r, 1700));
    }
    await route.fulfill({ response });
  });
  await page.fill("#words", "The Roth thing from my old job.");
  await page.waitForRequest("**/intake/*/turn");
  await page.fill("#words", "I need help with everyday investments.");
  await page.locator("#suggestion-section").waitFor({ state: "visible" });
  assert.doesNotMatch(await page.textContent("#question"), /don.t see a Roth/);
  await selectedReview(page);
  await page.click("#back");
  await page.click("#none");
  await page.click("#review");
  await page.locator("#account").waitFor({ state: "visible" });
  assert.equal(await page.inputValue("#account"), "");
  for (let i = 1; i < timings.length; i++)
    assert.ok(timings[i] - timings[i - 1] >= 1100);
  await context.close();
});

test("recoverable turn errors preserve words and permit human help with no selected account", async () => {
  const { page, context } = await pageFor();
  let fail = true;
  await page.route("**/intake/*/turn", async (route) => {
    if (fail) {
      fail = false;
      return route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ message: "Service busy." }),
      });
    }
    return route.continue();
  });
  await page.fill("#words", "I need a person to help me.");
  await page.locator("#error").waitFor({ state: "visible" });
  assert.equal(await page.inputValue("#words"), "I need a person to help me.");
  await page.click("#person");
  await page.locator("#summary").waitFor({ state: "visible" });
  assert.equal(await page.inputValue("#account"), "");
  assert.match(await page.inputValue("#summary"), /speak with a person/);
  await page.click("#confirm");
  await page.locator("#success-screen").waitFor({ state: "visible" });
  await context.close();
});

test("uncertain submission is not automatically retried or reported as success", async () => {
  const { page, context } = await pageFor();
  await typeRequest(page, "I have a retirement account question.");
  await selectedReview(page);
  let calls = 0;
  await page.route("**/intake/*/confirm", (route) => {
    calls++;
    return route.abort();
  });
  await page.click("#confirm");
  await page.locator("#error").waitFor({ state: "visible" });
  assert.match(await page.textContent("#error"), /couldn.t verify/);
  assert.ok(await page.locator("#confirm").isDisabled());
  assert.equal(calls, 1);
  assert.ok(await page.locator("#success-screen").isHidden());
  await context.close();
});

test("unsupported and denied microphone both leave typing fully usable; mobile has no overflow", async () => {
  for (const denied of [false, true]) {
    const { page, context } = await pageFor(
      "CLIENT-017",
      denied
        ? () => {
            window.webkitSpeechRecognition = undefined;
            window.SpeechRecognition = class {
              start() {
                setTimeout(() => this.onerror({ error: "not-allowed" }), 0);
              }
              stop() {}
            };
          }
        : () => {
            window.SpeechRecognition = undefined;
            window.webkitSpeechRecognition = undefined;
          },
    );
    if (denied) {
      await page.click("#mic");
      await page.waitForFunction(() =>
        document.querySelector("#speech-status").textContent.includes("denied"),
      );
    }
    assert.match(
      await page.textContent("#speech-status"),
      denied ? /denied/ : /doesn.t support/,
    );
    await page.setViewportSize({ width: 390, height: 844 });
    await typeRequest(page, "I need help with my account.");
    await selectedReview(page);
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await page.click("#confirm");
    await page.locator("#success-screen").waitFor({ state: "visible" });
    await context.close();
  }
});
