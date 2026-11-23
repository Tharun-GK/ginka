from src.llm.chunking import chunk_text


def test_html_noise_is_removed_and_all_content_is_chunked():
    chunks = chunk_text("<nav>skip me</nav><main><h1>Heading</h1><p>" + "important " * 300 + "</p></main>",
                        max_chars=120)
    joined = "\n".join(chunks)
    assert "skip me" not in joined
    assert "Heading" in joined
    assert "important" in joined
    assert all(len(chunk) <= 120 for chunk in chunks)
