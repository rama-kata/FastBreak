import pytest

from fastbreak.pipeline.fetch import Fetcher, FetchError, IncompleteResponse


class FakeEndpoint:
    calls = 0
    fail_times = 0

    def __init__(self, timeout=None, **params):
        FakeEndpoint.calls += 1
        if FakeEndpoint.calls <= FakeEndpoint.fail_times:
            raise ValueError("not JSON")  # what a blocked request looks like
        self.params = params

    def get_dict(self):
        return {"params": self.params}


class HalfFinishedBoxScore:
    """What nba_api does with a box score whose team stats are still null."""

    calls = 0

    def __init__(self, timeout=None, **params):
        HalfFinishedBoxScore.calls += 1
        stats = None
        stats.get("points")


class FakeClock:
    """Time only moves when the fetcher sleeps, and every sleep is recorded."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock():
    FakeEndpoint.calls = 0
    FakeEndpoint.fail_times = 0
    return FakeClock()


@pytest.fixture
def fetcher(tmp_path, clock):
    return Fetcher(tmp_path, sleep=clock.sleep, clock=clock.clock)


def test_first_call_fetches_and_caches(fetcher, tmp_path):
    data = fetcher.get(FakeEndpoint, season="2024-25")
    assert data == {"params": {"season": "2024-25"}}
    assert FakeEndpoint.calls == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_second_call_uses_cache(fetcher):
    fetcher.get(FakeEndpoint, season="2024-25")
    fetcher.get(FakeEndpoint, season="2024-25")
    assert FakeEndpoint.calls == 1


def test_refresh_fetches_again(fetcher):
    fetcher.get(FakeEndpoint, season="2024-25")
    fetcher.get(FakeEndpoint, refresh=True, season="2024-25")
    assert FakeEndpoint.calls == 2


def test_retries_then_succeeds(fetcher):
    FakeEndpoint.fail_times = 2
    data = fetcher.get(FakeEndpoint, season="2024-25")
    assert data == {"params": {"season": "2024-25"}}
    assert FakeEndpoint.calls == 3


def test_gives_up_after_max_attempts(fetcher):
    FakeEndpoint.fail_times = 99
    with pytest.raises(FetchError, match="after 5 attempts"):
        fetcher.get(FakeEndpoint, season="2024-25")
    assert FakeEndpoint.calls == 5


def test_failures_are_not_cached(fetcher, tmp_path):
    FakeEndpoint.fail_times = 99
    with pytest.raises(FetchError):
        fetcher.get(FakeEndpoint, season="2024-25")
    assert list(tmp_path.iterdir()) == []


def test_waits_grow_between_retries(fetcher, clock):
    FakeEndpoint.fail_times = 99
    with pytest.raises(FetchError):
        fetcher.get(FakeEndpoint, season="2024-25")
    assert len(clock.sleeps) == 4  # one wait between each of the 5 attempts
    assert all(later > earlier for earlier, later in zip(clock.sleeps, clock.sleeps[1:]))


def test_an_incomplete_response_is_not_retried_or_cached(fetcher, tmp_path):
    HalfFinishedBoxScore.calls = 0
    with pytest.raises(IncompleteResponse, match="came back incomplete: AttributeError"):
        fetcher.get(HalfFinishedBoxScore, game_id="0022600101")
    assert HalfFinishedBoxScore.calls == 1
    assert list(tmp_path.glob("*.json")) == []
