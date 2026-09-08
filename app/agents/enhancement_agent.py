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

    # Phase 3/5: We ONLY load explicitly retrieved context restricting boundaries, generating declarative patches safely!
    files_to_read = state.get("enhancement_files_to_read", [])
    b_files, f_files = load_retrieved_files(source_path, files_to_read)

    return {
        "backend_files": GeneratedFiles(files=b_files),
        "frontend_files": GeneratedFiles(files=f_files),
        "pending_patches": [c.model_dump() for c in result.changes],
    }
