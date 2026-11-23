from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass

import aiohttp
from pydantic import BaseModel, Field, ValidationError

from config.settings import settings
from src.llm.chunking import chunk_text

log = logging.getLogger(__name__)


class Extraction(BaseModel):
    organizations: list[str] = Field(default_factory=list)
    summary: str = ""
    topics: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class Provider:
    name: str
    endpoint: str
    model: str
    api_key: str
    key_name: str


PROVIDERS = (
    Provider("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
             "gemini-2.0-flash", settings.gemini_api_key, "GEMINI_API_KEY"),
    Provider("Groq", "https://api.groq.com/openai/v1/chat/completions",
             "llama-3.3-70b-versatile", settings.groq_api_key, "GROQ_API_KEY"),
    Provider("DeepSeek", "https://api.deepseek.com/chat/completions",
             "deepseek-chat", settings.deepseek_api_key, "DEEPSEEK_API_KEY"),
)


async def _request(provider: Provider, text: str) -> dict:
    headers = {"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"}
    payload = {"model": provider.model, "messages": [
        {"role": "system", "content": "Extract organization names, a concise summary, and topics. Return JSON only."},
        {"role": "user", "content": text}],
        "response_format": {"type": "json_object"}}
    timeout = aiohttp.ClientTimeout(total=45)
    for attempt in range(3):
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(provider.endpoint, headers=headers, json=payload) as response:
                if response.status == 413:
                    raise ValueError("LLM provider rejected payload size (HTTP 413); split it into smaller chunks.")
                if response.status == 429 and attempt < 2:
                    await response.read()
                else:
                    response.raise_for_status()
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]
                    if data.get("usage"):
                        log.info("%s token usage: %s", provider.name, data["usage"])
                    return json.loads(content)
        import asyncio
        await asyncio.sleep(min(2 ** attempt + random.random(), 8))
    raise RuntimeError(f"{provider.name} rate limited after retries")


async def extract(content: str, providers: tuple[Provider, ...] = PROVIDERS) -> Extraction | None:
    for provider in providers:
        if not provider.api_key:
            continue
        try:
            pieces = chunk_text(content)
            results = []
            for piece in pieces:
                results.append(Extraction.model_validate(await _request(provider, piece)))
            return Extraction(
                organizations=list(dict.fromkeys(name for result in results for name in result.organizations)),
                summary=" ".join(result.summary for result in results if result.summary),
                topics=list(dict.fromkeys(topic for result in results for topic in result.topics)),
            )
        except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, IndexError,
                json.JSONDecodeError, ValidationError, RuntimeError) as exc:
            log.warning("LLM provider %s failed: %s", provider.name, exc)
    return None
