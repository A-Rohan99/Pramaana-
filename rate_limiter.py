"""
In-memory per-user rate limiter.

Good enough for a hackathon demo (single process, doesn't survive a
restart). If this ever goes past demo stage, swap the dict for Redis --
the interface below stays identical.
"""

import time
from collections import defaultdict

WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 3

_request_log: dict[int, list[float]] = defaultdict(list)


def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    window_start = now - WINDOW_SECONDS

    # Drop timestamps outside the current window.
    _request_log[user_id] = [t for t in _request_log[user_id] if t > window_start]

    if len(_request_log[user_id]) >= MAX_REQUESTS_PER_WINDOW:
        return True

    _request_log[user_id].append(now)
    return False
