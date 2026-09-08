import os
from typing import List, Dict, Any, Tuple
from app.state.schemas import FileContent


def validate_and_apply_patches(
    b_files: List[FileContent],
    f_files: List[FileContent],
    actions: List[Dict[str, Any]],
    workspace_path_override: str = "",  # just for testing constraints if needed, but not required
) -> Tuple[List[FileContent], List[FileContent], Dict[str, Any], bool, str]:

    if not actions:
        return (
            b_files,
            f_files,
            {"applied": [], "created": [], "deleted": [], "errors": []},
            True,
            "",
        )

    # Deepcopy to guarantee atomic rollback if mid-flight validations or replacements fail
    new_b = [FileContent(path=f.path, content=f.content) for f in b_files]
    new_f = [FileContent(path=f.path, content=f.content) for f in f_files]

    seen_files = set()
    allowed_extensions = {
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".css",
        ".html",
        ".json",
        ".txt",
        ".md",
        ".env.example",
    }

    applied = []
    created = []
    deleted = []

    def _norm(p: str) -> str:
        return p.replace("\\\\", "/").replace("\\", "/")

    def _find_file(path: str) -> Tuple[List[FileContent], int]:
        for idx, f in enumerate(new_b):
            if _norm(f.path) == _norm(path):
                return (new_b, idx)
        for idx, f in enumerate(new_f):
            if _norm(f.path) == _norm(path):
                return (new_f, idx)
        return (None, -1)

    try:
        # Atomic Validation & Application!
        for action in actions:
            action_type = action.get("action")
            raw_path = action.get("file", "")
            rel_path = _norm(raw_path)

            # Conflict Detection
            if rel_path in seen_files:
                raise ValueError(f"Duplicate or conflicting actions for {rel_path}")
            seen_files.add(rel_path)

            # Path Traversal and Safety using robust standard pathlib containment
            import pathlib

            base_dir = (
                workspace_path_override
                if workspace_path_override
                else "/mock_sandbox_root"
            )
            base_root = pathlib.Path(base_dir).resolve()

            # Reject bare traversal operators locally to fail fast safely
            if ".." in rel_path or rel_path.startswith("/"):
                raise ValueError(f"Invalid path traversal syntax on {rel_path}")

            try:
                candidate_path = pathlib.Path(base_root, rel_path).resolve()
                candidate_path.relative_to(base_root)
            except ValueError:
                raise ValueError(f"Path escape outside workspace for {rel_path}")

            ext = os.path.splitext(rel_path)[1].lower()
            if ext and ext not in allowed_extensions:
                raise ValueError(f"File type {ext} not permitted for {rel_path}")

            target_list, idx = _find_file(rel_path)
            file_exists = target_list is not None

            # Semantics & Execution
            if action_type == "modify":
                if not file_exists:
                    raise ValueError(f"Target missing for modify: {rel_path}")

                text = target_list[idx].content
                patches = action.get("patches", [])

                if action.get("content") and not patches:
                    text = action.get("content")

                if patches:
                    for patch in patches:
                        target = patch.get("target_content", "")
                        replace = patch.get("replacement_content", "")
                        if target and target in text:
                            if text.count(target) > 1:
                                raise ValueError(
                                    f"Ambiguous patch target in {rel_path}: matched multiple times"
                                )
                            text = text.replace(target, replace)
                        else:
                            raise ValueError(f"Patch target not found in {rel_path}")

                target_list[idx].content = text
                applied.append(rel_path)

            elif action_type == "create":
                if file_exists:
                    raise ValueError(f"Target already exists for create: {rel_path}")
                content = action.get("content", "")
                if not isinstance(content, str):
                    raise ValueError(f"Content must be a string for create: {rel_path}")

                is_backend = rel_path.startswith("backend/")
                target_pool = new_b if is_backend else new_f
                target_pool.append(FileContent(path=rel_path, content=content))
                created.append(rel_path)

            elif action_type == "delete":
                if not file_exists:
                    raise ValueError(f"Target missing for delete: {rel_path}")
                target_list.pop(idx)
                deleted.append(rel_path)

            else:
                raise ValueError(f"Unrecognized action: {action_type}")

        return (
            new_b,
            new_f,
            {"applied": applied, "created": created, "deleted": deleted},
            True,
            "",
        )

    except Exception as e:
        # Rollback is instant because we just discard new_b and new_f!
        return (
            b_files,
            f_files,
            {
                "errors": [
                    f"Patch application failed mid-flight and rolled back: {str(e)}"
                ]
            },
            False,
            str(e),
        )
