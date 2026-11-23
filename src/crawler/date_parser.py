from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

RELATIVE = re.compile(
    r"^\s*(?:published\s+)?(?:(\d+)\s+(minute|hour|day|week)s?\s+ago|yesterday)\s*$",
    re.IGNORECASE,
)


def parse_date(value: str | datetime | None, now: datetime | None = None) -> datetime | None:
    if value is None:
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = value.strip()
        if not text:
            return None
        relative = RELATIVE.match(text)
        if relative:
            if text.casefold().endswith("yesterday"):
                return (current - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            amount = int(relative.group(1))
            unit = relative.group(2).casefold()
            delta = {"minute": timedelta(minutes=amount), "hour": timedelta(hours=amount),
                     "day": timedelta(days=amount), "week": timedelta(weeks=amount)}[unit]
            return current - delta
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(text)
            except (TypeError, ValueError, OverflowError):
                return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_fresh(value: str | datetime | None, now: datetime | None = None) -> bool:
    published = parse_date(value, now=now)
    if published is None:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age = current.astimezone(timezone.utc) - published
    return timedelta(0) <= age <= timedelta(hours=24)


def extract_publication_date(html: str) -> datetime | None:
    soup = BeautifulSoup(html, "html.parser")
    for selector, attribute in (
        ('meta[property="article:published_time"]', "content"),
        ('meta[property="og:published_time"]', "content"),
        ('meta[name="datePublished"]', "content"),
        ('meta[itemprop="datePublished"]', "content"),
        ("time[datetime]", "datetime"),
    ):
        element = soup.select_one(selector)
        if element and (parsed := parse_date(element.get(attribute))):
            return parsed
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = __import__("json").loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            date = parse_date(candidate.get("datePublished") or candidate.get("dateCreated"))
            if date:
                return date
    return None
