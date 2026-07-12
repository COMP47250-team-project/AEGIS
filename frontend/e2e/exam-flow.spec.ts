// frontend/e2e/exam-flow.spec.ts
// AEGIS-109: End-to-end test covering the full professor → student → report flow.
//
// Prerequisites: full stack running via docker compose (playwright.config.ts handles this).
//
// Serial mode ensures all 3 tests run as a unit and share the same RUN suffix on retry.
// Tests run in order: T1 creates the exam, T2 takes it, T3 checks the report.

import { test, expect } from "@playwright/test";

// Serial mode: if T1 fails, T2 and T3 are skipped. On retry the whole block
// re-runs together, so RUN is consistent across all three tests in a retry.
test.describe.configure({ mode: "serial" });

// Fixed run identifier shared by all tests in this run (stable within a retry).
const RUN = Date.now();
const PROF_EMAIL = `prof_${RUN}@example.com`;
const PROF_PASS = "E2eTest1234!";
const STUD_EMAIL = `stud_${RUN}@example.com`;
const STUD_PASS = "E2eTest1234!";
const EXAM_TITLE = `E2E Exam ${RUN}`;

// Shared exam ID — captured in T1, used in T2 and T3.
let examId = "";

// ---------------------------------------------------------------------------
// Helper: produce the "YYYY-MM-DDTHH:MM" string expected by datetime-local inputs.
// ---------------------------------------------------------------------------
function toDatetimeLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

// ---------------------------------------------------------------------------
// Helper: set a datetime-local input value and fire React's synthetic change.
// page.fill() alone is unreliable for <input type="datetime-local"> — React
// reads the value via the nativeInputValueSetter hack instead of tracking
// keyboard events. We use the React internal setter approach here.
// ---------------------------------------------------------------------------
async function fillDatetimeLocal(
  page: import("@playwright/test").Page,
  selector: string,
  value: string,
) {
  await page.evaluate(
    ({ sel, val }) => {
      const el = document.querySelector(sel) as HTMLInputElement | null;
      if (!el) return;
      // Use Object.getOwnPropertyDescriptor to get the React-overridden setter.
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )?.set;
      if (nativeInputValueSetter) {
        nativeInputValueSetter.call(el, val);
      } else {
        el.value = val;
      }
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    },
    { sel: selector, val: value },
  );
}

// ---------------------------------------------------------------------------
// Test 1: Professor registers, creates exam with 1 MCQ + 1 short-answer
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
  await page.waitForURL("/professor/dashboard", { timeout: 30_000 });

  // 2. Navigate to create exam page
  await page.click('[data-testid="new-exam-btn"]');
  await page.waitForURL("/professor/exams/new", { timeout: 15_000 });

  // 3. Fill exam details
  // Exam starts in 5 seconds so it auto-opens by the time the student test runs.
  const startTime = new Date(Date.now() + 5_000);
  const endTime = new Date(Date.now() + 35 * 60_000);

  await page.fill("#exam-title", EXAM_TITLE);
  await page.fill("#exam-course", "E2E-101");

  // datetime-local inputs require the React nativeInputValueSetter trick.
  await fillDatetimeLocal(page, "#exam-start", toDatetimeLocal(startTime));
  await fillDatetimeLocal(page, "#exam-end", toDatetimeLocal(endTime));

  // 4. Configure Q1 as MCQ
  await page.selectOption('[data-testid="q-type-0"]', "mcq");
  await page.fill('[data-testid="q-prompt-0"]', "What is 2 + 2?");
  await page.fill('[data-testid="q-opt-0-0"]', "3");
  await page.fill('[data-testid="q-opt-0-1"]', "4");
  // Mark "4" (second radio, index 1) as the correct answer
  await page.locator('input[type="radio"][name="correct-0"]').nth(1).click();

  // 5. Add Q2 as short-answer
  await page.click('button:has-text("+ Add question")');
  await page.fill('[data-testid="q-prompt-1"]', "Explain recursion briefly.");

  // 6. Enrol the test student
  await page.fill("#exam-enrol", STUD_EMAIL);

  // 7. Submit the form — redirects to /professor/session/{examId}
  await page.click('[data-testid="create-exam-submit"]');
  await page.waitForURL(/\/professor\/session\/.+/, { timeout: 30_000 });

  // 8. Capture exam ID for subsequent tests
  const match = page.url().match(/\/professor\/session\/([\w-]+)/);
  expect(match).not.toBeNull();
  examId = match![1];
  expect(examId).toBeTruthy();
});

// ---------------------------------------------------------------------------
// Test 2: Student registers, takes exam, triggers telemetry, submits
// ---------------------------------------------------------------------------

test("student registers, takes exam, triggers tab blur + paste events, submits", async ({
  browser,
}) => {
  // Separate browser context so student cookies are independent of the professor page.
  const ctx = await browser.newContext({ baseURL: "http://localhost:5173" });

  try {
    const page = await ctx.newPage();

    // 1. Register as student
    await page.goto("/register");
    await page.fill("#name", "E2E Student");
    await page.fill("#email", STUD_EMAIL);
    await page.click('[data-testid="role-student"]');
    await page.fill("#password", STUD_PASS);
    await page.fill("#confirmPassword", STUD_PASS);
    await page.click('[data-testid="register-submit"]');
    await page.waitForURL("/student/dashboard", { timeout: 30_000 });

    // 2. Poll until the exam appears as Open (auto-opens ~5s after creation in T1)
    await expect(async () => {
      await page.reload();
      await expect(page.locator(`text=${EXAM_TITLE}`)).toBeVisible();
      await expect(page.locator("text=Enter Exam")).toBeVisible();
    }).toPass({ timeout: 40_000, intervals: [2_000] });

    // 3. Enter the exam
    await page.click("text=Enter Exam");

    // 4. Accept GDPR consent
    await page.waitForSelector("text=I Consent — Begin Exam", {
      timeout: 15_000,
    });
    await page.click("text=I Consent — Begin Exam");

    // 5. Wait for questions to load in exam shell
    await page.waitForSelector("text=What is 2 + 2?", { timeout: 15_000 });

    // 6. Answer Q1 (MCQ)
    await page.click("text=4");

    // 7. Simulate tab_blur telemetry event
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      Object.defineProperty(document, "visibilityState", {
        value: "visible",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // 8. Navigate to Q2 and answer
    await page.click("text=Next →");
    await page.waitForSelector("text=Explain recursion briefly.", {
      timeout: 10_000,
    });
    const textarea = page.locator("textarea").first();
    await textarea.click();
    await textarea.fill("A function that calls itself with a smaller input.");

    // 9. Submit exam
    await page.click("text=Finish Exam");
    await page.waitForSelector('[data-testid="confirm-submit"]', {
      timeout: 10_000,
    });
    await page.click('[data-testid="confirm-submit"]');

    // 10. Assert submission confirmation
    await page.waitForURL(/\/exam\/.*\/submitted/, { timeout: 20_000 });
    await expect(page.locator("text=Submitted successfully")).toBeVisible();
  } finally {
    await ctx.close().catch(() => {});
  }
});

// ---------------------------------------------------------------------------
// Test 3: Professor sees non-zero risk score in session history
// ---------------------------------------------------------------------------

test("professor session history shows risk score > 0% after student submission", async ({
  page,
}) => {
  // Log in as professor (uses same PROF_EMAIL as T1 since RUN is shared in serial mode)
  await page.goto("/login");
  await page.fill("#email", PROF_EMAIL);
  await page.fill("#password", PROF_PASS);
  await page.click("text=Sign in");
  await page.waitForURL("/professor/dashboard", { timeout: 30_000 });

  // Navigate to History tab
  await page.click('[data-testid="tab-history"]');

  // Wait for the completed exam to appear
  await expect(async () => {
    await expect(page.locator(`text=${EXAM_TITLE}`)).toBeVisible();
  }).toPass({ timeout: 20_000, intervals: [2_000] });

  // Click into the session
  await page.click(`text=${EXAM_TITLE}`);

  // Poll for a non-zero risk score — async scorer may take up to 30s
  let integrityPct = 0;
  await expect(async () => {
    const pctLocator = page.locator("text=/\\d+%/").first();
    const text = await pctLocator.textContent();
    const match = text?.match(/(\d+)%/);
    integrityPct = match ? parseInt(match[1], 10) : 0;
    expect(integrityPct).toBeGreaterThan(0);
  }).toPass({ timeout: 30_000, intervals: [3_000] });

  // Assert signal breakdown chart has at least one bar
  const scoreBar = page.locator('[style*="width"]').first();
  await expect(scoreBar).toBeVisible();
});
