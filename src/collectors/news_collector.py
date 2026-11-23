from __future__ import annotations

import asyncio
import logging
import os
import xml.etree.ElementTree as ET

import aiohttp

from config.settings import settings
from src.crawler.async_crawler import USER_AGENT
from src.crawler.date_parser import extract_publication_date, is_fresh, parse_date

DEFAULT_FEEDS = "https://feeds.arstechnica.com/arstechnica/technology-lab"
log = logging.getLogger(__name__)


async def collect() -> list[dict]:
    feeds = [url.strip() for url in os.getenv("NEWS_RSS_FEEDS", DEFAULT_FEEDS).split(",") if url.strip()]
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": USER_AGENT}) as session:
        async def read(url: str):
            async with session.get(url) as response:
                response.raise_for_status()
                return url, await response.text()
        results = await asyncio.gather(*(read(url) for url in feeds), return_exceptions=True)
    records = []
    for result in results:
        if isinstance(result, Exception):
            log.warning("News feed request failed: %s", result)
            continue
        feed_url, body = result
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            log.warning("Ignoring malformed news RSS feed: %s", feed_url)
            continue
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            description = item.findtext("description") or ""
            raw_date = item.findtext("pubDate") or ""
            published = parse_date(raw_date)
            if not published:
                published = extract_publication_date(item.findtext("description") or "")
            if not title or not url or not is_fresh(published):
                continue
            if not any(term in f"{title} {description}".casefold()
                       for term in ("artificial intelligence", "machine learning", " ai ", "llm", "openai")):
                continue
            records.append({"category": "news", "title": title, "organization": "",
                            "source_name": feed_url, "source_url": feed_url, "url": url,
                            "summary": description, "published_at": published,
                            "raw_data": {"description": description}})
    return records


if __name__ == "__main__":
    print(asyncio.run(collect()))
