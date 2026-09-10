from app.state.schemas import GraphState, GeneratedFiles
from app.tools.patch_engine import validate_and_apply_patches


def project_safety_node(state: GraphState) -> GraphState:
    print("Running Unified Patch Engine / Safety Evaluation Node...")

    pending_patches = state.get("pending_patches", [])
    if not pending_patches:
        return {}  # No patches to apply, proceed cleanly

    b_files = state.get("backend_files")
    f_files = state.get("frontend_files")

    source_b = b_files.files if b_files else []
    source_f = f_files.files if f_files else []

    new_b, new_f, results, success, error_msg = validate_and_apply_patches(
        source_b, source_f, pending_patches
    )

    if not success:
        errs = state.get("safety_errors", []) or []
        errs.extend(results.get("errors", []))
        if error_msg:
            errs.append(f"Patch Engine Hard Fault: {error_msg}")

        # Optional diagnostic output keeping loops clean
        print("--- PATCH FAULT ---")
        for e in errs:
            print(f" * {e}")

        return {"safety_errors": errs}

    def _count_lines(files) -> int:
        return sum(len(f.content.splitlines()) for f in files)

    # -------------------------------------------------------------
    # RESTORED PROJECT DESTRUCTION SAFETY CHECKS (Do NOT Remove!)
    # -------------------------------------------------------------
    mode = state.get("mode", "create")
    safety_errors = state.get("safety_errors", []) or []
    source_path = state.get("source_project_path", "")

    if mode == "enhance" and source_path:

        def _load_project_files_safely(base_dir: str):
            import os
            from app.state.schemas import FileContent

            b, f = [], []
            ignore = {
                "node_modules",
                ".git",
                "dist",
                "build",
                "venv",
                "__pycache__",
                "workspace",
            }
            for root, dirs, files in os.walk(base_dir):
                dirs[:] = [d for d in dirs if d not in ignore]
                for file in files:
                    if not file.endswith(
                        (
                            ".js",
                            ".jsx",
                            ".ts",
                            ".tsx",
                            ".css",
                            ".html",
                            ".json",
                            ".txt",
                            ".md",
                            ".env.example",
                        )
                    ):
                        continue
                    filepath = os.path.join(root, file)
                    rel = os.path.relpath(filepath, base_dir).replace("\\", "/")
                    try:
                        with open(filepath, "r", encoding="utf-8") as f_obj:
                            content = f_obj.read()
                        if rel.startswith("backend/"):
                            b.append(FileContent(path=rel, content=content))
                        else:
                            f.append(FileContent(path=rel, content=content))
                    except Exception:
                        pass
            return b, f

        orig_b, orig_f = _load_project_files_safely(source_path)

        original_lines = _count_lines(orig_b) + _count_lines(orig_f)
        new_lines = _count_lines(new_b) + _count_lines(new_f)

        if original_lines > 0:
            ratio = new_lines / original_lines
            if ratio < 0.85:
                safety_errors.append(
                    f"Destruction Safety Triggered: Projected workspace dropped massive line counts ({(1-ratio)*100:.1f}% reduction). The Agent erased functionality."
                )

        orig_names = set(f.path for f in orig_b + orig_f)
        new_names = set(f.path for f in new_b + new_f)

        missing = orig_names - new_names
        for m in missing:
            if m not in results.get("deleted", []):
                safety_errors.append(
                    f"Destruction Safety Triggered: Component '{m}' was unexpectedly wiped from the codebase."
                )

    if safety_errors:
        return {"safety_errors": safety_errors}

    return {
        "backend_files": GeneratedFiles(files=new_b),
        "frontend_files": GeneratedFiles(files=new_f),
        "pending_patches": [],  # Flush states cleanly preventing infinite overrides
        "safety_errors": [],  # Flush previous safety errors on success!
        "workspace_deletions": results.get("deleted", []),
    }
