from __future__ import annotations

from bs4 import BeautifulSoup


def chunk_text(content: str, max_chars: int = 6000) -> list[str]:
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    soup = BeautifulSoup(content, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        node.decompose()
    text = soup.get_text("\n", strip=True) if "<" in content and ">" in content else content
    blocks = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    current = ""
    for block in blocks:
        while len(block) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            split_at = block.rfind(" ", 0, max_chars + 1)
            split_at = split_at if split_at > 0 else max_chars
            chunks.append(block[:split_at])
            block = block[split_at:].lstrip()
        candidate = f"{current}\n{block}".strip() if current else block
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
