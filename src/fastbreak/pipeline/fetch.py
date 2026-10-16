import hashlib
import json
import random
import time
from pathlib import Path

import requests

# nba_api doesn't raise on a bad HTTP status: a blocked or failed request comes back
# as an error page, which only fails when parsed as JSON (ValueError).
RETRYABLE = (requests.exceptions.RequestException, ValueError)


class FetchError(Exception):
    """Raised when a call still fails after every retry."""


class Fetcher:
    """Calls NBA.com politely: waits between calls, retries failures, caches results."""

    def __init__(
        self, cache_dir, min_gap=1.0, max_attempts=5, sleep=time.sleep, clock=time.monotonic
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_gap = min_gap
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.clock = clock
        self._last_call = float("-inf")  # so the first call never waits

    def get(self, endpoint_cls, refresh=False, **params):
        """Return the endpoint's data, from the cache if it's there, otherwise from NBA.com."""
        path = self._cache_path(endpoint_cls, params)
        if path.exists() and not refresh:
            return json.loads(path.read_text())
        data = self._call_with_retries(endpoint_cls, params)
        self._write_cache(path, data)  # only reached on success, so errors are never cached
        return data

    def _cache_path(self, endpoint_cls, params):
        """The same endpoint and parameters always map to the same file."""
        key = json.dumps(params, sort_keys=True)
        digest = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{endpoint_cls.__name__}-{digest}.json"

    def _wait_for_gap(self):
        """Sleep until at least min_gap seconds have passed since the last call."""
        wait = self.min_gap - (self.clock() - self._last_call)
        if wait > 0:
            self.sleep(wait)

    def _call_with_retries(self, endpoint_cls, params):
        """Call the endpoint, waiting longer after each failure, and give up after max_attempts."""
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            self._wait_for_gap()
            self._last_call = self.clock()
            try:
                return endpoint_cls(**params, timeout=30).get_dict()
            except RETRYABLE as e:
                last_error = e
                if attempt < self.max_attempts:
                    self.sleep(min(60, 2**attempt) + random.random())
        raise FetchError(
            f"{endpoint_cls.__name__} failed after {self.max_attempts} attempts: {last_error}"
        )

    def _write_cache(self, path, data):
        """Write to a .tmp file, then rename it, so a crash never leaves a half-written file."""
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(path)
