"""Usage report in the TDX / AllSight format: Computers, Peak, Total, Total Time, Date Range.

Usage (run on the server, from the repo root):
    python report.py 2025-08-20 2025-12-15
    python report.py 2025-08-20 2025-12-15 --devices ZWXTTCY5GW,ZM3296Y9XH

Dates are local and inclusive. Output is tab-separated so it pastes straight into Excel.
Only completed sessions (st_sessions_history) count; a session still open is not in the report yet.
"""
import argparse
from datetime import date, datetime, time, timedelta


def summarize(sessions, start, end):
    """sessions: iterable of (device_id, start_time, end_time). Each is clipped to [start, end)."""
    clipped = [(d, max(s, start), min(e, end)) for d, s, e in sessions if s < end and e > start]

    # Peak concurrent sessions: +1 at each start, -1 at each end, keep the running max.
    # (t, -1) sorts before (t, 1), so a session ending exactly as another starts isn't an overlap.
    events = sorted([(s, 1) for _, s, _ in clipped] + [(e, -1) for _, _, e in clipped])
    peak = current = 0
    for _, step in events:
        current += step
        peak = max(peak, current)

    return {
        "used": len({d for d, _, _ in clipped}),
        "peak": peak,
        "total": len(clipped),
        "total_seconds": int(sum((e - s).total_seconds() for _, s, e in clipped)),
    }


def fmt_duration(seconds):
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{secs:02}"  # hours run past 24, e.g. 11645:15:15


def fmt_date(d):
    return f"{d.month}/{d.day}/{d:%y}"


def main():
    parser = argparse.ArgumentParser(description="Sentinel usage report")
    parser.add_argument("start", type=date.fromisoformat, help="first day, YYYY-MM-DD")
    parser.add_argument("end", type=date.fromisoformat, help="last day (inclusive), YYYY-MM-DD")
    parser.add_argument("--devices", help="comma-separated serials; omit for every registered device")
    args = parser.parse_args()

    # Local midnight at both ends; astimezone() picks the right UTC offset for each date (DST-safe).
    start = datetime.combine(args.start, time()).astimezone()
    end = datetime.combine(args.end + timedelta(days=1), time()).astimezone()
    devices = [d.strip() for d in args.devices.split(",") if d.strip()] if args.devices else None

    from sqlalchemy import text  # imported here so the test runs without a database
    from app.database import engine

    sql = ("SELECT st_device_id, st_start_time, st_end_time FROM st_sessions_history "
           "WHERE st_start_time < :end AND st_end_time > :start")
    params = {"start": start, "end": end}
    if devices:
        sql += " AND st_device_id = ANY(:devices)"
        params["devices"] = devices

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).all()
        computers = len(devices) if devices else conn.execute(
            text("SELECT COUNT(*) FROM st_devices")).scalar()

    r = summarize(rows, start, end)
    print("Computers\tPeak\tTotal\tTotal Time\tDate Range")
    print(f"{computers}\t{r['peak']}\t{r['total']}\t{fmt_duration(r['total_seconds'])}\t"
          f"{fmt_date(args.start)} - {fmt_date(args.end)}")
    if r["used"] < computers:
        print(f"\n{computers - r['used']} of {computers} computers had no sessions in this range.")


if __name__ == "__main__":
    main()
