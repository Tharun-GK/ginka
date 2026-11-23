from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz, process

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed_entities.json"
LEGAL_SUFFIXES = {"inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation", "company", "co"}


def normalize(name: str) -> str:
    value = unicodedata.normalize("NFKC", name).casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    tokens = [token for token in value.split() if token not in LEGAL_SUFFIXES]
    return " ".join(tokens)


class EntityResolver:
    def __init__(self, path: Path = SEED_PATH):
        entities = json.loads(path.read_text(encoding="utf-8"))
        self.aliases: dict[str, str] = {}
        for entity in entities:
            canonical = entity["canonical_name"]
            for alias in [canonical, *entity.get("aliases", [])]:
                self.aliases[normalize(alias)] = canonical
        self.keys = list(self.aliases)

    def resolve(self, raw_name: str) -> dict:
        key = normalize(raw_name)
        if not key:
            return {"raw_name": raw_name, "canonical_name": raw_name, "confidence": 0.0,
                    "method": "unmatched", "review_required": True}
        if key in self.aliases:
            return {"raw_name": raw_name, "canonical_name": self.aliases[key], "confidence": 1.0,
                    "method": "exact", "review_required": False}
        match = process.extract(key, self.keys, scorer=fuzz.ratio, limit=2)
        score = match[0][1] if match else 0
        runner_up = match[1][1] if len(match) > 1 else 0
        if score >= 94 and score - runner_up >= 8:
            return {"raw_name": raw_name, "canonical_name": self.aliases[match[0][0]],
                    "confidence": score / 100, "method": "fuzzy", "review_required": False}
        return {"raw_name": raw_name, "canonical_name": raw_name, "confidence": score / 100,
                "method": "manual_review", "review_required": True}
