import os
from typing import List
from app.state.schemas import GraphState, FileContent


def _count_lines(files: List[FileContent]) -> int:
    return sum(len(f.content.splitlines()) for f in files)


def project_safety_node(state: GraphState) -> GraphState:
    print("Running Project Safety Evaluation Node...")

    mode = state.get("mode", "create")
    if mode != "enhance":
        return {}  # Only matters for enhancements where drop off threatens destruction

    source_path = state.get("source_project_path", "")
    if not source_path:
        return {}

    b_files = state.get("backend_files")
    f_files = state.get("frontend_files")
    if not b_files or not f_files:
        return {}

    # Gather original files layout
    from app.agents.enhancement_agent import load_full_project_into_memory

    orig_b, orig_f = load_full_project_into_memory(source_path)

    original_lines = _count_lines(orig_b) + _count_lines(orig_f)
    new_lines = _count_lines(b_files.files) + _count_lines(f_files.files)

    safety_errors = state.get("safety_errors", []) or []

    # Check overall line reduction
    if original_lines > 0:
        ratio = new_lines / original_lines
        if ratio < 0.85:
            safety_errors.append(
                f"Destruction Safety Triggered: Projected workspace dropped massive line counts ({(1-ratio)*100:.1f}% reduction). The Agent erased functionality."
            )

    # Check if a critical file suddenly dropped entirely without 'delete' instruction context (e.g. LLM failure)
    orig_names = set(f.path for f in orig_b + orig_f)
    new_names = set(f.path for f in b_files.files + f_files.files)

    missing = orig_names - new_names
    for m in missing:
        safety_errors.append(
            f"Destruction Safety Triggered: Component '{m}' was unexpectedly wiped from the codebase."
        )

    if safety_errors:
        return {"safety_errors": safety_errors}

    return {}
