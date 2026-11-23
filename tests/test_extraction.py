import json

import pytest
from pydantic import ValidationError

from src.llm.extraction import Extraction


def test_llm_output_schema_validation():
    result = Extraction.model_validate(json.loads('{"organizations":["OpenAI"],"summary":"Research","topics":["LLM"]}'))
    assert result.organizations == ["OpenAI"]
    with pytest.raises(ValidationError):
        Extraction.model_validate({"organizations": "not-a-list"})
