import json
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
    safety_errors = list(state.get("safety_errors", []) or [])
    history = state.get("repair_history", [])

    b_files = state.get("backend_files", GeneratedFiles(files=[]))
    f_files = state.get("frontend_files", GeneratedFiles(files=[]))

    b_file_list = b_files.files
    f_file_list = f_files.files

    files_str = (
        "BACKEND FILES:\n"
        + b_files.model_dump_json(indent=2)
        + "\nFRONTEND FILES:\n"
        + f_files.model_dump_json(indent=2)
    )

    all_errs = []
    if validation_errs:
        all_errs.extend(validation_errs)
    if safety_errors:
        all_errs.extend(safety_errors)

    mode = state.get("mode", "create")
    modified_paths = []

    if mode == "enhance":
        # Pull original logic through identical enhancement patches structure
        print(" -> Detected Enhancement Iteration Mode. Applying patch constraints.")
        from app.prompts.enhancement import enhancement_prompt

        # Format a dynamic goal appending the explicit errors
        dynamic_goal = (
            "CRITICAL REPAIR TASK: You are evaluating a broken patch injection.\n"
            "The baseline project implementation for the user request was already applied, but it failed compilation/validation.\n"
            "DO NOT infer a new architectural/API change. The conceptual feature logic exists in the files.\n"
            f"Original Feature Request (for context only): {state.get('raw_goal', '')}\n\n"
            "You MUST prioritize the following concrete compiler trace/syntax errors over architectural speculation.\n"
            "If the validator provides a concrete syntax/type error in a specific file, repair that specific error first.\n"
            "Review the current exact file content to find the overlapping/duplicate JSX lines or import failures.\n"
            "Do not modify unrelated areas like `api.ts` merely because the feature involves data.\n"
            f"Validation Errors / Traceback:\n{json.dumps(all_errs, indent=2)}\n"
            f"Execution Logs:\n{json.dumps(exec_res, indent=2)}\n\n"
            "REPAIR INSTRUCTION:\n"
            "Output localized patches that ONLY resolve these exact compiler routing errors without re-implementing the parent feature."
        )

        prompt = enhancement_prompt.format(
            goal=dynamic_goal,
            chunks=files_str,
        )

        max_retries = 3
        result = None
        original_prompt = prompt

        for attempt in range(max_retries):
            raw_result = enhancement_llm.invoke(prompt)

            if isinstance(raw_result, dict) and raw_result.get("parsing_error"):
                err = raw_result["parsing_error"]

                if attempt == max_retries - 1:
                    raise ValueError(
                        f"LLM structured output validation failed repeatedly: {str(err)}"
                    )

                raw_output = raw_result.get("raw", "")
                prompt = (
                    original_prompt
                    + "\n\nYour previous output failed structured validation. "
                    "Here is the previous output and the validation error. "
                    "Correct the previous output and return a complete replacement "
                    "EnhancementAnalysis matching the schema. Do not return a partial object."
                    + f"\n\nPrevious Output:\n{raw_output}"
                    + f"\n\nValidation Error:\n{str(err)}"
                )
                continue

            result = (
                raw_result.get("parsed") if isinstance(raw_result, dict) else raw_result
            )

            if result is None:
                raise ValueError(
                    "structured-output parsing failure: Enhancement LLM returned None"
                )

            break

        print(f"Repair Analysis (Patch Mode): {result.analysis}")

        from app.utils.path import resolve_patch_path

        for change in result.changes:
            try:
                path = resolve_patch_path(
                    change.file,
                    b_file_list + f_file_list,
                )
            except ValueError as ve:
                error_message = f"Path Resolution Error: {ve}"
                print(error_message)
                safety_errors.append(error_message)
                continue

            is_backend = path.startswith("backend/")
            target_list = b_file_list if is_backend else f_file_list
            found = False

            if change.action == "delete":
                file_exists = any(f.path == path for f in target_list)

                if not file_exists:
                    safety_errors.append(f"File not found for delete operation: {path}")
                    continue

                if is_backend:
                    b_file_list = [f for f in b_file_list if f.path != path]
                else:
                    f_file_list = [f for f in f_file_list if f.path != path]

                if path not in modified_paths:
                    modified_paths.append(path)

            elif change.action == "create":
                if any(f.path == path for f in target_list):
                    safety_errors.append(
                        f"File already exists for create operation: {path}"
                    )
                    continue

                target_list.append(
                    FileContent(
                        path=path,
                        content=change.content or "",
                    )
                )

                if path not in modified_paths:
                    modified_paths.append(path)

            elif change.action == "modify":
                for f in target_list:
                    if f.path != path:
                        continue

                    found = True

                    if not change.patches:
                        safety_errors.append(
                            f"No patches provided for modify operation: {path}"
                        )
                        continue

                    file_modified = False

                    for patch in change.patches:
                        if patch.target_content in f.content:
                            f.content = f.content.replace(
                                patch.target_content,
                                patch.replacement_content,
                            )
                            file_modified = True
                        else:
                            error_message = f"Patch target not found in {path}"
                            print(error_message)
                            safety_errors.append(error_message)

                    if file_modified and path not in modified_paths:
                        modified_paths.append(path)

                    break

                if not found:
                    safety_errors.append(f"File not found for modify operation: {path}")

    else:
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
            history=json.dumps(history, indent=2),
            files=files_str,
        )

        result = repair_llm.invoke(prompt)
        print(f"Repair Analysis: {result.analysis}")

        from app.utils.path import resolve_patch_path

        for change in result.changes:
            try:
                path = resolve_patch_path(
                    change.file,
                    b_file_list + f_file_list,
                )
            except ValueError as ve:
                error_message = f"Path Resolution Error: {ve}"
                print(error_message)
                safety_errors.append(error_message)
                continue

            is_backend = path.startswith("backend/")
            target_list = b_file_list if is_backend else f_file_list
            found = False

            if change.action == "delete":
                file_exists = any(f.path == path for f in target_list)

                if not file_exists:
                    safety_errors.append(f"File not found for delete operation: {path}")
                    continue

                if is_backend:
                    b_file_list = [f for f in b_file_list if f.path != path]
                else:
                    f_file_list = [f for f in f_file_list if f.path != path]

                if path not in modified_paths:
                    modified_paths.append(path)

            elif change.action == "modify":
                for f in target_list:
                    if f.path == path:
                        f.content = change.content
                        found = True

                        if path not in modified_paths:
                            modified_paths.append(path)

                        break

                if not found:
                    safety_errors.append(f"File not found for modify operation: {path}")

            elif change.action == "create":
                if any(f.path == path for f in target_list):
                    safety_errors.append(
                        f"File already exists for create operation: {path}"
                    )
                    continue

                target_list.append(
                    FileContent(
                        path=path,
                        content=change.content,
                    )
                )

                if path not in modified_paths:
                    modified_paths.append(path)

    new_hist = {
        "attempt": attempts,
        "source": (
            "safety/validator" if validation_errs or safety_errors else "executor"
        ),
        "errors": all_errs if all_errs else exec_res.get("errors", []),
        "files_changed": modified_paths,
        "analysis": result.analysis,
        "result": "applied" if modified_paths else "failed",
    }

    history.append(new_hist)

    return {
        "repair_attempts": attempts,
        "repair_history": history,
        "backend_files": GeneratedFiles(files=b_file_list),
        "frontend_files": GeneratedFiles(files=f_file_list),
        "validation_errors": None,
        "execution_result": None,
        "safety_errors": safety_errors,
    }
