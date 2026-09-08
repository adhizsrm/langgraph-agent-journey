import json
from pydantic import BaseModel, ValidationError
from app.agents.llm import create_structured_llm


class FileContent(BaseModel):
    path: str
    content: str


class GeneratedFiles(BaseModel):
    files: list[FileContent]


class MockLLMResponse:
    def __init__(self, content):
        self.content = content


class MockLLM:
    def __init__(self):
        self.responses = []
        self.calls = 0

    def invoke(self, prompt):
        res = self.responses[self.calls]
        self.calls += 1
        return MockLLMResponse(res)


import app.agents.llm as llm_module


def setup_mock_llm(responses):
    mock = MockLLM()
    mock.responses = responses
    original_llm = llm_module.llm
    llm_module.llm = mock
    original_provider = llm_module.provider
    llm_module.provider = "mock"
    return mock, original_llm, original_provider


def teardown_mock_llm(original_llm, original_provider):
    llm_module.llm = original_llm
    llm_module.provider = original_provider


def test_1_valid_json():
    print("Testing 1 - Valid JSON...")
    mock, orig_llm, orig_prov = setup_mock_llm(
        ['{"files": [{"path": "a.js", "content": "console.log(1);"}]}']
    )
    try:
        wrapper = create_structured_llm(GeneratedFiles)
        res = wrapper.invoke("test")
        assert len(res.files) == 1
        assert res.files[0].path == "a.js"
    finally:
        teardown_mock_llm(orig_llm, orig_prov)


def test_2_fenced_json():
    print("Testing 2 - Fenced JSON...")
    mock, orig_llm, orig_prov = setup_mock_llm(
        ['```json\n{"files": [{"path": "a.js", "content": "console.log(1);"}]}\n```']
    )
    try:
        wrapper = create_structured_llm(GeneratedFiles)
        res = wrapper.invoke("test")
        assert len(res.files) == 1
    finally:
        teardown_mock_llm(orig_llm, orig_prov)


def test_3_think_block():
    print("Testing 3 - Think Block...")
    mock, orig_llm, orig_prov = setup_mock_llm(
        [
            '<think>\ninternal reasoning\n</think>\n\n{"files": [{"path": "a.js", "content": "console.log(1);"}]}'
        ]
    )
    try:
        wrapper = create_structured_llm(GeneratedFiles)
        res = wrapper.invoke("test")
        assert len(res.files) == 1
    finally:
        teardown_mock_llm(orig_llm, orig_prov)


def test_4_surrounding_text():
    print("Testing 4 - Surrounding Text...")
    mock, orig_llm, orig_prov = setup_mock_llm(
        [
            'Here is the output:\n{"files": [{"path": "a.js", "content": "console.log(1);"}]}\nHope that helps!'
        ]
    )
    try:
        wrapper = create_structured_llm(GeneratedFiles)
        res = wrapper.invoke("test")
        assert len(res.files) == 1
    finally:
        teardown_mock_llm(orig_llm, orig_prov)


def test_5_source_code_backslashes():
    print("Testing 5 - Source Code Escaping...")
    content = 'const value = "\\\\";\nconst regex = /\\\\/g;\nconst windowsPath = "C:\\\\temp\\\\file";'
    json_str = json.dumps({"files": [{"path": "a.js", "content": content}]})
    mock, orig_llm, orig_prov = setup_mock_llm([json_str])
    try:
        wrapper = create_structured_llm(GeneratedFiles)
        res = wrapper.invoke("test")
        assert res.files[0].content == content
    finally:
        teardown_mock_llm(orig_llm, orig_prov)


def test_6_invalid_quote_escape():
    print("Testing 6 - Invalid Quote Escape...")
    bad_json = '{"files": [{"path": "a.js", "content": "console.log(\\\'hi\\\');"}]}'
    mock, orig_llm, orig_prov = setup_mock_llm([bad_json, bad_json, bad_json])
    try:
        wrapper = create_structured_llm(GeneratedFiles)
        try:
            wrapper.invoke("test")
            assert False, "Should have raised exception"
        except Exception as e:
            assert (
                "JSONSyntaxError" in str(type(e).__name__)
                or "JSONDecodeError" in str(e)
                or "JSONSyntaxError" in str(e)
            )
    finally:
        teardown_mock_llm(orig_llm, orig_prov)


def test_7_schema_validation_failure():
    print("Testing 7 - Schema Validation Failure...")
    mock, orig_llm, orig_prov = setup_mock_llm(
        ['{"wrong_key": "value"}', '{"wrong_key": "value"}', '{"wrong_key": "value"}']
    )
    try:
        wrapper = create_structured_llm(GeneratedFiles)
        try:
            wrapper.invoke("test")
            assert False, "Should have raised exception"
        except Exception as e:
            assert "ValidationError" in str(
                type(e).__name__
            ) or "SchemaValidationError" in str(type(e).__name__)
    finally:
        teardown_mock_llm(orig_llm, orig_prov)


def test_8_malformed_truncated_response():
    print("Testing 8 - Malformed Truncated Response...")
    mock, orig_llm, orig_prov = setup_mock_llm(
        [
            '{"files": [{"path": "a.js", "content": "console.',
            '{"files": [{"path": "a.js", "content": "console.',
            '{"files": [{"path": "a.js", "content": "console.',
        ]
    )
    try:
        wrapper = create_structured_llm(GeneratedFiles)
        try:
            wrapper.invoke("test")
            assert False, "Should have raised exception"
        except Exception as e:
            assert "JSONExtractionError" in str(
                type(e).__name__
            ) or "JSONSyntaxError" in str(type(e).__name__)
    finally:
        teardown_mock_llm(orig_llm, orig_prov)


if __name__ == "__main__":
    test_1_valid_json()
    test_2_fenced_json()
    test_3_think_block()
    test_4_surrounding_text()
    test_5_source_code_backslashes()
    test_6_invalid_quote_escape()
    test_7_schema_validation_failure()
    test_8_malformed_truncated_response()
    print("All tests passed cleanly!")
