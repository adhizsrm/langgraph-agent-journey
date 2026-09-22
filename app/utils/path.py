import posixpath
from typing import List
from app.state.schemas import FileContent


def resolve_patch_path(raw_path: str, context_files: List[FileContent]) -> str:
    """
    Normalizes and resolves a raw LLM patch path against known workspace project context.
    """
    path = raw_path.replace("\\", "/").replace("//", "/")

    if path.startswith("/"):
        path = path.lstrip("/")

    if path.startswith("backend/") or path.startswith("frontend/"):
        return posixpath.normpath(path)

    if path.startswith("./") or path.startswith("../"):
        search_str_dq = f'"{path}"'
        search_str_sq = f"'{path}'"

        for f in context_files:
            if search_str_dq in f.content or search_str_sq in f.content:
                dir_name = posixpath.dirname(f.path)
                resolved = posixpath.normpath(posixpath.join(dir_name, path))

                if not (
                    resolved.startswith("backend/") or resolved.startswith("frontend/")
                ):
                    raise ValueError(
                        f"Path escape attempt: resolved path '{resolved}' is outside project root limits."
                    )
                return resolved

        raise ValueError(
            f"Cannot resolve relative path '{path}' safely. No existing context file explicitly imports or references it."
        )

    raise ValueError(
        f"Unsafe path format '{path}'. Must be properly canonical (frontend/... or backend/...) or explicitly relative (./...) with a valid context reference."
    )
