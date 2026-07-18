from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from sales.models import Sale


# USE_TZ=False project-wide — naive local time only, matching every other app.
def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


class MLClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def predict_all(self):
        response = httpx.get(f"{self.base_url}/predict_all/", timeout=10)
        response.raise_for_status()
        data = response.json()
        # v1 returns {"predictions": [...]}, v2 returns a bare [...] — normalize both to a list.
        return data["predictions"] if isinstance(data, dict) else data


def _order_dates_by_customer():
    """{customer_name: sorted list of distinct order dates}, excluding "Guest" (the
    shared walk-in placeholder — not a real individual). A set collapses same-day
    multiple orders into one "visit" before intervals are computed — two items
    bought the same day isn't a same-day return."""
    rows = (
        Sale.objects.exclude(customer_name="Guest")
        .exclude(customer_name="")
        .order_by("customer_name", "date_created")
        .values_list("customer_name", "date_created")
    )
    by_customer = {}
    for name, dt in rows:
        by_customer.setdefault(name, set()).add(dt.date())
    return {name: sorted(date_set) for name, date_set in by_customer.items()}


def _predict_next(known_dates):
    """The v1 algorithm itself: last known date + the average gap between all known
    dates. Shared by compute_v1_predictions() (using everything known so far) and
    backtest_v1_model() (using only the dates before each held-out order)."""
    intervals = [(known_dates[i] - known_dates[i - 1]).days for i in range(1, len(known_dates))]
    avg_interval = round(sum(intervals) / len(intervals))
    return known_dates[-1] + timedelta(days=avg_interval), avg_interval


def _categorize(next_refill_date, predicted_days_interval, today):
    """Classifies a customer relative to their OWN typical order rhythm, not a fixed
    day count — this business has customers who reorder every 2 days sitting right
    next to ones who reorder every 8 months, so a fixed "60 days = churned" threshold
    would be meaningless for either end of that range. `ratio` is how many of the
    customer's own predicted intervals have elapsed since their predicted return
    date: <0 hasn't reached it yet, 0-1 is on schedule, 1-2 missed one cycle, 2+
    missed two or more — very likely lost."""
    ratio = (today - next_refill_date).days / predicted_days_interval
    if ratio >= 2:
        return "Churned", "danger"
    if ratio >= 1:
        return "Overdue", "warning"
    if ratio >= 0:
        return "Due Now", "success"
    return "Upcoming", "info"


def compute_v1_predictions():
    """v1 predictor — a statistical baseline computed directly from this app's own
    Sale history, no external ML service involved. For every customer with at least
    two distinct order dates, predicts their next order date as their last order
    date plus the average number of days between their past orders, and classifies
    them (see _categorize()) — including whether they look churned.

    Every sale counts regardless of status — a placed order is the recency/frequency
    signal here, not whether it was ultimately paid."""
    today = _today()
    predictions = []
    for name, dates in _order_dates_by_customer().items():
        if len(dates) < 2:
            continue
        next_date, avg_interval = _predict_next(dates)
        category, category_tone = _categorize(next_date, avg_interval, today)
        predictions.append({
            "customer_name": name,
            "last_refill_date": dates[-1],
            "predicted_days_interval": avg_interval,
            "next_refill_date": next_date,
            "category": category,
            "category_tone": category_tone,
        })

    predictions.sort(key=lambda p: p["next_refill_date"])
    return predictions


def backtest_v1_model():
    """Scores the v1 algorithm against what customers actually did: for every order
    beyond a customer's 2nd, predicts it using only the orders that came BEFORE it
    (the exact same algorithm as compute_v1_predictions(), just run against a past
    point in time), then compares that prediction to the order date that actually
    happened. Aggregated across every customer's full history — a genuine backtest,
    not a comparison against today's still-pending live predictions (which haven't
    happened yet, so there's nothing to score them against).

    Returns None if there isn't at least one customer with 3+ orders yet (need 2 to
    predict a 3rd from)."""
    errors = []
    for dates in _order_dates_by_customer().values():
        for i in range(2, len(dates)):
            predicted_date, _ = _predict_next(dates[:i])
            actual_date = dates[i]
            errors.append(abs((predicted_date - actual_date).days))

    if not errors:
        return None

    within_3_days = sum(1 for e in errors if e <= 3)
    return {
        "sample_count": len(errors),
        "mean_absolute_error_days": round(sum(errors) / len(errors), 1),
        "accuracy_within_3_days_pct": round(within_3_days / len(errors) * 100, 1),
    }
