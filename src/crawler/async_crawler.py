from __future__ import annotations

import asyncio
import logging

import aiohttp

from config.settings import settings

log = logging.getLogger(__name__)
USER_AGENT = "GraphOneResearchPrototype/1.0 (public data; contact: configure your own user agent)"


async def fetch_text(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, headers={"User-Agent": USER_AGENT}) as response:
        response.raise_for_status()
        return await response.text()


async def fetch_many(urls: list[str]) -> list[str]:
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
    semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def one(session: aiohttp.ClientSession, url: str) -> str | None:
        async with semaphore:
            try:
                return await fetch_text(session, url)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                log.warning("Public source request failed for %s: %s", url, exc)
                return None

    async with aiohttp.ClientSession(timeout=timeout) as session:
        return [value for value in await asyncio.gather(*(one(session, url) for url in urls)) if value is not None]
