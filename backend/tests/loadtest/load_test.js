// k6 WebSocket load test: 50 student connections + 2 professor subscribers.
// Each student sends 1 telemetry event/sec for 120s (keystroke/tab_blur/paste
// mix) then disconnects; professors count live broadcasts.
//
//   1. stack up on localhost:8000
//   2. python3 provision.py            (writes data.json)
//   3. docker run --rm -v "$PWD:/ld" grafana/k6 run /ld/load_test.js
import ws from "k6/ws";
import { check } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const data = JSON.parse(open("./data.json"));

const connectOk = new Rate("ws_connect_success");
const eventsSent = new Counter("events_sent");
const profBroadcasts = new Counter("prof_broadcasts");
const connectMs = new Trend("ws_connect_ms", true);

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
    checks: ["rate==1.0"], // zero failed upgrades
  },
};

const TYPES = ["key_interval", "tab_blur", "paste"];
function frame(i) {
  const type = TYPES[i % 3];
  const payload =
    type === "key_interval"
      ? { interval_ms: 80 + (i % 200) }
      : type === "paste"
        ? { question_id: "q1", char_count: 50 }
        : { reason: "window_blur" };
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
