# DECISIONS.md

Architectural, technology, and scope decisions made during the AEGIS project.
Each entry records what was decided, why, what was rejected, and what the
decision enables or forecloses. This document satisfies the Technology Stack
Justification rubric criterion and answers Mentor Dominic's June 11 question:
"What research has been done on tech trade-offs?"

---

## D-01: FastAPI over Django or Flask

**Date:** 2026-01-15
**Status:** Accepted

**Decision:** Use FastAPI as the backend web framework.

**Rationale:** AEGIS has two real-time requirements that ruled out synchronous
frameworks: streaming telemetry events from up to 200 concurrent students
during an exam, and pushing live risk summaries to the professor console every
five seconds. Django's ORM and view layer are synchronous by default; adding
async support requires Channels and a separate ASGI layer, which doubles the
operational surface area. Flask has no first-class async or WebSocket support.
FastAPI is built on Starlette, which is ASGI-native, meaning WebSocket handlers
and HTTP endpoints share the same event loop with no adapters. Pydantic v2
integration provides automatic request validation and response serialisation,
which reduced boilerplate significantly for the 15+ request/response schema
pairs in the exam and telemetry routers. The team had prior FastAPI exposure
from coursework, which reduced ramp-up time during the compressed delivery
schedule.

**Alternatives considered:**
- **Django + Django Channels:** Mature ecosystem, but async support is a
  retrofit. Two separate processes (ASGI and WSGI) add deployment complexity
  that is inappropriate for a student team with a fixed Azure credit budget.
- **Flask + Flask-SocketIO:** Flask-SocketIO uses eventlet or gevent for
  concurrency, neither of which integrates cleanly with asyncio-native
  libraries like asyncpg and SQLAlchemy 2.0 async.
- **Node.js/Express:** Would have required the team to split expertise across
  two languages (Python for ML components, JS for backend), increasing
  integration risk.

**Consequences:** Enables native async/await throughout the stack. All database
calls use SQLAlchemy 2.0 async session with asyncpg driver, which means no
thread-pool bridging. WebSocket endpoints are first-class routes. Constrains
the team to Python for all backend work, which is acceptable given the
team's profile.

---

## D-02: React with TypeScript over Vue or Angular

**Date:** 2026-01-15
**Status:** Accepted

**Decision:** Use React with TypeScript for the frontend.

**Rationale:** The professor console receives a live JSON payload every five
seconds containing per-student risk scores across six signal components. The
student exam UI handles real-time WebSocket events with structured payloads
that vary by event type (tab_blur, paste, key_interval, etc.). TypeScript's
structural type system allowed us to define these payload shapes as interfaces
and catch mismatches at compile time rather than at runtime during a live exam.
The telemetry event schema changed three times during development; TypeScript
made those refactors safe. React's component model suited the dashboard layout:
the professor console is a composition of independent student cards that update
independently, which maps naturally to React's re-render model.

**Alternatives considered:**
- **Vue 3 with TypeScript:** Vue's TypeScript integration via `<script setup>`
  is strong, but the team had significantly more React experience. Switching
  would have cost two to three weeks of ramp-up during a twelve-week project.
- **Angular:** Strong TypeScript-first framework, but Angular's opinionated
  structure (modules, decorators, dependency injection) adds ceremony that is
  disproportionate for a focused single-page application. Angular's bundle size
  would also have complicated the initial load time for students on exam day.
- **Plain JavaScript with no framework:** Considered briefly for the student
  exam UI to minimise bundle size. Rejected because managing live WebSocket
  state, answer drafts, and countdown timers without a reactive system
  produces fragile, hard-to-test code.

**Consequences:** TypeScript catches schema mismatches between frontend event
handling and backend payloads at build time. ESLint and Pyright run in CI on
both sides of the stack, providing end-to-end type safety. The team cannot use
JavaScript-only libraries without type stubs, which is an acceptable constraint.

---

## D-03: PostgreSQL over NoSQL databases

**Date:** 2026-01-20
**Status:** Accepted

**Decision:** Use PostgreSQL as the sole database.

**Rationale:** The data model has strong relational structure: a telemetry event
belongs to a student session, which belongs to an exam session, which belongs
to a quiz, which belongs to a course, which belongs to a professor. Every
meaningful query crosses at least two of these joins. A document store would
require either deeply nested documents (making atomic updates across boundaries
difficult) or manual reference management that reimplements what a relational
database does natively. ACID transactions are non-negotiable: a student's
answer submission and their session status update must either both succeed or
both fail. PostgreSQL's JSONB type handles the telemetry payload column, where
each event type has a different schema (tab_blur stores duration_ms, paste
stores text_length, key_interval stores an array of intervals). JSONB supports
GIN indexing for querying inside the payload, and SQLAlchemy's
`JSON().with_variant(JSONB(), "postgresql")` pattern allows the same model to
run on SQLite for tests. UUID as a native column type and `gen_random_uuid()`
as a server-side default removed UUID generation from application code
entirely. TIMESTAMPTZ stores timezone-aware timestamps natively, which is
critical for comparing client_ts (potentially skewed by student clock drift)
against server_ts (authoritative UTC).

**Alternatives considered:**
- **MongoDB:** Flexible schema suits telemetry events, but the exam and scoring
  data is strongly relational. Running MongoDB alongside PostgreSQL for
  telemetry was evaluated and rejected: two databases double the operational
  overhead, backup complexity, and migration surface area.
- **InfluxDB or TimescaleDB:** Purpose-built for time-series data like
  telemetry. Rejected because the primary query pattern is not time-range
  aggregation but per-student per-exam aggregation at scoring time, which is a
  small bounded set of rows. PostgreSQL handles this without performance concern
  at the scale of hundreds of students per exam.
- **DynamoDB:** Managed, scalable, but single-table design requires significant
  upfront modelling expertise. The team's timeline did not allow for that
  investment, and the relational structure of the data makes DynamoDB a poor
  fit.

**Consequences:** ACID guarantees are available throughout. Schema changes are
managed via Alembic migrations with full rollback support. SQLite can substitute
for PostgreSQL in the test suite using SQLAlchemy's dialect abstraction,
enabling CI without a live database. The team cannot store unbounded binary
blobs cheaply, but no such requirement exists in AEGIS.

---

## D-04: Rule-based scorer over machine learning

**Date:** 2026-01-25
**Status:** Accepted

**Decision:** Implement integrity scoring as a weighted rule-based function
with six explicit signal components, deferring ML to Phase 3.

**Rationale:** An ML approach requires labelled training data: examples of
genuine student behaviour and examples of cheating behaviour with ground-truth
labels. No such dataset existed at project start, and collecting one ethically
during the project would require IRB approval, participant consent, and time
the schedule did not allow. A rule-based scorer with published weights is
transparent: a professor can explain to a student exactly why their score is
0.63 (paste events contributed 0.80, tab switches contributed 0.45). An ML
model's decision is not directly explainable without additional tooling. The
rule-based approach also allows per-exam calibration via the three scoring
presets (lenient, standard, strict), which adjust threshold sensitivity without
retraining. The scorer formula is:
`risk = 0.30×tab_switch + 0.25×paste + 0.20×iki + 0.10×first_keypress + 0.10×answer_time + 0.05×resize`.
Weights were informed by the academic literature on keystroke dynamics and
browser-based proctoring (Bixler & D'Mello 2013; Romero et al. 2021).

**Alternatives considered:**
- **Random Forest or Gradient Boosting:** Strong performance on behavioural
  classification tasks in the literature. Rejected for MVP due to absence of
  training data and explainability requirements.
- **Anomaly detection (Isolation Forest, Autoencoder):** Does not require
  labelled cheating data, only normal behaviour. Deferred to Phase 3: the
  student baseline mechanism (StudentBaseline model, computed from pre-exam
  keystrokes) is designed to feed into an anomaly detector once sufficient
  data is collected.
- **LLM-based analysis of answer text:** Evaluated briefly for detecting
  AI-generated short answers. Rejected: falls outside GDPR data minimisation
  scope, and answer content analysis was not in the agreed system boundary.

**Consequences:** Scoring is transparent, reproducible, and explainable.
Weights can be tuned without redeployment via the scoring preset mechanism.
The scorer will miss sophisticated cheating that mimics normal behaviour
patterns. Phase 3 ML work has a clear input contract: the StudentBaseline
and TelemetryEvent tables are designed to support anomaly detection queries.

---

## D-05: Docker Compose for development, Azure for production

**Date:** 2026-02-01
**Status:** Accepted

**Decision:** Use Docker Compose for local development and CI, and Azure
Container Apps with Azure Database for PostgreSQL for production deployment.

**Rationale:** Mentor Dominic's advice in the June 11 session was explicit:
avoid Kubernetes for a student team on a fixed credit budget. Azure Container
Apps (ACA) provides container orchestration, auto-scaling via KEDA, and
WebSocket support without exposing Kubernetes API complexity. The team has
a $500 Azure for Students credit. ACA costs are consumption-based, meaning
idle environments incur minimal charges. Docker Compose in development ensures
the local environment matches production: same PostgreSQL version, same
environment variable structure, same container boundaries. The Dockerfile uses
`alembic upgrade head && uvicorn ...` as the entrypoint, so schema migrations
run automatically on every deployment before the application starts.

**Alternatives considered:**
- **Azure Kubernetes Service (AKS):** Full Kubernetes control, but requires
  cluster management, node pool sizing decisions, and significantly more
  configuration. Inappropriate for a team of four with a twelve-week timeline.
- **Heroku:** Simple deployment, but WebSocket support requires paid dynos and
  Heroku's free tier was retired. Credit budget would not stretch to multiple
  paid dynos.
- **Railway or Render:** Evaluated as simpler alternatives. Rejected because
  the Azure Service Bus integration (D-08) requires Azure-native services, and
  splitting infrastructure across two cloud providers increases complexity.
- **Bare VM on Azure:** Maximum control, but the team would own OS patching,
  TLS termination, and process supervision — operational overhead that is
  disproportionate for the project scope.

**Consequences:** Local development requires Docker Desktop. CI runs the full
test suite against SQLite in memory without a live PostgreSQL instance, which
is fast but requires SQLAlchemy's dialect abstraction to be maintained. Azure
Container Apps limits maximum WebSocket connection duration, which is
acceptable for exam sessions of up to three hours.

---

## D-06: No webcam or microphone capture

**Date:** 2026-02-05
**Status:** Accepted

**Decision:** AEGIS does not capture, transmit, or store video or audio from
student devices.

**Rationale:** Webcam and microphone capture require explicit, informed consent
under GDPR Article 7 and constitute processing of biometric or sensitive
personal data under Article 9 in some interpretations (facial recognition from
video). The legal basis for processing in an exam context is legitimate
interest under Article 6(1)(f), but biometric processing requires explicit
consent or a specific legal basis that Irish third-level institutions may not
have established for automated proctoring. Mentor feedback in the June 11
session reinforced this: "privacy by design, not privacy by compliance." Beyond
legal risk, video-based proctoring has documented bias against students with
darker skin tones (Harber et al. 2021), which conflicts with the project's
equity goals. Behavioural signals from keyboard and browser events provide
sufficient signal for a first-generation integrity tool without these risks.

**Alternatives considered:**
- **Opt-in webcam with face presence detection:** Evaluated as a middle ground.
  Rejected because opt-in in an exam context is not freely given (students may
  feel coerced), which undermines the validity of consent under GDPR.
- **Audio activity detection without recording:** Detecting whether a
  microphone is active (e.g., voice present) without storing audio. Rejected
  because it still requires microphone permission and introduces a new category
  of personal data with unclear legal basis.

**Consequences:** AEGIS cannot detect physical collaboration (student looking
at another screen, speaking answers aloud). This is an accepted limitation
documented in the project scope. The system is privacy-preserving by design
and can be deployed without a Data Protection Impact Assessment specific to
biometric processing.

---

## D-07: Keystroke interval timing only, not key values

**Date:** 2026-02-05
**Status:** Accepted

**Decision:** Telemetry captures the time between keystrokes (inter-keystroke
interval in milliseconds) but never the key values themselves.

**Rationale:** Key values constitute personal data under GDPR: they can reveal
passwords, personal communications, and sensitive content entered in other
browser contexts if the student switches tabs. Even within the exam, capturing
key values would mean storing the student's answer text twice (once in
exam_answers, once in the telemetry stream), which violates the data
minimisation principle under GDPR Article 5(1)(c). The IKI signal — mean
interval, standard deviation, and p90 — provides sufficient discriminating
power between genuine typing and pasted text. Research by Bergadano et al.
(2002) and more recent work on keystroke dynamics authentication confirms that
IKI alone can distinguish users with reasonable accuracy. The StudentBaseline
model stores only mean_keystroke_interval_ms and keystroke_stddev_ms, not any
key sequence information.

**Alternatives considered:**
- **Full keystroke logging (key down/up with key values):** Maximum signal but
  maximum privacy risk. Rejected categorically on GDPR grounds.
- **Key category logging (letter, number, backspace, special):** Partial
  anonymisation that preserves some behavioural signal without exact key
  values. Rejected because the added complexity of categorisation does not
  justify the marginal signal improvement over raw IKI.

**Consequences:** The IKI signal can detect unusually fast typing (consistent
with paste-and-type behaviour) and rhythm discontinuities (consistent with
copying from another source). It cannot detect which specific keys were pressed,
meaning some cheating patterns (e.g., looking up and slowly typing an answer)
are invisible to this signal. This is documented in the scorer's known
limitations.

---

## D-08: Azure Service Bus over Apache Kafka

**Date:** 2026-02-10
**Status:** Accepted

**Decision:** Use Azure Service Bus as the message broker for telemetry event
queuing and score job dispatch.

**Rationale:** Apache Kafka requires cluster management: ZooKeeper (or KRaft),
broker nodes, topic configuration, and consumer group coordination. Running
Kafka on Azure requires either AKS (which D-05 rejected) or Confluent Cloud
(which would consume the majority of the $500 credit budget). Azure Service Bus
is a managed PaaS service that requires no infrastructure management. It
integrates natively with Azure Container Apps via KEDA (Kubernetes Event-Driven
Autoscaling): the scorer worker can scale from zero to N instances based on
queue depth, meaning the service costs nothing when no exam is running. The
Service Bus SDK for Python (`azure-servicebus`) is well-documented and the team
integrated it within two days. Dead-letter queue support is built-in and
configurable without additional infrastructure.

**Alternatives considered:**
- **Apache Kafka (self-managed on AKS):** Maximum throughput and replay
  capability. Rejected due to operational overhead and credit budget
  constraints. Appropriate for a production system processing millions of
  events; inappropriate for a prototype handling hundreds.
- **Redis Streams:** Lightweight, fast, already available as Azure Cache for
  Redis. Evaluated seriously. Rejected because Redis persistence is less
  durable than Service Bus by default, and the dead-letter queue pattern
  required for the scorer retry logic would need to be implemented manually.
- **RabbitMQ:** Mature, well-understood message broker. Rejected for the same
  reasons as Kafka: requires self-hosting or a paid managed service.
- **Direct HTTP from telemetry receiver to scorer:** Simplest possible
  architecture. Rejected because synchronous HTTP from the WebSocket handler
  to the scorer would block the event loop during scoring, violating D-11
  (non-blocking telemetry).

**Consequences:** Score computation is fully decoupled from telemetry ingestion.
The telemetry WebSocket endpoint commits events to PostgreSQL and enqueues a
message to Service Bus without waiting for scoring to complete. The scorer
worker processes batches independently and can be scaled horizontally. In local
development and CI, the Service Bus connection string is set to a placeholder
value and the dispatch is skipped gracefully, enabling full test coverage
without a live Azure connection.

---

## D-09: Azure Container Apps over Azure Kubernetes Service

**Date:** 2026-02-10
**Status:** Accepted

**Decision:** Deploy all production services on Azure Container Apps rather
than managing an AKS cluster.

**Rationale:** This decision was directly influenced by Mentor Dominic's
advice (June 11 session). AKS provides full Kubernetes control but requires
the team to manage cluster upgrades, node pools, pod security policies, ingress
controllers, and certificate management. Azure Container Apps abstracts all
of this: a container image, environment variables, and a scaling rule are
sufficient to deploy a production service. ACA supports WebSocket connections
natively on its HTTP ingress, which was a non-negotiable requirement for the
telemetry gateway. KEDA integration with Azure Service Bus means the scorer
worker scales to zero between exams and scales out automatically when queue
depth increases, which optimises the credit budget. ACA also supports
revision-based deployments, enabling zero-downtime updates by directing traffic
gradually to the new revision.

**Alternatives considered:**
- **AKS:** Full control, but the operational overhead is disproportionate for
  a four-person team with a twelve-week timeline. Appropriate for a production
  system with a dedicated platform engineering team.
- **Azure App Service:** Simpler than ACA, but lacks KEDA integration and
  has more limited WebSocket support (connection timeouts, lack of horizontal
  scaling based on custom metrics).
- **Azure Functions (serverless):** Cost-effective for sporadic workloads.
  Rejected because the telemetry WebSocket handler requires a long-lived
  connection (the duration of the exam), which is incompatible with the
  stateless, short-lived execution model of serverless functions.

**Consequences:** The team has no Kubernetes operational burden. Scaling
behaviour is declarative and automatic. The system cannot be deployed to
non-Azure infrastructure without replacing the KEDA scaling rules and
Service Bus integration. This creates vendor lock-in that is acceptable for
an academic prototype but would need to be addressed in a production system.

---

## D-10: Three scoring presets over continuous weight sliders

**Date:** 2026-03-18
**Status:** Accepted

**Decision:** Expose scoring sensitivity to professors via three named presets
(Lenient, Standard, Strict) rather than allowing continuous adjustment of
individual signal weights.

**Rationale:** Mentor Siddharth's feedback in the June 18 session identified
a specific risk with continuous weight configuration: if professors can adjust
weights after seeing results, the system can be used to reverse-engineer which
behaviours trigger flags, and students can be coached to avoid them. Three
named presets with fixed, non-visible weights prevent this. The preset names
communicate intent (Lenient is appropriate for open-book assessments, Strict
for closed-book high-stakes exams) without exposing the underlying signal
weights. From a UX perspective, a slider interface for six weights with
interdependencies is cognitively demanding and likely to produce misconfigured
exams. Three options are a decision, not a tuning exercise.

**Alternatives considered:**
- **Single global threshold (flag if score >= X):** Simpler. Rejected because
  the threshold alone does not capture the professor's intent about which
  signals matter for a given exam type.
- **Per-signal weight sliders:** Maximum flexibility. Rejected on mentor
  feedback: gaming risk and UX complexity outweigh the flexibility benefit.
- **No configuration at all (fixed weights only):** Simplest. Rejected because
  different exam types legitimately warrant different sensitivity. An open-book
  exam where students are expected to reference materials should tolerate more
  tab-switching than a closed-book exam.

**Consequences:** Professors cannot fine-tune scoring beyond three levels.
The scoring preset is stored on the ExamSession row and passed to the scorer
at exam close. Adding a fourth preset in future is a backward-compatible
change. The weights behind each preset are not exposed via any API endpoint,
preventing reverse-engineering.

---

## D-11: Non-blocking telemetry pipeline

**Date:** 2026-03-01
**Status:** Accepted

**Decision:** Telemetry collection failures must never cause exam answer loss
or block the student exam experience.

**Rationale:** This is a core design principle rather than a technology choice,
but it has pervasive architectural consequences. A student's answer submission
(`POST /exams/{id}/answers`) commits to PostgreSQL before any side effects.
The telemetry WebSocket handler catches and logs exceptions without propagating
them to the student. The live monitor (in-memory, per-process) and the Service
Bus dispatch are both best-effort: if either fails, the telemetry event is
logged but the student's exam continues unaffected. This principle was
established after the team observed that a WebSocket disconnection during
early testing caused the student UI to display an error state, which is
unacceptable during a live exam. The exam answer endpoint explicitly documents:
"This endpoint MUST NOT fail due to WebSocket or Service Bus unavailability."

**Alternatives considered:**
- **Synchronous telemetry (block answer submission until telemetry is
  confirmed):** Provides strong consistency between answers and telemetry.
  Rejected because a Service Bus timeout (which can be several seconds) would
  block the student from saving their answer, risking data loss if they
  navigate away.
- **Client-side telemetry buffering with retry:** The browser SDK buffers
  events and retries on reconnection. This is implemented, but the server-side
  non-blocking guarantee remains necessary because buffer contents may be lost
  if the student closes the browser.

**Consequences:** There is a class of failure mode where answers are saved but
telemetry events are not. In this case, the student's submission is preserved
(correct outcome) but their integrity score will be based on incomplete
telemetry (acceptable outcome — the scorer treats missing data conservatively).
The scorer is never called synchronously from the answer submission path.

---

## D-12: Metadata-only telemetry collection under GDPR

**Date:** 2026-02-05
**Status:** Accepted

**Decision:** AEGIS collects only behavioural metadata (event types and
timing) and never clipboard content, screen content, or keypress values.

**Rationale:** GDPR Article 5(1)(c) requires that personal data be adequate,
relevant, and limited to what is necessary for the purpose (data minimisation).
The purpose of AEGIS is to detect behavioural anomalies during exams, not to
reconstruct what the student did. Tab-switch events record duration, not which
site was visited. Paste events record the length of pasted text, not its
content. Keystroke events record timing intervals, not which keys were pressed
(see D-07). The legal basis for processing is legitimate interest under GDPR
Article 6(1)(f): the institution has a legitimate interest in academic
integrity that is not overridden by the student's privacy interests, given that
(a) the processing is limited to metadata, (b) the student is informed and
provides consent (recorded in the student_sessions.consent_at column), and
(c) the data is used only for integrity assessment, not profiling. The GDPR
consent screen is mandatory before any telemetry is captured; the
`GET /exams/{id}/questions` endpoint returns 403 if consent_at is null.

**Alternatives considered:**
- **Screen capture (periodic screenshots):** High signal for detecting
  off-screen resources. Rejected: constitutes processing of potentially
  sensitive personal data visible on screen, requires explicit consent, and
  the technical implementation (canvas capture) is blocked by browser security
  policies for cross-origin content.
- **Clipboard monitoring (reading clipboard content on paste):** Would reveal
  the exact text pasted. Rejected on GDPR data minimisation grounds and because
  the Clipboard API requires explicit user permission in modern browsers.
- **Full browser history during exam:** Would reveal which sites were visited
  during tab switches. Rejected: clearly disproportionate to the legitimate
  interest basis and likely to constitute profiling under GDPR Article 4(4).

**Consequences:** AEGIS cannot produce evidence of what a student copied from
an external source, only that a paste event occurred. This is intentional:
the system flags for human review, it does not make determinations. A professor
reviewing a flagged student sees that 143 characters were pasted at a specific
time, not what those characters were. All collected metadata is scoped to the
exam session and can be deleted on request under GDPR Article 17.

---

*Last updated: 2026-07-12*
*Maintained by the AEGIS team. New decisions follow the same format and are
numbered sequentially. Superseded decisions retain their entry with a
cross-reference to the superseding decision.*