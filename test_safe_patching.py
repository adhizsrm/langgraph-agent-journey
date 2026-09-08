import os
import shutil
import tempfile
import pytest
from app.state.schemas import FileContent
from app.tools.patch_engine import validate_and_apply_patches
from app.workspace.manager import create_temp_enhancement_workspace


def test_valid_modify():
    b_files = [FileContent(path="backend/src/users.js", content="original content")]
    f_files = []
    actions = [
        {"action": "modify", "file": "backend/src/users.js", "content": "new content"}
    ]

    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions
    )
    assert success is True
    assert new_b[0].content == "new content"
    assert res["applied"] == ["backend/src/users.js"]


def test_valid_create():
    b_files = []
    f_files = []
    actions = [
        {"action": "create", "file": "backend/src/auth.js", "content": "auth setup"}
    ]

    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions
    )
    assert success is True
    assert len(new_b) == 1
    assert new_b[0].path == "backend/src/auth.js"
    assert new_b[0].content == "auth setup"


def test_valid_delete():
    b_files = [FileContent(path="backend/src/legacy.js", content="old code")]
    f_files = []
    actions = [{"action": "delete", "file": "backend/src/legacy.js"}]

    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions
    )
    assert success is True
    assert len(new_b) == 0
    assert res["deleted"] == ["backend/src/legacy.js"]


def test_missing_modify():
    b_files = []
    f_files = []
    actions = [
        {"action": "modify", "file": "backend/src/missing.js", "content": "missing"}
    ]

    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions
    )
    assert success is False
    assert "Target missing for modify" in msg


def test_create_existing():
    b_files = [FileContent(path="backend/src/users.js", content="existing")]
    f_files = []
    actions = [{"action": "create", "file": "backend/src/users.js", "content": "new"}]

    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions
    )
    assert success is False
    assert "Target already exists for create" in msg


def test_path_traversal():
    b_files = []
    f_files = []
    actions = [{"action": "create", "file": "../outside.js", "content": "hello"}]

    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions
    )
    assert success is False
    assert "Invalid path traversal" in msg


def test_absolute_path_escape():
    b_files = []
    f_files = []
    actions = [{"action": "create", "file": "/etc/shadow", "content": "hello"}]
    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions
    )
    assert success is False
    assert "Invalid path traversal" in msg


def test_delete_modify_conflict():
    b_files = [FileContent(path="backend/src/users.js", content="old code")]
    f_files = []
    actions = [
        {"action": "delete", "file": "backend/src/users.js"},
        {"action": "modify", "file": "backend/src/users.js", "content": "new"},
    ]

    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions
    )
    assert success is False
    assert "Duplicate or conflicting actions" in msg


def test_duplicate_modify_conflict():
    b_files = [FileContent(path="backend/src/users.js", content="old code")]
    f_files = []
    actions = [
        {"action": "modify", "file": "backend/src/users.js", "content": "new 1"},
        {"action": "modify", "file": "backend/src/users.js", "content": "new 2"},
    ]

    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions
    )
    assert success is False
    assert "Duplicate or conflicting actions" in msg


def test_atomic_validation():
    b_files = [FileContent(path="backend/src/valid.js", content="ok")]
    f_files = []
    actions = [
        {"action": "modify", "file": "backend/src/valid.js", "content": "updated"},
        {
            "action": "modify",
            "file": "backend/src/invalid_missing.js",
            "content": "fail",
        },
    ]

    # Must reject ALL actions without modifying anything
    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions
    )
    assert success is False
    # Verifying atomic rollback: original un-mutated objects remain untouched
    assert b_files[0].content == "ok"
    assert new_b[0].content == "ok"


def test_original_project_remains_untouched():
    source = tempfile.mkdtemp()
    target = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(source, "backend/src"), exist_ok=True)
        with open(os.path.join(source, "backend/src/users.js"), "w") as f:
            f.write("original source file")

        b_files = [
            FileContent(path="backend/src/users.js", content="original source file")
        ]
        f_files = []
        actions = [
            {
                "action": "modify",
                "file": "backend/src/users.js",
                "content": "modified in memory workspace",
            }
        ]

        new_b, new_f, res, success, msg = validate_and_apply_patches(
            b_files, f_files, actions
        )

        with open(os.path.join(source, "backend/src/users.js"), "r") as f:
            disk_content = f.read()

        assert disk_content == "original source file"
        assert new_b[0].content == "modified in memory workspace"
    finally:
        shutil.rmtree(source, ignore_errors=True)
        shutil.rmtree(target, ignore_errors=True)


def test_delete_preserved_through_workspace():
    source = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(source, "backend/src"), exist_ok=True)
        with open(os.path.join(source, "backend/src/old.js"), "w") as f:
            f.write("delete me")
        with open(os.path.join(source, "backend/src/new.js"), "w") as f:
            f.write("keep me")

        b_files = [
            FileContent(path="backend/src/old.js", content="delete me"),
            FileContent(path="backend/src/new.js", content="keep me"),
        ]
        f_files = []

        actions = [{"action": "delete", "file": "backend/src/old.js"}]
        new_b, new_f, res, success, msg = validate_and_apply_patches(
            b_files, f_files, actions
        )

        workspace_path, written, err = create_temp_enhancement_workspace(
            source, new_b, new_f, res.get("deleted", [])
        )

        assert not os.path.exists(os.path.join(workspace_path, "backend/src/old.js"))
        assert os.path.exists(os.path.join(workspace_path, "backend/src/new.js"))

    finally:
        shutil.rmtree(source, ignore_errors=True)


def test_sibling_directory_prefix_vulnerability():
    b_files = [FileContent(path="backend/src/users.js", content="ok")]
    f_files = []

    # Attempting to access `workspace_evil` when the override is `workspace`
    actions = [
        {
            "action": "create",
            "file": "../workspace_evil/malicious.js",
            "content": "evil payload",
        }
    ]

    new_b, new_f, res, success, msg = validate_and_apply_patches(
        b_files, f_files, actions, workspace_path_override="/mock/workspace"
    )

    assert success is False
    assert (
        "Path escape outside workspace" in msg or "Invalid path traversal syntax" in msg
    )
