import os
import shutil
import uuid
import posixpath
from typing import List, Tuple
from app.state.schemas import FileContent


def create_temp_workspace(
    backend_files: List[FileContent], frontend_files: List[FileContent]
) -> Tuple[str, List[str], str]:
    """Returns workspace_path, written_files, and an error if there was one."""
    workspace_id = str(uuid.uuid4())[:8]
    workspace_path = posixpath.join("workspace", f"run_{workspace_id}")

    all_files = backend_files + frontend_files
    written_files = []
    error = None

    try:
        for f in all_files:
            full_path = posixpath.join(workspace_path, f.path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as out:
                out.write(f.content)
            written_files.append(full_path)
    except Exception as e:
        error = f"Failed to write files to temp workspace: {str(e)}"

    return workspace_path, written_files, error


def create_temp_enhancement_workspace(
    source_path: str,
    backend_files: List[FileContent],
    frontend_files: List[FileContent],
    enhancement_changes: List[dict] = None,
) -> Tuple[str, List[str], str]:
    workspace_id = str(uuid.uuid4())[:8]
    workspace_path = posixpath.join("workspace", f"run_{workspace_id}")
    written_files = []
    error = None

    if enhancement_changes is None:
        enhancement_changes = []

    try:
        # Fork original workspace
        shutil.copytree(source_path, workspace_path, dirs_exist_ok=True)
        # Apply modified in-memory state on top of the workspace (covers modifies/creates)
        all_files = backend_files + frontend_files
        for f in all_files:
            full_path = posixpath.join(workspace_path, f.path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as out:
                out.write(f.content)
            written_files.append(full_path)

        # Handle removals
        for change in enhancement_changes:
            if change.get("action") == "delete":
                target_path = posixpath.join(
                    workspace_path, change.get("file", "").replace("\\", "/")
                )
                if os.path.exists(target_path):
                    os.remove(target_path)
    except Exception as e:
        error = f"Failed to setup enhancement temp workspace: {str(e)}"

    return workspace_path, written_files, error


def cleanup_workspace(workspace_path: str) -> None:
    if workspace_path and os.path.exists(workspace_path):
        try:
            shutil.rmtree(workspace_path)
        except Exception as e:
            print(f"Cleanup warning: {e}")
