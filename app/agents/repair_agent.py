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

    raw_attempts = state.get("repair_attempts", 0)
    if raw_attempts >= 3:
        print(
            "Defensive Guard: Repair limit (3) exceeded inside repair node. Aborting."
        )
        return {
            "error": "Defensive Guard: Max repair attempts reached natively.",
            "workflow_status": "FAILED",
            "repair_attempts": raw_attempts,
            "pending_patches": [],  # Flush stale states rigorously mapping terminal edges securely!
        }

    attempts = raw_attempts + 1
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

    # Detect lack of repair progress (repeated identical errors)
    if history and attempts > 1:
        last_errors = history[-1].get("errors", [])
        if sorted(all_errs) == sorted(last_errors):
            return {
                "error": "FINAL FAILURE: Repair loop detected lack of progress. The identical validation errors persisted after repair.",
                "workflow_status": "FAILED",
                "repair_attempts": raw_attempts,
                "backend_files": GeneratedFiles(files=b_file_list),
                "frontend_files": GeneratedFiles(files=f_file_list),
                "validation_errors": None,
                "execution_result": None,
                "safety_errors": None,
                "pending_patches": [],
            }

    error_text = json.dumps(all_errs) + json.dumps(exec_res)

    # 1. Extract specifically targeted error files dynamically
    error_files = set()
    file_map = {f.path: f.content for f in b_file_list + f_file_list}
    path_list = list(file_map.keys())

    for p in path_list:
        if p in error_text:
            error_files.add(p)

    # Include fallback boundaries identifying creation files
    if not error_files and mode == "enhance":
        for c in state.get("enhancement_changes", []):
            if c.get("file"):
                error_files.add(c.get("file").replace("\\", "/"))
    elif not error_files and mode == "create":
        error_files = set(path_list)

    # 2. Build Dependency Graph across exact bounds
    from app.tools.dependency_graph import build_repository_dependency_graph

    workspace_path = state.get("workspace_path", "")
    graph = build_repository_dependency_graph(path_list, workspace_path, file_map)

    # 3. Pull Impact Traces!
    dependent_context = set(error_files)
    if workspace_path:  # Ensure tree checks match explicit roots
        for ef in error_files:
            # Add files determining direct implementations AND direct dependencies natively
            dependent_context.update(graph.get_forward_dependencies({ef}, max_depth=1))
            dependent_context.update(graph.get_reverse_dependencies({ef}, max_depth=1))

    # 4. Topological Prioritization (Dependencies Before Dependents)
    def count_forward_deps(path):
        return len(graph.get_forward_dependencies({path}, max_depth=5))

    ordered_paths = sorted(list(dependent_context), key=lambda x: count_forward_deps(x))

    # 5. Handle Package Contradictions
    # If standard validation complains about missing dependencies natively present in package.json!
    package_json = file_map.get("frontend/package.json", "") + file_map.get(
        "backend/package.json", ""
    )
    package_metadata_override = ""
    if "Cannot find module" in error_text or "Missing" in error_text:
        # We explicitly surface this paradox safely!
        package_metadata_override = "\n\n[PACKAGE DEPENDENCY NOTE: Ensure dependency mismatches evaluate physical package.json values! Check versions natively!]"

    # 6. Hard Byte/Token Guard Limit (Tokens ~ chars/4, 30k = ~120k chars limit)
    char_limit = 100000
    current_chars = 0
    final_files = []

    for path in ordered_paths:
        if path not in file_map:
            continue
        content = file_map[path]
        if len(content) > 30000:
            content = (
                content[:15000] + "\n...[CONTENT TRUNCATED]...\n" + content[-15000:]
            )

        added_len = len(path) + len(content)
        if current_chars + added_len > char_limit:
            break
        final_files.append({"path": path, "content": content})
        current_chars += added_len

    manifest_str = "\n".join(sorted(path_list))
    files_str = (
        "RELEVANT REPAIR CONTEXT (ORDERED ROOT-CAUSE DEPENDENCIES FIRST):\n"
        + json.dumps(final_files, indent=2)
        + package_metadata_override
        + "\n\nEXISTING PROJECT FILES:\n"
        + manifest_str
    )

    modified_paths = []

    def _norm(p: str) -> str:
        return p.replace("frontend/", "").replace("backend/", "").strip("/")

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

    repair_metrics = {
        "repair_error_count": (
            len(all_errs) if all_errs else len(exec_res.get("errors", []))
        ),
        "repair_context_files": len(final_files),
        "repair_direct_files": len(error_files),
        "repair_dependency_files": len(dependent_context) - len(error_files),
        "repair_patch_count": len(result.changes),
    }

    return {
        "repair_attempts": attempts,
        "repair_history": history,
        "backend_files": GeneratedFiles(files=b_file_list),
        "frontend_files": GeneratedFiles(files=f_file_list),
        "validation_errors": None,
        "execution_result": None,
        "safety_errors": None,
        "pending_patches": [c.model_dump() for c in result.changes],
        "repair_metrics": repair_metrics,
    }
