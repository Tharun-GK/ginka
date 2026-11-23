from __future__ import annotations

import asyncio

import aiohttp

from config.settings import settings
from src.crawler.async_crawler import USER_AGENT

GITHUB_SEARCH = "https://api.github.com/search/repositories"


async def collect() -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    params = {"q": "topic:ai-tools", "sort": "updated", "per_page": 30}
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(GITHUB_SEARCH, params=params) as response:
            response.raise_for_status()
            body = await response.json()
    records = []
    for repo in body.get("items", []):
        url = repo.get("html_url")
        name = repo.get("name")
        if not url or not name:
            continue
        records.append({"category": "product", "title": name,
                        "organization": (repo.get("owner") or {}).get("login", ""),
                        "source_name": "GitHub topic: ai-tools", "source_url": GITHUB_SEARCH,
                        "url": url, "summary": repo.get("description") or "",
                        "raw_data": {"stars": repo.get("stargazers_count", 0),
                                     "language": repo.get("language"), "topics": repo.get("topics", [])}})
    return records


if __name__ == "__main__":
    print(asyncio.run(collect()))
