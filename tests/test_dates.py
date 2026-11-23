from datetime import datetime, timezone

from src.crawler.date_parser import extract_publication_date, is_fresh, parse_date


def test_iso_and_rfc_dates_normalize_to_utc():
    assert parse_date("2026-11-21T12:00:00Z").utcoffset().total_seconds() == 0
    assert parse_date("Sat, 21 Nov 2026 12:00:00 +0000").hour == 12


def test_relative_dates_and_unknown_dates():
    now = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)
    assert parse_date("Published 2 hours ago", now).hour == 10
    assert parse_date("unknown", now) is None


def test_freshness_requires_verifiable_date_within_24_hours():
    now = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)
    assert is_fresh("2026-11-21T00:01:00Z", now)
    assert not is_fresh("2026-11-19T12:00:00Z", now)
    assert not is_fresh(None, now)


def test_publication_date_metadata_jsonld_and_time():
    assert extract_publication_date('<meta property="og:published_time" content="2026-11-20T08:30:00Z">').hour == 8
    assert extract_publication_date(
        '<script type="application/ld+json">{"datePublished":"2026-11-20T08:30:00Z"}</script>').hour == 8
    assert extract_publication_date('<time datetime="2026-11-20T08:30:00Z">yesterday</time>').hour == 8
