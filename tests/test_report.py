# Checks the report math with made-up sessions; no database needed.
# Run: python -m pytest tests/   or   python -m tests.test_report
from datetime import datetime, timedelta, timezone

from report import fmt_duration, summarize


def t(day, hour, minute=0):
    return datetime(2025, 9, day, hour, minute, tzinfo=timezone.utc)


START, END = t(1, 0), t(3, 0)  # report covers Sep 1 and Sep 2


def test_counts_peak_and_time():
    sessions = [
        ("A", t(1, 9), t(1, 10)),      # 1h
        ("B", t(1, 9, 30), t(1, 11)),  # 1.5h, overlaps A -> peak 2
        ("A", t(2, 9), t(2, 9, 30)),   # 0.5h
    ]
    r = summarize(sessions, START, END)
    assert r == {"used": 2, "peak": 2, "total": 3, "total_seconds": 3 * 3600}


def test_back_to_back_is_not_overlap():
    r = summarize([("A", t(1, 9), t(1, 10)), ("B", t(1, 10), t(1, 11))], START, END)
    assert r["peak"] == 1


def test_sessions_clipped_to_range():
    sessions = [
        ("A", START - timedelta(hours=2), t(1, 1)),  # starts before range, 1h inside
        ("B", t(2, 23), END + timedelta(hours=2)),   # 1h inside, ends after range
        ("C", t(3, 5), t(3, 6)),                     # entirely after range: excluded
    ]
    r = summarize(sessions, START, END)
    assert r == {"used": 2, "peak": 1, "total": 2, "total_seconds": 2 * 3600}


def test_empty():
    assert summarize([], START, END) == {"used": 0, "peak": 0, "total": 0, "total_seconds": 0}


def test_duration_format_past_24h():
    assert fmt_duration(11645 * 3600 + 15 * 60 + 15) == "11645:15:15"
    assert fmt_duration(0) == "0:00:00"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("report tests OK")
