import json
from app.state.schemas import (
    GraphState,
    GeneratedFiles,
    OrchestratorOutput,
    FileContent,
)
from app.agents.llm import repair_llm
from app.prompts.repair import repair_prompt


def project_repair_node(state: GraphState) -> GraphState:
    print("Running Project Repair Agent...")
    attempts = state.get("repair_attempts", 0) + 1
    print(f"Repair attempt {attempts}/3")

    validation_errs = state.get("validation_errors", [])
    exec_res = state.get("execution_result", {})
    history = state.get("repair_history", [])

    b_files = state.get("backend_files", GeneratedFiles(files=[]))
    f_files = state.get("frontend_files", GeneratedFiles(files=[]))

    files_str = (
        "BACKEND FILES:\\n"
        + b_files.model_dump_json(indent=2)
        + "\\nFRONTEND FILES:\\n"
        + f_files.model_dump_json(indent=2)
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
        validation_errors=json.dumps(validation_errs, indent=2),
        execution_result=json.dumps(exec_res, indent=2),
        history=json.dumps(history, indent=2),
        files=files_str,
    )

    result = repair_llm.invoke(prompt)

    print(f"Repair Analysis: {result.analysis}")

    # Apply modifications
    b_file_list = b_files.files
    f_file_list = f_files.files

    backend_root = (
        state["orchestrator_spec"]
        .file_locations.get("backend_root", "backend/")
        .strip("/")
    )
    frontend_root = (
        state["orchestrator_spec"]
        .file_locations.get("frontend_root", "frontend/")
        .strip("/")
    )

    modified_paths = []

    for change in result.changes:
        path = change.file.replace("\\\\", "/")
        modified_paths.append(path)
        is_backend = path.startswith(backend_root)

        target_list = b_file_list if is_backend else f_file_list
        found = False

        if change.action == "delete":
            target_list[:] = [f for f in target_list if f.path != path]
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

    # Record history
    new_hist = {
        "attempt": attempts,
        "source": "validator" if validation_errs else "executor",
        "errors": validation_errs if validation_errs else exec_res.get("errors", []),
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
        # Clear out validation and execution state to force fresh perspective
        "validation_errors": None,
        "execution_result": None,
    }
