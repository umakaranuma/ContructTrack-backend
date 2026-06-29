"""Attendance helpers shared by owner dashboard and mobile APIs."""


def resolve_attendance_rate(worker, record):
    """Per-day rate from attendance form, or worker's roster (creation) rate."""
    raw = record.get('daily_rate_lkr')
    if raw is not None and raw != '':
        try:
            rate = float(raw)
            if rate > 0:
                return rate
        except (TypeError, ValueError):
            pass
    return float(worker.daily_rate_lkr)
