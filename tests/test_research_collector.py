from src.collectors.research_collector import parse_feed


def test_arxiv_api_http_id_becomes_traceable_https_url():
    feed = """<feed xmlns="http://www.w3.org/2005/Atom">
    <entry><id>http://arxiv.org/abs/2601.01234v1</id>
    <title>A Real Paper</title><summary>Test abstract</summary>
    <published>2026-01-02T03:04:05Z</published>
    <author><name>Research Author</name></author></entry>
    </feed>"""
    records = parse_feed(feed)
    assert len(records) == 1
    assert records[0]["url"] == "https://arxiv.org/abs/2601.01234v1"
    assert records[0]["source_url"] == "https://export.arxiv.org/api/query"
