from datetime import date, datetime, timezone

# Deterministic clock for the demo seed to ensure 100% reproducible data generation
DEMO_REFERENCE_DATE = date(2026, 10, 6)
DEMO_REFERENCE_TIME = datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc)
