from __future__ import annotations

import asyncio

import aiohttp

from config.settings import settings
from src.crawler.async_crawler import USER_AGENT

HN_API = "https://hacker-news.firebaseio.com/v0"


async def collect() -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": USER_AGENT}) as session:
        async with session.get(f"{HN_API}/v0/showstories.json") as response:
            response.raise_for_status()
            story_ids = (await response.json())[:50]
        semaphore = asyncio.Semaphore(settings.max_concurrency)

        async def get_story(story_id: int) -> dict | None:
            async with semaphore:
                try:
                    async with session.get(f"{HN_API}/v0/item/{story_id}.json") as response:
                        response.raise_for_status()
                        return await response.json()
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    return None

        stories = await asyncio.gather(*(get_story(story_id) for story_id in story_ids))
    records = []
    for story in stories:
        if not story or story.get("deleted") or story.get("dead"):
            continue
        title = story.get("title", "")
        lower = title.casefold()
        if not title.casefold().startswith("show hn:") or not any(
            term in lower for term in (" ai", "machine learning", "llm", "artificial intelligence")
        ):
            continue
        url = story.get("url") or f"https://news.ycombinator.com/item?id={story['id']}"
        records.append({"category": "startup", "title": title.removeprefix("Show HN: ").strip(),
                        "organization": story.get("by", ""), "source_name": "Hacker News Show HN",
                        "source_url": f"https://news.ycombinator.com/item?id={story['id']}",
                        "url": url, "summary": story.get("text", ""),
                        "published_at": story.get("time") and __import__("datetime").datetime.fromtimestamp(
                            story["time"], __import__("datetime").timezone.utc),
                        "raw_data": {"hn_id": story["id"], "submitter": story.get("by", "")}})
    return records


if __name__ == "__main__":
    print(asyncio.run(collect()))
