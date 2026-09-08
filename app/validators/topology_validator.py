import os
from typing import List, Set
from app.tools.grep_tool import discover_entry_points
from app.tools.ast_parser import extract_local_imports


def validate_topology(workspace_path: str) -> List[str]:
    """
    Validates that newly generated/modified components are topologically connected
    to the Application Roots, preventing orphaned LLM logic blocks.
    """
    errors = []

    # Locate all dynamically mapped entry roots from disk
    entry_roots = discover_entry_points(workspace_path)
    if not entry_roots:
        return []  # No organic entry roots found, cannot validate topology strictly

    # Expand reachable components
    reachable_files = set(entry_roots)
    queue = list(entry_roots)

    # Map physical files
    file_contents = {}
    ignore_dirs = {"node_modules", ".git", "dist", "build", "venv", "__pycache__"}
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if file.endswith((".js", ".jsx", ".ts", ".tsx", ".css", ".html")):
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, workspace_path).replace("\\", "/")
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        file_contents[rel_path] = f.read()
                except Exception:
                    pass

    # Breadth First AST Dependency Traversal
    processed = set()
    while queue:
        current_node = queue.pop(0)
        if current_node in processed:
            continue

        processed.add(current_node)

        if current_node in file_contents:
            full_path = os.path.join(workspace_path, current_node)
            imports = extract_local_imports(
                full_path, file_contents[current_node], workspace_path
            )

            for child in imports:
                if child not in reachable_files:
                    reachable_files.add(child)
                    queue.append(child)

    # Validate that every logical source file is reachable
    for rel_path in file_contents.keys():
        if rel_path.endswith((".js", ".jsx", ".ts", ".tsx", ".css")):
            # Ignore test files or config blobs
            if "test" in rel_path or "config" in rel_path or "setup" in rel_path:
                continue

            if rel_path not in reachable_files:
                errors.append(
                    f"Topological Disconnect: '{rel_path}' is never imported or rendered by the application roots ({entry_roots}). If this file is required, you must wire it into the main DOM / Providers! If it is a duplicate or unnecessary, you must delete it using the 'delete' action."
                )

    return errors
