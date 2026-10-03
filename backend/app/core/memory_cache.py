import threading
import time


_lock = threading.Lock()
_values: dict[str, tuple[float, str]] = {}
_next_allowed: dict[str, float] = {}


def get_cached_value(key: str) -> str | None:
    now = time.monotonic()
    with _lock:
        entry = _values.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= now:
            _values.pop(key, None)
            return None
        return value


def set_cached_value(key: str, value: str, ttl_seconds: int) -> None:
    with _lock:
        _values[key] = (time.monotonic() + max(0, ttl_seconds), value)


def acquire_rate_limit(key: str, interval_seconds: int = 1) -> bool:
    """Pace upstream requests within this API process."""
    now = time.monotonic()
    with _lock:
        next_allowed = _next_allowed.get(key, 0.0)
        if now < next_allowed:
            return False
        _next_allowed[key] = now + interval_seconds
        return True
