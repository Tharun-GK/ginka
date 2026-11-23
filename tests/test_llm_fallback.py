import asyncio

from src.llm.extraction import Extraction, Provider, extract


def test_provider_failure_falls_back_to_next_configured_provider(monkeypatch):
    first = Provider("first", "https://invalid.example", "model", "secret-1", "FIRST_KEY")
    second = Provider("second", "https://invalid.example", "model", "secret-2", "SECOND_KEY")
    calls = []

    async def fake_request(provider, text):
        calls.append(provider.name)
        if provider is first:
            raise RuntimeError("provider unavailable")
        return {"organizations": ["OpenAI"], "summary": "AI research", "topics": ["research"]}

    monkeypatch.setattr("src.llm.extraction._request", fake_request)
    result = asyncio.run(extract("Article text", providers=(first, second)))
    assert isinstance(result, Extraction)
    assert result.organizations == ["OpenAI"]
    assert calls == ["first", "second"]
