import pytest
from unittest.mock import MagicMock, patch
from app.agents.enhancement_agent import enhancement_agent_node
from app.state.schemas import EnhancementAnalysis, EnhancementAction, EnhancementPatch


def test_enhancement_agent_valid_response():
    state = {
        "raw_goal": "Add something",
        "enhancement_chunks": [],
        "source_project_path": "fake/path",
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = EnhancementAnalysis(
        analysis="Looks good",
        changes=[
            EnhancementAction(file="backend/test.js", action="create", content="hello")
        ],
    )

    with patch("app.agents.enhancement_agent.enhancement_llm", mock_llm):
        with patch(
            "app.agents.enhancement_agent.load_full_project_into_memory",
            return_value=([], []),
        ):
            result = enhancement_agent_node(state)
            assert "error" not in result
            assert len(result["enhancement_changes"]) == 1


def test_enhancement_agent_handles_none_result():
    state = {
        "raw_goal": "Add something",
        "enhancement_chunks": [],
        "source_project_path": "fake/path",
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = None

    with patch("app.agents.enhancement_agent.enhancement_llm", mock_llm):
        result = enhancement_agent_node(state)
        assert "error" in result
        assert "structured-output parsing failure" in result["error"]


def test_enhancement_agent_invocation_exception():
    state = {
        "raw_goal": "Add something",
        "enhancement_chunks": [],
        "source_project_path": "fake/path",
    }

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("API rate limit exceeded")

    with patch("app.agents.enhancement_agent.enhancement_llm", mock_llm):
        result = enhancement_agent_node(state)
        assert "error" in result
        assert "LLM invocation failure: API rate limit exceeded" in result["error"]
