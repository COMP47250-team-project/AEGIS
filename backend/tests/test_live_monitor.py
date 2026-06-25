"""Tests for the in-memory live monitor behind the professor dashboard.

Student frames update the aggregates; the professor reads snapshots. We check
aggregation, the 60s active window, and that the live risk score matches the
DB scorer (so the live number and the final report agree).
"""

from app.services.live_monitor import ACTIVE_WINDOW_S, LiveMonitor
from app.services.scorer import compute_risk_score
from app.services.scoring import Event
from app.services.scoring.components.paste import paste_score
from app.services.scoring.components.tab_blur import tab_blur_score

EXAM = "exam-1"


def test_ten_active_students_all_appear_in_one_snapshot():
    monitor = LiveMonitor()
    for i in range(10):
        monitor.record_event(EXAM, f"s{i}", "tab_blur", {}, name=f"Name{i}", now=100.0)

    snap = monitor.snapshot(EXAM, now=100.0)
    assert snap["exam_id"] == EXAM
    assert len(snap["students"]) == 10
    assert all(s["active"] for s in snap["students"])
    assert {s["student_id"] for s in snap["students"]} == {f"s{i}" for i in range(10)}


def test_counts_name_and_last_event_tracked():
    monitor = LiveMonitor()
    monitor.record_event(EXAM, "s1", "tab_blur", {}, name="Alice", now=1.0)
    monitor.record_event(EXAM, "s1", "tab_blur", {}, now=2.0)
    monitor.record_event(EXAM, "s1", "paste", {"char_count": 12}, now=3.0)

    student = monitor.snapshot(EXAM, now=3.0)["students"][0]
    assert student["name"] == "Alice"
    assert student["tab_blurs"] == 2
    assert student["pastes"] == 1
    assert student["last_event"] == "paste"


def test_live_risk_matches_db_scorer():
    monitor = LiveMonitor()
    for _ in range(3):
        monitor.record_event(EXAM, "s1", "tab_blur", {}, now=1.0)
    for _ in range(3):
        monitor.record_event(EXAM, "s1", "paste", {"question_id": "q1"}, now=1.0)

    # The live tab/paste scores must come from the same component functions the
    # DB scorer uses, so the live number and the final report agree.
    events = [Event("tab_blur", {})] * 3 + [Event("paste", {"question_id": "q1"})] * 3
    expected = round(
        compute_risk_score(
            {
                "tab_switch": tab_blur_score(events),
                "paste": paste_score(events),
                "iki": 0.0,
                "first_keypress": 0.0,
                "answer_time": 0.0,
                "resize": 0.0,
            }
        ),
        3,
    )
    student = monitor.snapshot(EXAM, now=1.0)["students"][0]
    assert student["risk_score"] == expected
    assert student["integrity_score"] == expected  # back-compat alias


def test_student_inactive_after_60_seconds():
    monitor = LiveMonitor()
    monitor.record_event(EXAM, "s1", "tab_blur", {}, now=100.0)

    at_boundary = monitor.snapshot(EXAM, now=100.0 + ACTIVE_WINDOW_S)["students"][0]
    assert at_boundary["active"] is True

    past_boundary = monitor.snapshot(EXAM, now=100.0 + ACTIVE_WINDOW_S + 0.1)["students"][0]
    assert past_boundary["active"] is False


def test_seeded_student_with_no_events_is_inactive():
    monitor = LiveMonitor()
    monitor.seed_student(EXAM, "s1", "Bob")

    student = monitor.snapshot(EXAM, now=100.0)["students"][0]
    assert student["name"] == "Bob"
    assert student["active"] is False
    assert student["tab_blurs"] == 0
    assert student["last_event"] is None


def test_unknown_exam_snapshot_is_empty():
    monitor = LiveMonitor()
    assert monitor.snapshot("missing", now=1.0) == {"exam_id": "missing", "students": []}


def test_email_and_keystroke_score_in_snapshot():
    monitor = LiveMonitor()
    # 100ms mean interval -> iki component (400 - 100) / 400 = 0.75
    monitor.record_event(
        EXAM,
        "s1",
        "key_interval",
        {"interval_ms": 100},
        name="Alice",
        email="alice@ucd.ie",
        now=1.0,
    )

    student = monitor.snapshot(EXAM, now=1.0)["students"][0]
    assert student["email"] == "alice@ucd.ie"
    assert student["keystroke_score"] == 0.75


def test_seeded_student_carries_email():
    monitor = LiveMonitor()
    monitor.seed_student(EXAM, "s1", "Bob", "bob@ucd.ie")

    student = monitor.snapshot(EXAM, now=1.0)["students"][0]
    assert student["email"] == "bob@ucd.ie"
    assert student["keystroke_score"] == 0.0
