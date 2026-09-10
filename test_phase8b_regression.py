import pytest
import os
from unittest.mock import patch, MagicMock

from app.graph.routing import route_safety
from app.agents.repair_agent import project_repair_node
from app.tools.patch_engine import validate_and_apply_patches
from app.state.schemas import FileContent, GeneratedFiles


class MockAction:
    def __init__(self, file: str, action: str, content: str = ""):
        self.file = file
        self.action = action
        self.content = content

    def model_dump(self):
        return {"file": self.file, "action": self.action, "content": self.content}


class MockResult:
    def __init__(self, analysis: str, changes: list):
        self.analysis = analysis
        self.changes = changes


def mock_repair_invoke(*args, **kwargs):
    return MockResult("Analysis", [MockAction("foo.txt", "modify", "hello")])


# ==========================================
# PART 7 A. Repair attempt limit
# ==========================================
def test_repair_attempt_limit_guard():
    with patch(
        "app.agents.repair_agent.repair_llm.invoke", side_effect=mock_repair_invoke
    ):

        # 0 -> allowed
        s0 = {
            "repair_attempts": 0,
            "backend_files": GeneratedFiles(files=[]),
            "frontend_files": GeneratedFiles(files=[]),
        }
        r0 = project_repair_node(s0)
        assert r0["repair_attempts"] == 1
        assert len(r0["pending_patches"]) == 1

        # 1 -> allowed
        s1 = {
            "repair_attempts": 1,
            "backend_files": GeneratedFiles(files=[]),
            "frontend_files": GeneratedFiles(files=[]),
        }
        r1 = project_repair_node(s1)
        assert r1["repair_attempts"] == 2

        # 2 -> allowed
        s2 = {
            "repair_attempts": 2,
            "backend_files": GeneratedFiles(files=[]),
            "frontend_files": GeneratedFiles(files=[]),
        }
        r2 = project_repair_node(s2)
        assert r2["repair_attempts"] == 3

        # 3 -> PROHIBITED (must never reach 4/3)
        s3 = {
            "repair_attempts": 3,
            "backend_files": GeneratedFiles(files=[]),
            "frontend_files": GeneratedFiles(files=[]),
        }
        r3 = project_repair_node(s3)
        assert r3["workflow_status"] == "FAILED"
        assert r3["repair_attempts"] == 3  # Strict 3/3 boundary
        assert r3["pending_patches"] == []  # Flushing stale state!


# ==========================================
# PART 7 B. Safety route limit
# ==========================================
def test_route_safety_limit():
    # safety_errors present, repair_attempts = 2 -> project_repair
    assert (
        route_safety({"safety_errors": ["Error!"], "repair_attempts": 2})
        == "project_repair"
    )

    # safety_errors present, repair_attempts = 3 -> cleanup_failed_project
    assert (
        route_safety({"safety_errors": ["Error!"], "repair_attempts": 3})
        == "cleanup_failed_project"
    )

    # No safety_errors -> validate_generated_project
    assert (
        route_safety({"safety_errors": [], "repair_attempts": 2})
        == "validate_generated_project"
    )


# ==========================================
# PART 7 C. Repeated error termination
# ==========================================
def test_repeated_error_termination():
    with patch(
        "app.agents.repair_agent.repair_llm.invoke", side_effect=mock_repair_invoke
    ):
        state = {
            "repair_attempts": 2,  # Need attempts > 1 and history
            "safety_errors": ["Syntax Error in auth.js"],
            "repair_history": [
                {
                    "attempt": 1,
                    "errors": ["Syntax Error in auth.js"],
                    "analysis": "Fixing it",
                }
            ],
            "backend_files": GeneratedFiles(files=[]),
            "frontend_files": GeneratedFiles(files=[]),
        }
        res = project_repair_node(state)
        # Should abort before calling LLM
        assert res["workflow_status"] == "FAILED"
        assert res["error"].startswith(
            "FINAL FAILURE: Repair loop detected lack of progress."
        )
        assert res["pending_patches"] == []  # Verify patches are cleared!
        # Safety node would receive empty patches returning {}, routing nicely to validation


# ==========================================
# PART 7 D. Existing-file manifest
# ==========================================
def test_existing_file_manifest():
    # Setup mock backend files
    b_files = GeneratedFiles(
        files=[
            FileContent(
                path="backend/routes/todo.js",
                content="const service = require('../services/todoService');",
            ),
            FileContent(
                path="backend/services/todoService.js", content="module.exports = {};"
            ),
        ]
    )

    state = {
        "mode": "create",
        "repair_attempts": 0,
        "validation_errors": [
            "Cannot find module '../services/todoService'"
        ],  # Mock error targeting top file
        "backend_files": b_files,
        "frontend_files": GeneratedFiles(files=[]),
    }

    with patch("app.agents.repair_agent.repair_llm.invoke") as mock_invoke:
        mock_invoke.return_value = MockResult("A", [])
        project_repair_node(state)

        args = mock_invoke.call_args[0][0]  # Get formatted prompt

        # Verify Manifest
        assert "EXISTING PROJECT FILES" in args
        assert "backend/routes/todo.js" in args
        assert "backend/services/todoService.js" in args

        # We also need to verify bounded source context works
        assert "RELEVANT REPAIR CONTEXT" in args


# ==========================================
# PART 7 E. Patch engine behavior
# ==========================================
def test_patch_engine_behavior():
    source_b = [FileContent(path="backend/existing.js", content="hello")]
    source_f = []

    # CREATE existing -> conflict
    _, _, res_ce, succ_ce, msg_ce = validate_and_apply_patches(
        source_b,
        source_f,
        [{"file": "backend/existing.js", "action": "create", "content": "world"}],
    )
    assert not succ_ce
    assert "Target already exists for create" in msg_ce

    # CREATE missing -> success
    _, _, res_cm, succ_cm, msg_cm = validate_and_apply_patches(
        source_b,
        source_f,
        [{"file": "backend/missing.js", "action": "create", "content": "world"}],
    )
    assert succ_cm
    assert "backend/missing.js" in res_cm["created"]

    # MODIFY existing -> success
    _, _, res_me, succ_me, msg_me = validate_and_apply_patches(
        source_b,
        source_f,
        [{"file": "backend/existing.js", "action": "modify", "content": "world"}],
    )
    assert succ_me
    assert "backend/existing.js" in res_me["applied"]

    # MODIFY missing -> conflict
    _, _, res_mm, succ_mm, msg_mm = validate_and_apply_patches(
        source_b,
        source_f,
        [{"file": "backend/missing.js", "action": "modify", "content": "world"}],
    )
    assert not succ_mm
    assert "Target missing for modify" in msg_mm

    # DELETE existing -> success
    _, _, res_de, succ_de, msg_de = validate_and_apply_patches(
        source_b, source_f, [{"file": "backend/existing.js", "action": "delete"}]
    )
    assert succ_de
    assert "backend/existing.js" in res_de["deleted"]

    # DELETE missing -> conflict
    _, _, res_dm, succ_dm, msg_dm = validate_and_apply_patches(
        source_b, source_f, [{"file": "backend/missing.js", "action": "delete"}]
    )
    assert not succ_dm
    assert "Target missing for delete" in msg_dm
