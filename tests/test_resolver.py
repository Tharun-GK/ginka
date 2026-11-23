from src.resolver.entity_resolver import EntityResolver, normalize
import json
from pathlib import Path


def test_openai_alias_and_suffix_resolve():
    resolver = EntityResolver()
    assert resolver.resolve("OpenAI, Inc.")["canonical_name"] == "OpenAI"
    assert normalize("  OPEN AI, LLC ") == "open ai"


def test_unrelated_names_are_not_fuzzy_merged():
    result = EntityResolver().resolve("Definitely Not A Real Organization 92814")
    assert result["review_required"]
    assert result["canonical_name"] == "Definitely Not A Real Organization 92814"


def test_seed_has_fifty_distinct_canonical_organizations():
    seed = json.loads((Path(__file__).resolve().parents[1] / "data" / "seed_entities.json").read_text())
    assert len(seed) == 50
    assert len({entity["canonical_name"] for entity in seed}) == 50
