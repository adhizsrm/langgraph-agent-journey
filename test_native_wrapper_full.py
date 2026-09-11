import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError
import json
from httpx import HTTPStatusError, Request, Response

from app.state.schemas import OrchestratorOutput
import app.agents.llm

# Shared valid response mock for OrchestratorOutput
valid_json = {
    "entity_spec": {"entity_name": "Task", "fields": {"title": "string"}},
    "crud_operations": ["Create", "Read"],
    "api_contract": {"base_route": "/api/tasks", "operations": []},
    "execution_order": "backend_first",
    "file_locations": {"backend_root": "backend/", "frontend_root": "frontend/"},
}


def _mock_llm_wrapper(mock_invocations):
    mock_native_llm = MagicMock()
    mock_native_llm.invoke.side_effect = mock_invocations

    # We patch "provider" dynamically but we also patch "llm" so it initializes correctly
    with patch("app.agents.llm.provider", "openrouter"), patch(
        "app.agents.llm.llm", MagicMock()
    ) as mock_llm:
        mock_llm.with_structured_output.return_value = mock_native_llm
        wrapper = app.agents.llm.create_structured_llm(
            OrchestratorOutput, caller="test_caller"
        )
        return wrapper, mock_native_llm


def test_native_wrapper_raw_json():
    # Simulate Langchain parsing it perfectly and returning the object (raw json works)
    expected_obj = OrchestratorOutput(**valid_json)
    wrapper, mock_llm = _mock_llm_wrapper([expected_obj])

    result = wrapper.invoke("Test")
    assert result.execution_order == "backend_first"
    assert mock_llm.invoke.call_count == 1


def test_native_wrapper_embedded_json():
    # Simulate a ValidationError caused by text embedding
    embedded_str = (
        f"Here is your json output:\n{json.dumps(valid_json)}\nEnjoy your day!"
    )
    try:
        OrchestratorOutput.model_validate_json(embedded_str)
    except ValidationError as e:
        validation_error = e

    wrapper, mock_llm = _mock_llm_wrapper([validation_error])

    result = wrapper.invoke("Test")
    assert result.execution_order == "backend_first"
    assert mock_llm.invoke.call_count == 1  # Should fallback immediately, no re-calls


def test_native_wrapper_pure_text_rejected():
    str_val = "I'll generate the complete project for you..."
    try:
        OrchestratorOutput.model_validate_json(str_val)
    except ValidationError as e:
        validation_error = e

    wrapper, mock_llm = _mock_llm_wrapper(
        [validation_error, validation_error, validation_error]
    )

    with pytest.raises(app.agents.llm.SchemaValidationError):
        wrapper.invoke("Test")
    assert mock_llm.invoke.call_count == 3  # Tried 3 times and failed


def test_native_wrapper_wrong_shape_rejected():
    wrong_json = {"plan": {"stages": []}}
    try:
        OrchestratorOutput.model_validate_json(json.dumps(wrong_json))
    except ValidationError as e:
        validation_error = e

    wrapper, mock_llm = _mock_llm_wrapper(
        [validation_error, validation_error, validation_error]
    )

    with pytest.raises(app.agents.llm.SchemaValidationError):
        wrapper.invoke("Test")
    assert mock_llm.invoke.call_count == 3


def test_native_wrapper_invalid_json():
    invalid_json = '{"entity_spec": missing'
    try:
        OrchestratorOutput.model_validate_json(invalid_json)
    except ValidationError as e:
        validation_error = e

    wrapper, mock_llm = _mock_llm_wrapper(
        [validation_error, validation_error, validation_error]
    )

    with pytest.raises(app.agents.llm.SchemaValidationError):
        wrapper.invoke("Test")
    assert mock_llm.invoke.call_count == 3


def test_native_wrapper_provider_error():
    # Ensure a Provider error doesn't get labelled as SchemaValidationError
    # Mocking httpx.HTTPError specifically which inherits Exception
    import httpx

    # Pydantic OutputParser or Langchain API Error
    from openai import RateLimitError

    req = httpx.Request("GET", "https://api.openai.fake")
    resp = httpx.Response(429, request=req)
    err = RateLimitError("Rate limit exceeded", response=resp, body=None)

    wrapper, mock_llm = _mock_llm_wrapper([err, err, err])

    with pytest.raises(RateLimitError):
        wrapper.invoke("Test")
    assert mock_llm.invoke.call_count == 3
