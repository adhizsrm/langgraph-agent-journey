import os
import posixpath
import json
from typing import List
from app.state.schemas import GraphState, FileContent, GeneratedFiles
from app.prompts.enhancement import enhancement_prompt
from app.agents.llm import enhancement_llm


def load_full_project_into_memory(
    source_path: str,
) -> tuple[List[FileContent], List[FileContent]]:
    b_files = []
    f_files = []
    ignore_dirs = {"node_modules", ".git", "dist", "build", "venv", "__pycache__"}

    for root, dirs, files in os.walk(source_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            filepath = os.path.join(root, file)
            if not file.endswith(
                (
                    ".js",
                    ".jsx",
                    ".ts",
                    ".tsx",
                    ".json",
                    ".html",
                    ".css",
                    ".md",
                    ".env.example",
                )
            ):
                continue
            rel_path = os.path.relpath(filepath, source_path).replace("\\", "/")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                if rel_path.startswith("backend/"):
                    b_files.append(FileContent(path=rel_path, content=content))
                else:
                    f_files.append(FileContent(path=rel_path, content=content))
            except Exception:
                pass

    return b_files, f_files


def apply_patch_safely(source: str, target: str, replacement: str) -> str:
    """Applies a patch safely, falling back to a normalized string match if exact fails."""
    if target in source:
        if source.count(target) == 1:
            return source.replace(target, replacement)
        else:
            raise ValueError("Multiple exact matches found, ambiguous target")

    # Normalized search fallback
    import re

    tokens = re.split(r"(\s+)", target)
    if not tokens:
        raise ValueError("Empty target")

    regex_parts = []
    for token in tokens:
        if token == "":
            continue
        if token.strip():
            regex_parts.append(re.escape(token))
        else:
            regex_parts.append(r"\s+")

    pattern = re.compile("".join(regex_parts))
    matches = list(pattern.finditer(source))

    if len(matches) == 0:
        raise ValueError("Patch target not found (even normalized)")
    if len(matches) > 1:
        raise ValueError("Multiple normalized matches found, ambiguous target")

    start, end = matches[0].span()
    return source[:start] + replacement + source[end:]


def enhancement_agent_node(state: GraphState) -> GraphState:
    print("Running Enhancement Agent Node...")
    chunks = state.get("enhancement_chunks", [])
    source_path = state.get("source_project_path", "")

    prompt = enhancement_prompt.format(
        goal=state.get("raw_goal", ""), chunks=json.dumps(chunks, indent=2)
    )

    max_retries = 3
    result = None
    original_prompt = prompt

    for attempt in range(max_retries):
        try:
            raw_result = enhancement_llm.invoke(prompt)
            with open("forensic_llm_dump.txt", "a", encoding="utf-8") as f:
                f.write(
                    f"\n--- ATTEMPT {attempt + 1} ---\n{json.dumps(raw_result, indent=2, default=str)}\n"
                )
        except Exception as e:
            return {"error": f"LLM invocation failure: {str(e)}"}

        if raw_result.get("parsing_error"):
            err = raw_result["parsing_error"]
            if attempt == max_retries - 1:
                return {
                    "error": f"LLM structured output validation failed repeatedly: {str(err)}"
                }

            raw_output = raw_result.get("raw", "")
            prompt = (
                original_prompt
                + f"\n\nYour previous output failed structured validation. Here is the previous output and the validation error. Correct the previous output and return a complete replacement EnhancementAnalysis matching the schema. Do not return a partial object.\n\nPrevious Output:\n{raw_output}\n\nValidation Error:\n{str(err)}"
            )
            continue

        result = raw_result.get("parsed")
        if result is None:
            return {
                "error": "structured-output parsing failure: Enhancement LLM returned None"
            }

        break

    b_files, f_files = load_full_project_into_memory(source_path)

    safety_errors = []
    from app.utils.path import resolve_patch_path

    for change in result.changes:
        try:
            path = resolve_patch_path(change.file, b_files + f_files)
        except ValueError as ve:
            safety_errors.append(str(ve))
            continue

        is_backend = path.startswith("backend/")
        target_list = b_files if is_backend else f_files
        found = False

        if change.action == "delete":
            target_list[:] = [f for f in target_list if f.path != path]
        elif change.action == "create":
            target_list.append(FileContent(path=path, content=change.content or ""))
        elif change.action == "modify":
            for f in target_list:
                if f.path == path:
                    found = True
                    if change.patches:
                        updated_content = f.content
                        action_success = True
                        for patch in change.patches:
                            try:
                                updated_content = apply_patch_safely(
                                    updated_content,
                                    patch.target_content,
                                    patch.replacement_content,
                                )
                            except ValueError as e:
                                action_success = False
                                safety_errors.append(
                                    f"{str(e)} in {path}: {patch.target_content[:30]}..."
                                )
                        if action_success and updated_content != f.content:
                            f.content = updated_content
                        elif action_success and updated_content == f.content:
                            # It's an effective no-op, shouldn't happen with strict validator but guard nevertheless
                            safety_errors.append(
                                f"Action parsed but produced no changes in {path}"
                            )
                    break
            if not found:
                safety_errors.append(
                    f"Target file for modification not found structurally: {path}"
                )

    return {
        "backend_files": GeneratedFiles(files=b_files),
        "frontend_files": GeneratedFiles(files=f_files),
        "safety_errors": safety_errors if safety_errors else None,
        "enhancement_changes": [c.model_dump() for c in result.changes],
    }
