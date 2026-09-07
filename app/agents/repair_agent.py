import json
import os
from app.state.schemas import (
    GraphState,
    GeneratedFiles,
    OrchestratorOutput,
    FileContent,
)
from app.agents.llm import repair_llm, enhancement_llm
from app.prompts.repair import repair_prompt


def project_repair_node(state: GraphState) -> GraphState:
    print("Running Project Repair Agent...")
    attempts = state.get("repair_attempts", 0) + 1
    print(f"Repair attempt {attempts}/3")

    validation_errs = state.get("validation_errors", [])
    exec_res = state.get("execution_result", {})
    safety_errors = state.get("safety_errors", [])
    history = state.get("repair_history", [])

    b_files = state.get("backend_files", GeneratedFiles(files=[]))
    f_files = state.get("frontend_files", GeneratedFiles(files=[]))

    b_file_list = b_files.files
    f_file_list = f_files.files

    mode = state.get("mode", "create")
    all_errs = []
    if validation_errs:
        all_errs.extend(validation_errs)
    if safety_errors:
        all_errs.extend(safety_errors)

    error_text = json.dumps(all_errs) + json.dumps(exec_res)

    # 1. Select precisely relevant files avoiding Full Project Token Bloat
    relevant_files = []
    included_paths = set()

    if mode == "enhance":
        enhancement_changes = state.get("enhancement_changes", [])
        for c in enhancement_changes:
            path = c.get("file", "").replace("\\", "/")
            included_paths.add(path)
    else:
        # Create mode project footprints are traditionally tiny, but we still secure them
        for f in b_file_list + f_file_list:
            included_paths.add(f.path)

    # Include specific untargeted files if their filenames natively appear in the error trace!
    for f in b_file_list + f_file_list:
        if f.path not in included_paths:
            basename = os.path.basename(f.path)
            # basic heuristic checks
            if basename in error_text:
                included_paths.add(f.path)

    for path in included_paths:
        is_backend = path.startswith("backend/")
        target_group = b_file_list if is_backend else f_file_list
        for f in target_group:
            if f.path == path:
                relevant_files.append({"path": path, "content": f.content})
                break

    # 2. Hard Byte/Token Guard Limit (Tokens ~ chars/4, 30k = ~120k chars limit)
    char_limit = 100000
    current_chars = 0
    final_files = []

    for f_obj in relevant_files:
        content = f_obj["content"]
        if len(content) > 30000:
            content = (
                content[:15000] + "\n...[CONTENT TRUNCATED]...\n" + content[-15000:]
            )

        added_len = len(f_obj["path"]) + len(content)
        if current_chars + added_len > char_limit:
            break
        final_files.append({"path": f_obj["path"], "content": content})
        current_chars += added_len

    files_str = "RELEVANT FILES LOCATED:\n" + json.dumps(final_files, indent=2)

    modified_paths = []

    if mode == "enhance":
        # Pull original logic through identical enhancement patches structure
        print(" -> Detected Enhancement Iteration Mode. Applying patch constraints.")
        from app.prompts.enhancement import enhancement_prompt

        # Format a dynamic goal appending the explicit errors
        attempted_changes = state.get("enhancement_changes", [])

        dynamic_goal = (
            f"Original Goal: {state.get('raw_goal', '')}\n\n"
            f"Previous Attempted Changes: {json.dumps(attempted_changes, indent=2)}\n\n"
            f"WARNING: The following structural/safety/execution errors occurred on your attempt:\n{json.dumps(all_errs, indent=2)}\n{json.dumps(exec_res, indent=2)}\n\n"
            f"Please strictly fix these errors inside the target files using exact patch formatting. Do NOT regenerate unmodified large files!"
        )

        prompt = enhancement_prompt.format(goal=dynamic_goal, chunks=files_str)

        result = enhancement_llm.invoke(prompt)
        try:
            print(f"Repair Analysis (Patch Mode): {result.analysis}")
        except Exception:
            print(
                f"Repair Analysis (Patch Mode): [Output contained invalid characters and was skipped in console]"
            )

        for change in result.changes:
            path = change.file.replace("\\\\", "/")
            modified_paths.append(path)
            is_backend = path.startswith("backend/")
            target_list = b_file_list if is_backend else f_file_list
            found = False

            if change.action == "delete":
                if is_backend:
                    b_file_list = [f for f in b_file_list if f.path != path]
                else:
                    f_file_list = [f for f in f_file_list if f.path != path]
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
                        break
                if not found:
                    target_list.append(
                        FileContent(path=path, content=change.content or "")
                    )

    else:
        # Prevent context bloat by passing only the freshest repair attempt history
        focused_history = []
        if history:
            focused_history.append(
                {
                    "attempt": history[-1].get("attempt"),
                    "errors": history[-1].get("errors"),
                    "analysis": history[-1].get("analysis"),
                }
            )

        prompt = repair_prompt.format(
            goal=state.get("raw_goal", ""),
            spec=state.get(
                "orchestrator_spec",
                OrchestratorOutput(
                    entity_spec={"entity_name": "", "fields": {}},
                    crud_operations=[],
                    api_contract={"base_route": "", "operations": []},
                    execution_order="backend_first",
                    file_locations={},
                ),
            ).model_dump_json(indent=2),
            validation_errors=json.dumps(all_errs, indent=2),
            execution_result=json.dumps(exec_res, indent=2),
            history=json.dumps(focused_history, indent=2),
            files=files_str,
        )

        result = repair_llm.invoke(prompt)
        try:
            print(f"Repair Analysis: {result.analysis}")
        except Exception:
            print(
                f"Repair Analysis: [Output contained invalid characters and was skipped in console]"
            )

        for change in result.changes:
            path = change.file.replace("\\\\", "/")
            modified_paths.append(path)
            is_backend = path.startswith("backend/")

            target_list = b_file_list if is_backend else f_file_list
            found = False

            if change.action == "delete":
                if is_backend:
                    b_file_list = [f for f in b_file_list if f.path != path]
                else:
                    f_file_list = [f for f in f_file_list if f.path != path]
            elif change.action == "modify":
                for f in target_list:
                    if f.path == path:
                        f.content = change.content
                        found = True
                        break
                if not found:
                    target_list.append(FileContent(path=path, content=change.content))
            elif change.action == "create":
                target_list.append(FileContent(path=path, content=change.content))

    new_hist = {
        "attempt": attempts,
        "source": (
            "safety/validator" if validation_errs or safety_errors else "executor"
        ),
        "errors": all_errs if all_errs else exec_res.get("errors", []),
        "files_changed": modified_paths,
        "analysis": result.analysis,
        "result": "applied",
    }
    history.append(new_hist)

    return {
        "repair_attempts": attempts,
        "repair_history": history,
        "backend_files": GeneratedFiles(files=b_file_list),
        "frontend_files": GeneratedFiles(files=f_file_list),
        "validation_errors": None,
        "execution_result": None,
        "safety_errors": None,
    }
