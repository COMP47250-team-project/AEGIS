#!/usr/bin/env python3
"""Provision an open exam with N enrolled students for the k6 WebSocket load test.

Registers a professor (exam owner) + N students, creates and opens an exam,
enrols every student, and writes data.json (consumed by load_test.js).

Run with the stack up on localhost:8000:  python3 provision.py
"""
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("BASE", "http://localhost:8000")
WS_BASE = os.environ.get("WS_BASE", "ws://host.docker.internal:8000")
HTTP_BASE = os.environ.get("HTTP_BASE", "http://host.docker.internal:8000")
N = int(os.environ.get("N_STUDENTS", "50"))
N_PROFS = int(os.environ.get("N_PROFS", "2"))
PW = "loadtest123"


def post(path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_status": e.code, "_body": e.read().decode()}


def token_for(email, role, name):
    """Register (or, if already present, log in) and return an access token."""
    r = post("/auth/register", {"email": email, "password": PW, "role": role, "name": name})
    if r.get("access_token"):
        return r["access_token"]
    return post("/auth/login", {"email": email, "password": PW})["access_token"]


prof_token = token_for("loadprof@demo.ac.uk", "professor", "Load Prof")

emails = [f"ls{i}@demo.ac.uk" for i in range(N)]
student_tokens = [token_for(e, "student", f"S{i}") for i, e in enumerate(emails)]

quiz = post("/quizzes", {"title": "Load Test", "duration_minutes": 30}, prof_token)
question = post(
    f"/quizzes/{quiz['id']}/questions", {"type": "short", "prompt": "Q?"}, prof_token
)
post(f"/quizzes/{quiz['id']}/publish", {}, prof_token)
exam = post(
    "/exams",
    {
        "quiz_id": quiz["id"],
        "course_id": "LOAD",
        "scheduled_start": "2026-09-01T09:00:00+00:00",
        "duration_minutes": 60,
    },
    prof_token,
)
exam_id = exam["id"]

for e in emails:
    post(f"/exams/{exam_id}/enroll-by-email", {"email": e}, prof_token)
post(f"/exams/{exam_id}/open", {}, prof_token)

data = {
    "ws_base": WS_BASE,
    "http_base": HTTP_BASE,
    "exam_id": exam_id,
    "question_id": question["id"],
    "students": student_tokens,
    "professors": [prof_token] * N_PROFS,  # all connect as the owning professor
}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
with open(out, "w") as f:
    json.dump(data, f)
print(f"provisioned open exam {exam_id}: {N} students, {N_PROFS} professors -> {out}")
