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


def enhancement_agent_node(state: GraphState) -> GraphState:
    print("Running Enhancement Agent Node...")
    chunks = state.get("enhancement_chunks", [])
    source_path = state.get("source_project_path", "")

    prompt = enhancement_prompt.format(
        goal=state.get("raw_goal", ""), chunks=json.dumps(chunks, indent=2)
    )

    result = enhancement_llm.invoke(prompt)
    print(f"Enhancement Analysis: {result.analysis}")

    b_files, f_files = load_full_project_into_memory(source_path)

    safety_errors = []

    for change in result.changes:
        path = change.file.replace("\\\\", "/").replace("\\", "/")
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
                        for patch in change.patches:
                            if patch.target_content in f.content:
                                f.content = f.content.replace(
                                    patch.target_content, patch.replacement_content
                                )
                            else:
                                safety_errors.append(
                                    f"Patch target not found in {path}: {patch.target_content[:30]}..."
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
