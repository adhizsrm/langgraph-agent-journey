import os


def get_actual_directory_listing(base_path: str) -> str:
    if not os.path.exists(base_path):
        return "Directory does not exist yet."
    ignore_dirs = {"node_modules", ".git", "dist", "build", "venv", "__pycache__"}
    tree = []
    for root, dirs, files in os.walk(base_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        rel_path = os.path.relpath(root, base_path)
        if rel_path == ".":
            continue
        tree.append(rel_path.replace("\\", "/") + "/")
    return ", ".join(tree) if tree else "."
