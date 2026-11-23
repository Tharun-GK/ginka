from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlencode

import aiohttp

from config.settings import settings
from src.crawler.async_crawler import USER_AGENT
from src.crawler.date_parser import parse_date

ARXIV_API = "https://export.arxiv.org/api/query"
GITHUB_REPO = re.compile(r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
ATOM = {"a": "http://www.w3.org/2005/Atom"}
log = logging.getLogger(__name__)


def parse_feed(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    records = []
    for entry in root.findall("a:entry", ATOM):
        paper_url = entry.findtext("a:id", default="", namespaces=ATOM).strip()
        if paper_url.startswith("http://arxiv.org/abs/"):
            paper_url = paper_url.replace("http://", "https://", 1)
        title = " ".join(entry.findtext("a:title", default="", namespaces=ATOM).split())
        summary = " ".join(entry.findtext("a:summary", default="", namespaces=ATOM).split())
        published = parse_date(entry.findtext("a:published", namespaces=ATOM))
        authors = [author.findtext("a:name", default="", namespaces=ATOM)
                   for author in entry.findall("a:author", ATOM)]
        if not title or not paper_url.startswith("https://arxiv.org/abs/"):
            continue
        records.append({"category": "research", "title": title, "organization": ", ".join(authors),
                        "source_name": "arXiv", "source_url": ARXIV_API, "url": paper_url,
                        "summary": summary, "published_at": published,
                        "raw_data": {"authors": authors, "abstract": summary}})
    return records


async def collect() -> list[dict]:
    params = urlencode({"search_query": "all:artificial intelligence", "start": 0,
                        "max_results": settings.arxiv_results, "sortBy": "submittedDate",
                        "sortOrder": "descending"})
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": USER_AGENT}) as session:
        async with session.get(f"{ARXIV_API}?{params}") as response:
            response.raise_for_status()
            xml = await response.text()
    records = parse_feed(xml)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def verify_github(record: dict) -> None:
        matches = GITHUB_REPO.findall(record["summary"])
        if not matches:
            return
        owner, repository = matches[0]
        repository = repository.removesuffix(".git")
        try:
            async with semaphore:
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                    async with session.get(f"https://api.github.com/repos/{owner}/{repository}") as response:
                        if response.status == 404:
                            return
                        response.raise_for_status()
                        repo = await response.json()
            record["raw_data"].update({"github_repository": repo["html_url"],
                                       "github_stars": repo["stargazers_count"]})
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            log.warning("Could not verify paper GitHub link %s/%s: %s", owner, repository, exc)

    await asyncio.gather(*(verify_github(record) for record in records))
    return records


if __name__ == "__main__":
    print(asyncio.run(collect()))
