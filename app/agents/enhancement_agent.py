import os
import posixpath
import json
from typing import List
from app.state.schemas import GraphState, FileContent, GeneratedFiles
from app.prompts.enhancement import enhancement_prompt
from app.agents.llm import enhancement_llm


def load_retrieved_files(
    source_path: str, files_to_read: List[str]
) -> tuple[List[FileContent], List[FileContent]]:
    """Loads only explicitly retrieved file paths restricting aggressive context scaling limits natively."""
    b_files = []
    f_files = []

    for rel_path in set(files_to_read):
        filepath = os.path.normpath(os.path.join(source_path, rel_path))
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            normalized_rel = rel_path.replace("\\", "/")
            if normalized_rel.startswith("backend/"):
                b_files.append(FileContent(path=normalized_rel, content=content))
            else:
                f_files.append(FileContent(path=normalized_rel, content=content))
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
    try:
        print(f"Enhancement Analysis: {result.analysis}")
    except UnicodeEncodeError:
        print(
            f"Enhancement Analysis: {result.analysis.encode('utf-8', 'replace').decode('utf-8')}"
        )

    # Phase 3: We ONLY load the explicitly retrieved relevant files representing contextual deltas!
    files_to_read = state.get("enhancement_files_to_read", [])
    b_files, f_files = load_retrieved_files(source_path, files_to_read)

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
