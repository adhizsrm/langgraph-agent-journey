import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from app.state.schemas import OrchestratorOutput
import app.agents.llm


def test_fallback_extracts_raw_json():
    """Verify that raw JSON (without fences) parses correctly."""
    # This just tests the extraction logic handles plain JSON properly
    raw = '{"plan": {"stages": [{"name": "test", "description": "desc"}]}, "confidence_score": 0.9, "reasoning": "ok"}'
    parsed = app.agents.llm._extract_and_parse_json(raw)
    assert parsed["confidence_score"] == 0.9


def test_fallback_extracts_fenced_json():
    """Verify that fenced JSON parses correctly."""
    raw = '```json\n{"plan": {"stages": [{"name": "test", "description": "desc"}]}, "confidence_score": 0.9, "reasoning": "ok"}\n```'
    parsed = app.agents.llm._extract_and_parse_json(raw)
    assert parsed["confidence_score"] == 0.9


@patch("app.agents.llm.provider", "openrouter")
def test_native_wrapper_fenced_json_fallback():
    """
    Test the NativeStructuredLLMWrapper invoke method with a mocked
    native LLM that throws a ValidationError due to markdown fences.
    """
    # Create the structured LLM (forces NativeStructuredLLMWrapper because of the patch)

    # We must mock llm.with_structured_output to return our mock native_llm
    mock_native_llm = MagicMock()

    # We create a fake ValidationError that looks like Pydantic's
    valid_json = {
        "entity_spec": {"entity_name": "Task", "fields": {"title": "string"}},
        "crud_operations": ["Create", "Read"],
        "api_contract": {"base_route": "/api/tasks", "operations": []},
        "execution_order": "backend_first",
        "file_locations": {"backend_root": "backend/", "frontend_root": "frontend/"},
    }
    import json

    invalid_json_string = f"```json\n{json.dumps(valid_json)}\n```"

    # In Pydantic v2, ValidationError takes an error dict list
    try:
        OrchestratorOutput.model_validate_json(invalid_json_string)
    except ValidationError as real_error:
        fake_validation_error = real_error

    mock_native_llm.invoke.side_effect = [fake_validation_error]

    with patch("app.agents.llm.llm", MagicMock()) as mock_llm:
        mock_llm.with_structured_output.return_value = mock_native_llm
        wrapper = app.agents.llm.create_structured_llm(
            OrchestratorOutput, caller="test_caller"
        )

        assert (
            wrapper.__class__.__name__ == "NativeStructuredLLMWrapper"
        ), "Should return NativeStructuredLLMWrapper"

        # Call invoke. It should:
        # 1. Try mock_native_llm.invoke()
        # 2. Catch the ValidationError
        # 3. Use fallback to extract from the error string and parse
        # 4. Return an OrchestratorOutput WITHOUT retrying

        result = wrapper.invoke("Test prompt")

        # Verify
        assert isinstance(result, OrchestratorOutput)
        assert result.execution_order == "backend_first"

        # Ensure it didn't retry - it should only be called once!
        assert mock_native_llm.invoke.call_count == 1
