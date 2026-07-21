// k6 WebSocket load test. Student count / professor count come from data.json,
// so the same script runs Scenario A (50 students, 2 profs) and Scenario B
// (100 students, 3 profs), just re-run provision.py with different env first.
//
// Each student: upgrade to /ws/exam, send 1 event/sec for 120s (weighted mix),
// submit answers via REST at T+60s, disconnect at T+120s.
//
//   docker run --rm -v "$PWD:/ld" grafana/k6 run /ld/load_test.js
import ws from "k6/ws";
import http from "k6/http";
import { check } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const data = JSON.parse(open("./data.json"));

const connectOk = new Rate("ws_connect_success");
const eventsSent = new Counter("events_sent");
const profBroadcasts = new Counter("prof_broadcasts");
const connectMs = new Trend("ws_connect_ms", true);
const restAnswerMs = new Trend("rest_answer_ms", true);

export const options = {
  scenarios: {
    students: {
      executor: "per-vu-iterations",
      exec: "student",
      vus: data.students.length,
      iterations: 1,
      maxDuration: "140s",
    },
    professors: {
      executor: "per-vu-iterations",
      exec: "professor",
      vus: data.professors.length,
      iterations: 1,
      maxDuration: "140s",
    },
  },
  thresholds: {
    ws_connect_success: ["rate==1.0"], // 100% connection success
    ws_connect_ms: ["p(95)<5000"], // all established within 5s
    rest_answer_ms: ["p(99)<800"], // REST answer p99 <= 800ms
    checks: ["rate>0.99"],
  },
};

// Event mix: 40% key_interval, 30% tab_hidden/tab_shown, 20% paste, 10% window_resized.
function frame(i) {
  const r = i % 10;
  let type;
  if (r < 4) type = "key_interval";
  else if (r < 7) type = i % 2 === 0 ? "tab_hidden" : "tab_shown";
  else if (r < 9) type = "paste";
  else type = "window_resized";

  let payload = {};
  if (type === "key_interval") payload = { interval_ms: 80 + (i % 200) };
  else if (type === "paste") payload = { question_id: "q1", char_count: 50 };
  else if (type === "window_resized") payload = { width: 1024, height: 768 };

  return JSON.stringify({ type, sessionId: `s${__VU}`, clientTs: Date.now(), payload });
}

export function student() {
  const token = data.students[(__VU - 1) % data.students.length];
  const url = `${data.ws_base}/ws/exam/${data.exam_id}?token=${token}`;
  const t0 = Date.now();
  const res = ws.connect(url, {}, function (socket) {
    socket.on("open", () => {
      connectMs.add(Date.now() - t0);
      connectOk.add(true);
      let i = 0;
      let sending = true;
      socket.setInterval(() => {
        if (sending) {
          socket.send(frame(i++));
          eventsSent.add(1);
        }
      }, 1000);

      // REST answer submission at T+60s
      socket.setTimeout(() => {
        const r = http.post(
          `${data.http_base}/exams/${data.exam_id}/answers`,
          JSON.stringify({
            answers: [{ question_id: data.question_id, answer: "load-test answer" }],
          }),
          {
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
          }
        );
        restAnswerMs.add(r.timings.duration);
        check(r, { "answer saved (200)": (x) => x.status === 200 });
      }, 60000);

      socket.setTimeout(() => {
        sending = false;
        socket.close(); // graceful disconnect at T+120s
      }, 120000);
    });
    socket.on("error", () => connectOk.add(false));
  });
  check(res, { "student ws upgraded (101)": (r) => r && r.status === 101 });
}

export function professor() {
  const token = data.professors[(__VU - 1) % data.professors.length];
  const url = `${data.ws_base}/ws/professor/${data.exam_id}?token=${token}`;
  const res = ws.connect(url, {}, function (socket) {
    socket.on("open", () => connectOk.add(true));
    socket.on("message", () => profBroadcasts.add(1));
    socket.setTimeout(() => socket.close(), 122000);
  });
  check(res, { "professor ws upgraded (101)": (r) => r && r.status === 101 });
}
