<div align="center">
  <img src="images/aegis-logo.png" alt="AEGIS" width="110" />
  <h1>AEGIS screenshots</h1>
  <p>A walkthrough of the running system, in the order a professor and a student actually meet it.</p>
</div>

Every image was captured from a working deployment. Student names, emails and courses are seeded demo data, not real people. Risk percentages shown are whatever the scorer computed for that seeded session, so they vary between captures.

This gallery is kept out of the root README on purpose. Loading thirty PNGs on the repository landing page is slow, and most people arriving there want the setup instructions first.

## Contents

- [Accounts and access](#accounts-and-access)
- [Authoring an exam](#authoring-an-exam)
- [Enrolling students](#enrolling-students)
- [Sitting the exam](#sitting-the-exam)
- [Watching a live exam](#watching-a-live-exam)
- [Reviewing integrity after the exam](#reviewing-integrity-after-the-exam)
- [Grading and the AI copilot](#grading-and-the-ai-copilot)
- [What the student sees afterwards](#what-the-student-sees-afterwards)
- [Architecture and data model](#architecture-and-data-model)
- [Azure environment](#azure-environment)
- [Project tracking](#project-tracking)

---

## Accounts and access

### Sign in

One login page for all three roles. The route guard reads the role off the session and sends students to their exam list, professors to the console, and super admins to the admin console.

![AEGIS login page](images/AEGISLoginPage.png)

### Password reset email

Reset links are delivered through Azure Communication Services. The token is stored as a SHA-256 hash, so the raw value in the email is the only copy. When no ACS connection string is configured, the same email is printed to stdout instead, which is what happens on a local Docker Compose stack.

![Password reset email](images/PasswordResetEmail.png)

---

## Authoring an exam

### Professor console

The console is a single page with six tabs: live sessions, exams, quiz builder, scheduler, groups, and history. Active sessions refresh every 30 seconds.

![Professor console home page](images/ProfessorConsoleHomePage.png)

### Quiz builder

Multiple-choice and short-answer questions, with a question bank that pulls questions out of quizzes the professor has already published.

![Professor quiz creation screen](images/ProfessorQuizCreationScreen.png)

### Scheduling

A quiz becomes an exam when it gets a course, a start time, and a duration. This is also where the professor picks the scoring preset (Strict, Standard, or Lenient) and turns on open-book mode with an allowlist of resources. The weights behind each preset stay on the server, so a student cannot read the scoring rules out of the frontend.

![Professor exam scheduling screen](images/ProfessorExamSchedulingScreen.png)

---

## Enrolling students

### Enrolling individuals

Enrol by picking students from the roster, or by pasting a list of email addresses. Unknown addresses come back with a reason rather than failing the whole batch.

![Professor enrolling students for an exam](images/ProfessorEnrollingStudentsForExam.png)

### Student groups

A named group of students can be enrolled into an exam in one call, which saves re-pasting the same tutorial group every week.

![Professor creating a student group](images/ProfessorCreatingStudentGroups.png)

![Professor managing several student groups](images/ProfessorCreatingMultipleStudentGroups.png)

---

## Sitting the exam

### Consent gate

The exam will not hand over questions until the student has consented. The server checks this on every request for the question list and returns 403 while consent is missing, so the gate cannot be skipped by manipulating the frontend. The notice states exactly what is collected: keystroke timing but not key values, tab switching, paste events but not clipboard contents, and window size changes.

![Student GDPR consent notice](images/StudentGDPRNotice.png)

### Exam shell

Question navigation, a countdown, autosave every five seconds, and a submit confirmation. Answers save independently of telemetry, so a dropped WebSocket cannot cost the student their work.

![Student exam screen](images/StudentExamScreen.png)

### Open-book exams

When open-book mode is on, allowlisted PDFs and links appear in a side panel. Uploads are capped at 20 MB and restricted to PDF. Each open and close is recorded with a duration, so the professor can see which resources were used and for how long. Recording is best-effort: if the tracking call fails, the student keeps reading.

![Student exam screen with an embedded PDF](images/StudentExamScreenWithPDF.png)

### Monitored actions are visible to the student

Nothing is hidden. Leaving the window or dropping out of fullscreen produces a banner that says the action was recorded. The banner is informational and never blocks the student.

![Student who has left fullscreen to open an online resource](images/CheatingStudentWithOnlineResource.png)

---

## Watching a live exam

### Live monitor

Students appear with a provisional risk estimate, sorted so the highest sit at the top. The professor socket pushes a snapshot every five seconds from in-memory counters, so the live view costs no database queries per tick. A student who sends nothing for 60 seconds is treated as gone.

![Professor viewing the live monitor](images/ProfessorViewingLiveMonitor.png)

### Live event timeline

Drilling into one student shows their events as they arrive, with a severity tag per event type. Paste and tab-blur are high, keystroke intervals are medium, resize and first-keypress are low.

![Professor viewing a live event timeline](images/ProfessorViewingLiveEventTimeline.png)

---

## Reviewing integrity after the exam

### Exam history

Closed exams, each with the number of flagged students and a per-exam CSV export.

![Professor exam integrity history screen](images/ProfessorExamIntegrityHistoryScreen.png)

### Signal breakdown and event timeline

The final score is recomputed at close over the whole session, against the student's own typing baseline. The breakdown shows all six sub-scores, so a professor can see whether a number came from one loud signal or several quiet ones.

![Professor viewing a student integrity timeline](images/ProfessorViewingStudentIntegrityTimeline.png)

Students who never joined are shown as absent rather than as a suspicious zero.

![Per-student event timeline with signal breakdown](images/StudentEventTimeline.png)

---

## Grading and the AI copilot

### Manual grading

Multiple-choice answers are scored on submit. Short answers are graded by the professor, and results stay hidden from students until grades are explicitly released.

![Professor grade evaluation screen](images/ProfessorGradeEvaluationScreen.png)

### Grade suggestions

The copilot scores each short answer against the model answer and an optional rubric, returning a score, a one-line reason, and a confidence value. It writes nothing. The professor accepts a suggestion or types their own number, then saves.

![AI suggestions for manual grading](images/AISuggestionsForManualGrading.png)

### Integrity brief

A short plain-English summary of one student's behaviour, generated from the six sub-scores and event counts only. No keystroke timings, clipboard data, or answer text is sent to the model. Every brief ends with a fixed sentence saying it is not a verdict.

![AI integrity brief above the event timeline](images/AIIntegrityEventTimeline.png)

### Collusion detection

Answers are embedded and compared pairwise within each question, skipping anything under 20 characters. Pairs above the threshold (0.92 by default) are listed with their similarity. The disclaimer is part of the feature, not decoration: two students can write near-identical correct answers to a factual question.

![AI collusion detection tab](images/AICollusionDetection.png)

---

## What the student sees afterwards

### Exam list

Past exams show either a link to results or a "results pending" state, depending on whether the professor has released grades.

![Student exam list with released and pending results](images/StudentResultsWithExams.png)

### Results

Total score across multiple-choice and manually graded short answers, a per-question review, and the student's own integrity score. Students see the same number the professor sees.

![Student results page](images/StudentResultsPage.png)

---

## Architecture and data model

### System architecture

![AEGIS architecture diagram](images/ArchitectureDiagram.png)

### Azure topology

![Azure architecture diagram](images/AzureArchitectureMermaidDiagram.png)

### Database schema

Eighteen tables across users and courses, quizzes and questions, exam sessions and enrolments, answers, telemetry events, per-student typing baselines, session scores, risk flags, groups, open-book resources and access records, an append-only audit log, and password reset tokens.

![Entity relationship diagram](images/ERDiagram.png)

---

## Azure environment

### Resource group

Container Apps for the backend and frontend, PostgreSQL Flexible Server, Service Bus, Blob Storage, Communication Services, Key Vault, and a container registry, all in one resource group under a monthly budget with email alerts.

![Azure portal home page for the AEGIS resource group](images/AzureHomePage.png)

### Exported template

The deployed environment exported back out as ARM, which is a useful sanity check that the Bicep definitions and the live resources have not drifted apart.

![Exported ARM template of the AEGIS environment](images/AzureExportedTemplate.png)

---

## Project tracking

Work was tracked as Jira issues on the AEGIS board, one branch and pull request per ticket.

![Jira board for the AEGIS project](images/JiraBoard.png)
