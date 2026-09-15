import pytest
from app.graph.routing import route_safety


def test_route_safety_with_error_returns_cleanup():
    state = {"error": "LLM structured output validation failed repeatedly..."}

    # State has an error, it should explicitly route to cleanup_failed_project
    route = route_safety(state)
    assert route == "cleanup_failed_project"


def test_route_safety_without_error_but_with_safety_errors():
    state = {"safety_errors": ["Patch target not found"]}

    # Safety errors trigger repair
    route = route_safety(state)
    assert route == "project_repair"


def test_route_safety_clean():
    state = {}

    # Clean state progresses to validation
    route = route_safety(state)
    assert route == "validate_generated_project"
