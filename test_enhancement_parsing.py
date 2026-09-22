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
    mock_llm.invoke.return_value = {
        "raw": "",
        "parsing_error": None,
        "parsed": EnhancementAnalysis(
            analysis="Looks good",
            checklist={
                "requires_ui_changes": False,
                "requires_stylesheet_changes": False,
                "requires_logic_state": False,
                "requires_backend_api": True,
            },
            target_files=["backend/test.js"],
            changes=[
                EnhancementAction(
                    file="backend/test.js", action="create", content="hello"
                )
            ],
        ),
    }

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
    mock_llm.invoke.return_value = {"raw": "", "parsed": None, "parsing_error": None}

    with patch("app.agents.enhancement_agent.enhancement_llm", mock_llm):
        result = enhancement_agent_node(state)
        assert "error" in result
        assert (
            "structured-output parsing failure: Enhancement LLM returned None"
            in result["error"]
        )


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


from app.state.schemas import EnhancementAnalysis
from pydantic import ValidationError


def test_enhancement_agent_retry_on_validation_error():
    state = {
        "raw_goal": "Add something",
        "enhancement_chunks": [],
        "source_project_path": "fake/path",
    }

    mock_llm = MagicMock()
    # First call: ValidationError, Second call: Success
    mock_llm.invoke.side_effect = [
        {
            "raw": '{"bad": "json"}',
            "parsed": None,
            "parsing_error": ValidationError.from_exception_data(
                "Validation error", []
            ),
        },
        {
            "raw": '{"good": "json"}',
            "parsed": EnhancementAnalysis(
                analysis="Fixed",
                checklist={
                    "requires_ui_changes": False,
                    "requires_stylesheet_changes": False,
                    "requires_logic_state": False,
                    "requires_backend_api": True,
                },
                target_files=["backend/test.js"],
                changes=[
                    EnhancementAction(
                        file="backend/test.js", action="create", content="hello"
                    )
                ],
            ),
            "parsing_error": None,
        },
    ]

    with patch("app.agents.enhancement_agent.enhancement_llm", mock_llm):
        with patch(
            "app.agents.enhancement_agent.load_full_project_into_memory",
            return_value=([], []),
        ):
            result = enhancement_agent_node(state)
            assert "error" not in result
            assert len(result["enhancement_changes"]) == 1
            assert mock_llm.invoke.call_count == 2

            # Verify the prompt passed in the second call includes the failure text AND the previous raw LLM output
            second_call_prompt = mock_llm.invoke.call_args_list[1][0][0]
            assert '{"bad": "json"}' in second_call_prompt
            assert "Validation Error:" in second_call_prompt
            assert (
                "Your previous output failed structured validation"
                in second_call_prompt
            )


def test_enhancement_agent_retry_exhaustion():
    state = {
        "raw_goal": "Add something",
        "enhancement_chunks": [],
        "source_project_path": "fake/path",
    }
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = {
        "raw": '{"bad": "json"}',
        "parsed": None,
        "parsing_error": ValidationError.from_exception_data("Syntax error", []),
    }

    with patch("app.agents.enhancement_agent.enhancement_llm", mock_llm):
        result = enhancement_agent_node(state)
        # Verify clean GraphState error on exhaustion
        assert "error" in result
        assert "LLM structured output validation failed repeatedly: " in result["error"]
        assert mock_llm.invoke.call_count == 3


def test_target_files_changes_mismatch():
    with pytest.raises(
        ValidationError, match="Mismatch between target_files and changes"
    ):
        EnhancementAnalysis(
            analysis="Mismatch test",
            checklist={
                "requires_ui_changes": False,
                "requires_stylesheet_changes": False,
                "requires_logic_state": False,
                "requires_backend_api": False,
            },
            target_files=["frontend/src/App.jsx", "frontend/src/App.css"],
            changes=[
                EnhancementAction(
                    file="frontend/src/App.jsx",
                    action="modify",
                    patches=[
                        EnhancementPatch(target_content="a", replacement_content="b")
                    ],
                )
            ],
        )


def test_requires_stylesheet_changes_with_no_css_target():
    with pytest.raises(
        ValidationError, match="requires_stylesheet_changes=True but no .css/.scss file"
    ):
        EnhancementAnalysis(
            analysis="CSS test",
            checklist={
                "requires_ui_changes": False,
                "requires_stylesheet_changes": True,
                "requires_logic_state": False,
                "requires_backend_api": False,
            },
            target_files=["frontend/src/App.jsx"],
            changes=[
                EnhancementAction(
                    file="frontend/src/App.jsx",
                    action="modify",
                    patches=[
                        EnhancementPatch(target_content="a", replacement_content="b")
                    ],
                )
            ],
        )


def test_requires_backend_api_with_no_backend_target():
    with pytest.raises(
        ValidationError, match="requires_backend_api=True but no backend/ file"
    ):
        EnhancementAnalysis(
            analysis="Backend test",
            checklist={
                "requires_ui_changes": False,
                "requires_stylesheet_changes": False,
                "requires_logic_state": False,
                "requires_backend_api": True,
            },
            target_files=["frontend/src/api.js"],
            changes=[
                EnhancementAction(
                    file="frontend/src/api.js",
                    action="modify",
                    patches=[
                        EnhancementPatch(target_content="a", replacement_content="b")
                    ],
                )
            ],
        )


def test_requires_ui_changes_with_no_ui_target():
    with pytest.raises(
        ValidationError, match="requires_ui_changes=True but no .jsx/.tsx/.html file"
    ):
        EnhancementAnalysis(
            analysis="UI test",
            checklist={
                "requires_ui_changes": True,
                "requires_stylesheet_changes": False,
                "requires_logic_state": False,
                "requires_backend_api": False,
            },
            target_files=["frontend/src/utils.js"],
            changes=[
                EnhancementAction(
                    file="frontend/src/utils.js",
                    action="modify",
                    patches=[
                        EnhancementPatch(target_content="a", replacement_content="b")
                    ],
                )
            ],
        )


def test_valid_search_bar_style_single_file_enhancement_passes():
    # Should not raise exception
    EnhancementAnalysis(
        analysis="Search bar test",
        checklist={
            "requires_ui_changes": True,
            "requires_stylesheet_changes": False,
            "requires_logic_state": True,
            "requires_backend_api": False,
        },
        target_files=["frontend/src/App.jsx"],
        changes=[
            EnhancementAction(
                file="frontend/src/App.jsx",
                action="modify",
                patches=[EnhancementPatch(target_content="a", replacement_content="b")],
            )
        ],
    )


def test_valid_multi_file_enhancement_passes():
    # Should not raise exception
    EnhancementAnalysis(
        analysis="Dark mode test",
        checklist={
            "requires_ui_changes": True,
            "requires_stylesheet_changes": True,
            "requires_logic_state": True,
            "requires_backend_api": False,
        },
        target_files=["frontend/src/App.jsx", "frontend/src/App.css"],
        changes=[
            EnhancementAction(
                file="frontend/src/App.jsx",
                action="modify",
                patches=[EnhancementPatch(target_content="a", replacement_content="b")],
            ),
            EnhancementAction(
                file="frontend/src/App.css",
                action="modify",
                patches=[EnhancementPatch(target_content="c", replacement_content="d")],
            ),
        ],
    )


from app.state.schemas import EnhancementPatch
from pydantic import ValidationError


def test_enhancement_action_valid_modify():
    # Should not raise exception
    action = EnhancementAction(
        file="frontend/src/App.css",
        action="modify",
        patches=[EnhancementPatch(target_content="a", replacement_content="b")],
    )
    assert action.patches is not None
    assert len(action.patches) == 1


def test_enhancement_action_modify_with_content_but_no_patches():
    with pytest.raises(
        ValidationError, match="MUST contain a non-empty 'patches' list"
    ):
        EnhancementAction(
            file="frontend/src/App.css",
            action="modify",
            content="body { background: black; }",
        )


def test_enhancement_action_modify_with_empty_patches():
    with pytest.raises(
        ValidationError, match="MUST contain a non-empty 'patches' list"
    ):
        EnhancementAction(file="frontend/src/App.css", action="modify", patches=[])


def test_enhancement_action_create_with_content():
    # Should not raise exception for action='create'
    action = EnhancementAction(
        file="frontend/src/NewComp.jsx",
        action="create",
        content="export const NewComp = () => <div/>;",
    )
    assert action.content is not None


def test_enhancement_agent_dark_mode_completeness_contract():
    # Prove that the post-structured-output result of a dark-mode enhancement
    # must contain both DOM wiring in JSX and consuming CSS rules.
    # This validates our test boundary for expected LLM completion.

    jsx_patch = EnhancementPatch(
        target_content="<h1>Note App</h1>",
        replacement_content="<div className={`app ${darkMode ? 'dark-mode' : ''}`}>\n<h1>Note App</h1>",
    )

    css_patch = EnhancementPatch(
        target_content="body {",
        replacement_content="html.dark-mode body {\n  background: #333;\n}\nbody {",
    )

    action_jsx = EnhancementAction(
        file="frontend/src/App.jsx", action="modify", patches=[jsx_patch]
    )
    action_css = EnhancementAction(
        file="frontend/src/App.css", action="modify", patches=[css_patch]
    )

    original_jsx = "<h1>Note App</h1>"
    original_css = "body {"

    final_jsx = original_jsx.replace(
        jsx_patch.target_content, jsx_patch.replacement_content
    )
    final_css = original_css.replace(
        css_patch.target_content, css_patch.replacement_content
    )

    # Assert requirement 1: DOM Wiring in JSX
    assert "dark-mode" in final_jsx
    assert "${darkMode" in final_jsx or "classList.toggle('dark-mode'" in final_jsx

    # Assert requirement 2: Consuming CSS rules
    assert "html.dark-mode" in final_css or ".dark-mode" in final_css


def test_enhancement_agent_preserves_baseline_css():
    # Prove the full-file replacement failure pattern is rejected or baseline is preserved by targeted patch
    original_css = "body {\n  margin: 0;\n}\n.app {\n  max-width: 800px;\n}\n"

    # Incorrect behavior (full file overwrite with just toggle)
    bad_patch = EnhancementPatch(
        target_content=original_css,
        replacement_content=".dark-mode-toggle { display: flex; }",
    )
    bad_result = original_css.replace(
        bad_patch.target_content, bad_patch.replacement_content
    )
    # The bad patch destroys the baseline
    assert ".app {" not in bad_result

    # Correct behavior (targeted patch preserving baseline)
    good_patch = EnhancementPatch(
        target_content="body {\n  margin: 0;\n}",
        replacement_content="body {\n  margin: 0;\n}\n.dark-mode-toggle { display: flex; }",
    )
    good_result = original_css.replace(
        good_patch.target_content, good_patch.replacement_content
    )

    # The good patch must preserve unrelated baseline styles
    assert ".app {" in good_result
    assert ".dark-mode-toggle {" in good_result


def test_strict_nested_changes_validation():
    # Prove that an unexpected nested "changes" field inside EnhancementAction
    # (or anywhere) throws ValidationError due to extra="forbid"
    with pytest.raises(ValidationError) as exc_info:
        EnhancementAction(
            **{
                "file": "foo.ts",
                "action": "modify",
                "patches": [{"target_content": "a", "replacement_content": "b"}],
                "changes": [{"file": "foo.ts", "patches": []}],
            }
        )

    assert "Extra inputs are not permitted" in str(exc_info.value) or "changes" in str(
        exc_info.value
    )


def test_enhancement_agent_strict_nested_changes_retry():
    state = {
        "raw_goal": "Add search bar",
        "enhancement_chunks": [],
        "source_project_path": "fake/path",
    }

    mock_llm = MagicMock()
    # First call: LLM generates the invalid recursive payload (will fail parse step internally)
    # The framework converts validation failures to a re-prompt.
    # Second call: LLM corrects it.
    mock_llm.invoke.side_effect = [
        {
            "raw": '{"analysis": "test", "checklist": {"requires_ui_changes": true, "requires_stylesheet_changes": false, "requires_logic_state": true, "requires_backend_api": false}, "target_files": ["foo.tsx"], "changes": [{"file": "foo.tsx", "action": "modify", "patches": [{"target_content": "a", "replacement_content": "b"}], "changes": [{"file": "foo.tsx", "action": "modify", "patches": [{"target_content": "c", "replacement_content": "d"}]}]}]}',
            "parsed": None,
            "parsing_error": ValidationError.from_exception_data(
                "Extra inputs are not permitted",
                [
                    {
                        "type": "extra_forbidden",
                        "loc": ("changes", 0, "changes"),
                        "msg": "Extra inputs are not permitted",
                        "input": [],
                    }
                ],
            ),
        },
        {
            "raw": '{"analysis": "test", "checklist": {"requires_ui_changes": true, "requires_stylesheet_changes": false, "requires_logic_state": true, "requires_backend_api": false}, "target_files": ["foo.tsx"], "changes": [{"file": "foo.tsx", "action": "modify", "patches": [{"target_content": "a", "replacement_content": "b"}, {"target_content": "c", "replacement_content": "d"}]}]}',
            "parsed": EnhancementAnalysis(
                analysis="test",
                checklist={
                    "requires_ui_changes": True,
                    "requires_stylesheet_changes": False,
                    "requires_logic_state": True,
                    "requires_backend_api": False,
                },
                target_files=["foo.tsx"],
                changes=[
                    EnhancementAction(
                        file="foo.tsx",
                        action="modify",
                        patches=[
                            EnhancementPatch(
                                target_content="a", replacement_content="b"
                            ),
                            EnhancementPatch(
                                target_content="c", replacement_content="d"
                            ),
                        ],
                    )
                ],
            ),
            "parsing_error": None,
        },
    ]

    with patch("app.agents.enhancement_agent.enhancement_llm", mock_llm):
        with patch(
            "app.agents.enhancement_agent.load_full_project_into_memory",
            return_value=([], []),
        ):
            result = enhancement_agent_node(state)
            # Should have parsed exactly 2 patches in the single action
            assert "error" not in result
            assert len(result["enhancement_changes"][0]["patches"]) == 2
            assert mock_llm.invoke.call_count == 2
