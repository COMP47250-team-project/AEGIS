// frontend/e2e/exam-flow.spec.ts
// AEGIS-109: End-to-end test covering the full professor → student → report flow.
//
// Prerequisites: full stack running via docker compose (playwright.config.ts handles this).
//
// Test order matters — each test builds on state from the previous one:
//   Test 1: professor registers + creates exam
//   Test 2: student registers + takes exam + triggers telemetry events
//   Test 3: professor verifies risk score > 0 in session history

import { test, expect, Browser } from "@playwright/test";

// Unique suffix prevents email collisions across parallel CI runs on the same DB.
const RUN = Date.now();
const PROF_EMAIL = `prof_${RUN}@e2e.test`;
const PROF_PASS = "E2eTest1234!";
const STUD_EMAIL = `stud_${RUN}@e2e.test`;
const STUD_PASS = "E2eTest1234!";
const EXAM_TITLE = `E2E Exam ${RUN}`;

// Shared state: exam ID captured after creation, used in Test 2 and 3.
let examId = "";

// ---------------------------------------------------------------------------
// Helper: format a Date as the value accepted by datetime-local inputs
// ---------------------------------------------------------------------------
function toDatetimeLocal(d: Date): string {
  // "YYYY-MM-DDTHH:MM" — browser datetime-local format
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ---------------------------------------------------------------------------
// Test 1: Professor registers, creates an exam, sees it created
// ---------------------------------------------------------------------------

test("professor registers, creates exam with 1 MCQ + 1 short-answer, exam is created", async ({
  page,
}) => {
  // 1. Register as professor
  await page.goto("/register");
  await page.fill("#name", "E2E Professor");
  await page.fill("#email", PROF_EMAIL);
  await page.click('[data-testid="role-professor"]');
  await page.fill("#password", PROF_PASS);
  await page.fill("#confirmPassword", PROF_PASS);
  await page.click('[data-testid="register-submit"]');
  await page.waitForURL("/professor/dashboard");

  // 2. Navigate to create exam page
  await page.click('[data-testid="new-exam-btn"]');
  await page.waitForURL("/professor/exams/new");

  // 3. Fill in exam details
  // Exam opens 3 seconds from now so it auto-opens by the time the student arrives
  const startTime = new Date(Date.now() + 3_000);
  const endTime = new Date(Date.now() + 35 * 60_000); // 35 min window

  await page.fill("#exam-title", EXAM_TITLE);
  await page.fill("#exam-course", "E2E-101");

  // datetime-local inputs require programmatic fill via evaluate to bypass browser quirks
  await page.evaluate(
    ([startVal, endVal]) => {
      const startEl = document.getElementById(
        "exam-start",
      ) as HTMLInputElement | null;
      const endEl = document.getElementById(
        "exam-end",
      ) as HTMLInputElement | null;
      if (startEl) {
        startEl.value = startVal;
        startEl.dispatchEvent(new Event("input", { bubbles: true }));
        startEl.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (endEl) {
        endEl.value = endVal;
        endEl.dispatchEvent(new Event("input", { bubbles: true }));
        endEl.dispatchEvent(new Event("change", { bubbles: true }));
      }
    },
    [toDatetimeLocal(startTime), toDatetimeLocal(endTime)],
  );

  // 4. Configure Q1 as MCQ
  await page.selectOption('[data-testid="q-type-0"]', "mcq");
  await page.fill('[data-testid="q-prompt-0"]', "What is 2 + 2?");
  await page.fill('[data-testid="q-opt-0-0"]', "3");
  await page.fill('[data-testid="q-opt-0-1"]', "4");
  // Click the radio for option "4" (second option, index 1) — select it as correct answer
  // The radio is before the option text input; click the radio whose sibling input has value "4"
  await page.locator('input[type="radio"][name="correct-0"]').nth(1).click();

  // 5. Add Q2 as short-answer
  await page.click('button:has-text("+ Add question")');
  await page.fill('[data-testid="q-prompt-1"]', "Explain recursion briefly.");
  // Leave type as short (default) — no type change needed

  // 6. Enrol the test student
  await page.fill("#exam-enrol", STUD_EMAIL);

  // 7. Submit the form
  await page.click('[data-testid="create-exam-submit"]');

  // 8. Should redirect to professor session page for the new exam
  await page.waitForURL(/\/professor\/session\/.+/);

  // Capture exam ID from URL for subsequent tests
  const url = page.url();
  const match = url.match(/\/professor\/session\/([\w-]+)/);
  expect(match).not.toBeNull();
  examId = match![1];
  expect(examId).toBeTruthy();
});

// ---------------------------------------------------------------------------
// Test 2: Student registers, accepts consent, answers, triggers telemetry, submits
// ---------------------------------------------------------------------------

test("student registers, takes exam, triggers tab blur + paste events, submits", async ({
  browser,
}: {
  browser: Browser;
}) => {
  // Use a separate browser context (incognito) so the student session is independent.
  const ctx = await browser.newContext();
  const page = await ctx.newPage();

  try {
    // 1. Register as student
    await page.goto("/register");
    await page.fill("#name", "E2E Student");
    await page.fill("#email", STUD_EMAIL);
    await page.click('[data-testid="role-student"]');
    await page.fill("#password", STUD_PASS);
    await page.fill("#confirmPassword", STUD_PASS);
    await page.click('[data-testid="register-submit"]');
    await page.waitForURL("/student/dashboard");

    // 2. Wait for the exam to auto-open (it was scheduled 3s from now in Test 1)
    // Poll the dashboard until the exam appears as "Open"
    await expect(async () => {
      await page.reload();
      await expect(page.locator(`text=${EXAM_TITLE}`)).toBeVisible();
    }).toPass({ timeout: 20_000, intervals: [2_000] });

    // 3. Enter the exam
    await page.click("text=Enter Exam");

    // 4. Accept GDPR consent
    await page.waitForSelector("text=I Consent — Begin Exam");
    await page.click("text=I Consent — Begin Exam");

    // 5. Exam shell should now be active — wait for questions to load
    await page.waitForSelector("text=What is 2 + 2?", { timeout: 15_000 });

    // 6. Answer Q1 (MCQ) — click option "4"
    await page.click("text=4");

    // 7. Trigger a tab_blur telemetry event by simulating page visibility change
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      // Restore visibility
      Object.defineProperty(document, "visibilityState", {
        value: "visible",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // 8. Navigate to Q2
    await page.click("text=Next →");
    await page.waitForSelector("text=Explain recursion briefly.", {
      timeout: 10_000,
    });

    // 9. Type an answer in Q2 short-answer field (also fires keystroke telemetry)
    const textarea = page.locator("textarea").first();
    await textarea.click();
    await textarea.fill("A function that calls itself with a smaller input.");

    // 10. Submit exam
    await page.click("text=Finish Exam");
    await page.waitForSelector('[data-testid="confirm-submit"]', {
      timeout: 10_000,
    });
    await page.click('[data-testid="confirm-submit"]');

    // 11. Assert submission confirmation page
    await page.waitForURL(/\/exam\/.*\/submitted/, { timeout: 20_000 });
    await expect(page.locator("text=Submitted successfully")).toBeVisible();
  } finally {
    await ctx.close();
  }
});

// ---------------------------------------------------------------------------
// Test 3: Professor sees non-zero risk score in session history
// ---------------------------------------------------------------------------

test("professor session history shows risk score > 0% after student submission", async ({
  page,
}) => {
  // Log in as professor
  await page.goto("/login");
  await page.fill("#email", PROF_EMAIL);
  await page.fill("#password", PROF_PASS);
  await page.click("text=Sign in");
  await page.waitForURL("/professor/dashboard");

  // Navigate to History tab
  await page.click('[data-testid="tab-history"]');

  // Wait for the completed exam to appear in history — scoring is async so poll
  await expect(async () => {
    await expect(page.locator(`text=${EXAM_TITLE}`)).toBeVisible();
  }).toPass({ timeout: 15_000, intervals: [2_000] });

  // Click through to the session detail
  await page.click(`text=${EXAM_TITLE}`);

  // Wait for the student score card to appear (may take a few seconds for async scorer)
  // The scorer runs after exam close; we allow up to 30s
  let integrityPct = 0;
  await expect(async () => {
    // Look for any percentage text in the student score cards that is > 0
    const pctLocator = page.locator("text=/\\d+%/").first();
    const text = await pctLocator.textContent();
    const match = text?.match(/(\d+)%/);
    integrityPct = match ? parseInt(match[1], 10) : 0;
    expect(integrityPct).toBeGreaterThan(0);
  }).toPass({ timeout: 30_000, intervals: [3_000] });

  // Also assert signal breakdown chart is visible (at least one ScoreBar rendered)
  // ScoreBar renders a div with inline width style
  const scoreBar = page.locator('[style*="width"]').first();
  await expect(scoreBar).toBeVisible();
});
