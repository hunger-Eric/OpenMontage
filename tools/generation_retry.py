"""Transport retry helpers, without provider selection or approval policy."""
import math
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone


def retry_delay(response):
    """Respect Retry-After (seconds or HTTP date); use backoff when absent."""
    value = getattr(response, "headers", {}).get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    # Long provider pauses should wait, never retry early because of a local cap.
    return max(0, seconds) if math.isfinite(seconds) else None
