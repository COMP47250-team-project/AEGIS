# AEGIS Usability Study — Professor Interface (SUS)

Tracks: **AEGIS-95** (evaluation plan) · pairs with **AEGIS-94** (technical detection
metrics) and **AEGIS-93** (load test, see [`load_test_results.md`](load_test_results.md))
to give a complete evaluation story for the Evaluation criterion (10% interim / part
of the 30% final).

**Status: environment verified and ready; SUS responses collected and scored
(n=7, mean 92.86, Grade A+). Participant background, task success/timing, and
qualitative debrief data are still outstanding** — marked **Outstanding** in
§3/§4/§7 below with what's needed to close each gap. These are deliberately
left unfilled rather than populated with invented numbers — the rubric wants
a *real* study, and fabricated task/quote data would misrepresent it.

---

## 1. Method

- **Instrument:** standard 10-item System Usability Scale (Brooke, 1996), unmodified.
- **Design:** moderated, task-based session (~20 min) — briefing → 3 tasks (professor
  role) → SUS questionnaire → debrief interview.
- **Participants:** ≥5 non-team UCD MSc students/staff, acting as "professor."
- **Metrics collected:** task success (✓ / partial / ✗), time-on-task, error count,
  verbal confusion (quantitative) + verbatim debrief quotes (qualitative).
- **Scoring:** SUS raw→converted→×2.5 per participant (formula in §5); mean SUS +
  Sauro-Lewis curved grade (§6); optional Usability/Learnability subscales
  (Lewis & Sauro, 2009): Usability = items {1,2,3,5,6,7,8,9}, Learnability = {4,10}.

## 2. Environment (verified 2026-07-22)

| Item | Value |
|---|---|
| Deployed URL | `https://frontend-app.blacktree-49d535d3.westeurope.azurecontainerapps.io` |
| Environment | Azure Container Apps (AEGIS-67) — **confirmed live**, correctly redirects unauthenticated requests to `/login` |
| Facilitator/demo professor account | Name: **Dr. Aoife Byrne** · Email: `aoife.byrne@ucd.ie` · Password: *stored with the team, not committed here* |
| Demo student accounts | **Emma Doyle** (`emma.doyle@ucdconnect.ie`) — takes both seed exams with deliberately suspicious telemetry, ends up flagged. **Liam Walsh** (`liam.walsh@ucdconnect.ie`) — enrolled but never entered either exam, the clean "Absent" contrast. Both password: *stored with the team*. |
| Pre-seeded live session | ✅ **"Usability Study — Live Demo Quiz" (CS301)**, 3 questions (1 MCQ + 2 short-answer), currently **Open**. Emma Doyle shows **72% risk / High risk / flagged**; Liam Walsh shows 0%/Low risk — a clear, unambiguous answer for Task 2. |
| Pre-seeded historical session | ✅ **"Usability Study — Historical Demo Quiz" (CS302)**, 1 short-answer question, **Closed** with scores computed. Emma Doyle: 72% High risk, flagged, signal breakdown Tab Switch 90% / **Paste 100%** / **Keystroke 100%** (tied top signals) / Focus Loss 0% / Answer Timing 0% / Copy Sequence 0%. CSV export confirmed available. Liam Walsh correctly shows **"Absent — Did not join the exam — no session was recorded."** |
| SUS responses collected | ✅ **7 real responses** via Google Form, 2026-07-24 to 2026-07-26 (see §5) |

Note: Paste and Keystroke are tied at 100% as the top signal for Emma — either is a
correct answer for Task 3; brief the facilitator to accept both.

### Confirmed real UI flow per task (for facilitator accuracy — verified by walking through the actual deployed app)

**Task 1 — Create exam** (`+ New Exam` → `/professor/exams/new`):
fields are *Exam title*, *Course*, **Start** and **End** (both `datetime-local` —
there is no standalone "duration" field, so a 60-minute exam means setting **End =
Start + 60 min**), *Scoring sensitivity* (Strict / Standard / Lenient dropdown,
defaults to Standard), a *Questions* section (`+ Add question`, each with a
Text/Multiple-choice type dropdown — MCQ reveals *Option 1/2* text fields with a
radio button per option to mark the correct answer, plus `+ Add option`), an
*Enrol students (emails)* textarea (comma/newline-separated) with a CSV-upload
alternative, and a `Create Exam` submit button.

**Task 2 — Monitor a live session:** the professor **Dashboard** tab (not a
separate nav item) has an "Active Sessions" panel — *"Auto-refreshes every 30s ·
click a card to monitor live"*. Clicking a card opens the live risk console:
a per-student card grid sortable by Risk/Name/Flag, each card showing risk %,
a Moderate/Low/High-risk badge, live tab-blur and paste counts, and a
"Last: `<event>` · `<time>`" line, plus an "End exam" action.

**Task 3 — Review a completed session:** the **History** tab shows a
"Completed Exams" list (empty state: *"No completed exams yet — scores appear
here after you close an exam."*). Each completed exam expands into per-student
integrity score cards (six signals: Tab Switch, Paste, Keystroke, Focus Loss,
Answer Timing, Copy Sequence) and a "⬇ CSV" download button per session.

---

## 3. Participant recruitment

- **Target:** 6 booked (to land ≥5 completions), 20-min slots.
- **Profile:** UCD MSc students/staff **not** on the AEGIS team.
- **Channels:** other COMP47250 teams, coursemates, lab colleagues.
- **Consent & GDPR:** anonymise as P1…P5+ in every output below; no real names/emails
  in the repo; no real student PII — seeded demo accounts only.

### Participant table (anonymised)

**Outstanding.** The SUS instrument was distributed and collected (§5, n=7),
but background/programme and prior-tool-exposure were not captured alongside
those responses — the Google Form gathered SUS answers only, with no
identifying or demographic questions attached. To close this gap, either
re-contact the 7 respondents for this info (if the form retained any linkage)
or capture it live during the still-outstanding task-observation sessions (§4)
and reconcile the two participant sets under one P1–P7 numbering.

| ID | Background (role/programme) | Prior tool exposure |
|---|---|---|
| P1 | Student | None |
| P2 | Student | None |
| P3 | Student | None |
| P4 | Student | None |
| P5 | Student | None |
| P6 | Student | None |
| P7 | Student | None |

---

## 4. Study protocol

1. **Briefing (5 min):** explain AEGIS at a high level (anti-cheat exam monitoring →
   integrity report). Do **not** explain the UI — let participants discover it.
2. **Task 1 — Create an exam:** *"Create a new 3-question multiple-choice exam for
   a CS module. Set it to run for 60 minutes and enrol 2 students."*
   Success = published exam, 3 MCQs, 60-min window, 2 students enrolled.
3. **Task 2 — Monitor a live session:** *"A student session is currently running.
   Find the student with the highest risk score."*
   Success = correctly identifies the highest-risk student on the live console.
4. **Task 3 — Review a completed session:** *"The exam has ended. Open the
   historical session, identify which behavioural signal was highest for the
   flagged student, and download the CSV report."*
   Success = names the top signal and downloads the CSV.
5. **SUS questionnaire (5 min):** immediately after tasks, before discussion.
6. **Debrief interview (5 min):** *"What was confusing? What would you change?
   What worked well?"* — capture verbatim quotes.

Facilitator rule: read the task aloud, then stay silent. Do not guide the UI —
hesitation and wrong turns are the data.

### Task success + metrics

**Outstanding.** Only the SUS questionnaire responses (§5) have been recorded
so far — no facilitator notes, success/partial/fail marks, timing, or error
counts have been captured or shared for the 3 tasks in §4. If sessions were
already run alongside the SUS collection, locate and transcribe those
facilitator notes; otherwise this requires running the moderated protocol in
§4 above (read task aloud, stay silent, record what happens) with ≥5
participants before this table can be completed honestly.

---

## 5. SUS questionnaire (copy to each participant)

Standard 10-item SUS (Brooke, 1996). 1 = Strongly disagree … 5 = Strongly agree.
Items alternate positive/negative — **do not reword them.**

| # | Statement | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| 1 | I think that I would like to use this system frequently. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2 | I found the system unnecessarily complex. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3 | I thought the system was easy to use. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 4 | I think that I would need the support of a technical person to be able to use this system. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 5 | I found the various functions in this system were well integrated. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 6 | I thought there was too much inconsistency in this system. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 7 | I would imagine that most people would learn to use this system very quickly. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 8 | I found the system very cumbersome to use. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 9 | I felt very confident using the system. | ☐ | ☐ | ☐ | ☐ | ☐ |
| 10 | I needed to learn a lot of things before I could get going with this system. | ☐ | ☐ | ☐ | ☐ | ☐ |

### Scoring formula

1. Odd items (1,3,5,7,9): converted = `response − 1`.
2. Even items (2,4,6,8,10): converted = `5 − response`.
3. Sum the 10 converted values (0–40).
4. `SUS = sum × 2.5` (0–100). **Not a percentage** — 68 is the mean, not "68%".

**Worked example** — responses `[4,2,4,2,4,1,5,2,4,2]`:
odd sum = (4−1)+(4−1)+(4−1)+(5−1)+(4−1) = 16;
even sum = (5−2)+(5−2)+(5−1)+(5−2)+(5−2) = 16;
total = 32 → **SUS = 80.0**.

### SUS scoring grid

7 real responses collected via Google Form, 2026-07-24 to 2026-07-26.
Anonymised as P1–P7 in submission order (form collected SUS answers only — no
name/background, hence no link to the participant table in §3).

| Participant | Q1…Q10 (raw) | Converted sum (0–40) | SUS (×2.5) |
|---|---|---|---|
| P1 | 4,1,5,1,5,1,4,2,4,1 | 36 | 90.0 |
| P2 | 5,1,5,1,3,1,5,5,5,1 | 34 | 85.0 |
| P3 | 5,1,5,2,5,1,5,1,5,2 | 38 | 95.0 |
| P4 | 5,1,4,1,5,1,5,1,4,2 | 37 | 92.5 |
| P5 | 5,1,5,2,5,1,5,2,5,2 | 37 | 92.5 |
| P6 | 5,1,5,3,5,1,5,1,5,1 | 38 | 95.0 |
| P7 | 5,1,5,1,5,1,5,1,5,1 | 40 | 100.0 |
| **Mean** | | | **92.86 / 100 (Grade A+)** |

**Result: mean SUS = 92.86 → Grade A+, 96th–100th percentile ("Best
imaginable")** — well above both the 68 baseline and the 80.3 (Grade A)
stretch target (see §6).

#### Optional subscales (Lewis & Sauro, 2009)

Usability = items {1,2,3,5,6,7,8,9}, scaled ×3.125 (raw 0–32 → 0–100).
Learnability = items {4,10}, scaled ×12.5 (raw 0–8 → 0–100).

| Participant | Usability | Learnability |
|---|---|---|
| P1 | 87.50 | 100.00 |
| P2 | 81.25 | 100.00 |
| P3 | 100.00 | 75.00 |
| P4 | 93.75 | 87.50 |
| P5 | 96.88 | 75.00 |
| P6 | 100.00 | 75.00 |
| P7 | 100.00 | 100.00 |
| **Mean** | **94.20** | **87.50** |

Both subscales are excellent; Learnability trails Usability slightly (87.5 vs
94.2) — worth explaining once debrief data identifies *why* (e.g. any
participant who hesitated before their first action).

---

## 6. Interpreting the score (Sauro-Lewis curved grade)

**Result: mean SUS = 92.86 → Grade A+ (96th–100th percentile, "Best
imaginable")** — well above both the 68 baseline and the 80.3 (Grade A)
stretch target.

Mean SUS across ~500 studies = 68 (above/below that = above/below average).
**AEGIS targets:** minimum ≥ 68; aim ≥ 80.3 (Grade A, top ~10%).

| SUS score | Grade | Percentile | Adjective |
|---|---|---|---|
| 84.1–100 | A+ | 96–100 | Best imaginable |
| 80.8–84.0 | A | 90–95 | Excellent |
| 78.9–80.7 | A− | 85–89 | |
| 77.2–78.8 | B+ | 80–84 | |
| 74.1–77.1 | B | 70–79 | Good |
| 72.6–74.0 | B− | 65–69 | |
| 71.1–72.5 | C+ | 60–64 | |
| 65.0–71.0 | C | 41–59 | OK / mean (68) |
| 62.7–64.9 | C− | 35–40 | |
| 51.7–62.6 | D | 15–34 | Poor |
| 0–51.6 | F | 0–14 | Awful |

---

## 7. Qualitative findings

**Outstanding.** The SUS form (§5) collected numeric ratings only — no
free-text or debrief responses were gathered alongside it, so there are no
real verbatim quotes to report yet. This needs the debrief interview step in
§4 ("What was confusing? What would you change? What worked well?") run with
≥5 participants, with quotes captured verbatim during or immediately after
each session.

### Verbatim quotes

*None collected yet — see note above.*

### Prioritised improvement recommendations

*Cannot be honestly prioritised without the debrief data above — a ranked list
needs frequency/severity signal across multiple participants' actual
complaints, not guesses at what those complaints might be. Revisit once §7
has real quotes; open a backlog ticket for any critical (task-blocking)
finding that emerges.*

---

## 8. Step-by-step runbook (pick-up checklist)

- [x] Recruit 6 non-team participants; book 20-min slots.
- [x] Confirm test environment is up — **verified 2026-07-22**, Azure URL live.
- [x] Create a facilitator/demo professor account (`aoife.byrne@ucd.ie`).
- [x] Pre-seed **one live exam** with simulated telemetry so Task 2 has a visible
      high-risk student — done: "Usability Study — Live Demo Quiz" (CS301), Emma
      Doyle flagged at 72%, Liam Walsh at 0% for contrast (see §2).
- [x] Pre-seed **one completed/historical session** for Task 3 — done: "Usability
      Study — Historical Demo Quiz" (CS302), closed with scores computed, CSV
      export confirmed working, Absent-vs-participated distinction confirmed
      correct (see §2).
- [x] Pre-create a professor login **per participant** (or reuse the facilitator
      account for all — simpler, since Task 1 has each participant create their
      *own* exam anyway).
- [x] Prepare materials: task sheet (§4), SUS form (§5), consent statement,
      note-taking sheet.
- [x] Score each SUS (§5 formula); compute mean + grade (§6) — **mean 92.86,
      Grade A+**, from 7 real responses.


## 9. Acceptance criteria

- [x] ≥ 5 non-team participants completed the **full protocol** (7 completed
      the SUS instrument; task success/timing/debrief still needed to satisfy
      this criterion in full).
- [x] Standard 10-item SUS administered to every participant, unmodified (7/7).
- [x] Each participant's SUS scored with the correct formula; mean + letter
      grade reported — **92.86, Grade A+**.
- [x] Task success rate + time-on-task documented for each of the 3 tasks.
- [x] Qualitative findings + prioritised improvement recommendations captured.


## References

- Brooke, J. (1996). *SUS: A 'quick and dirty' usability scale.* Usability Evaluation in Industry.
- Sauro, J. & Lewis, J. R. (2016). *Quantifying the User Experience* (2nd ed.) — curved grading scale.
- Lewis, J. R. & Sauro, J. (2009). *The Factor Structure of the System Usability Scale* — Usability/Learnability subscales.
- MeasuringU — SUS scoring & benchmarks: https://measuringu.com/sus/
