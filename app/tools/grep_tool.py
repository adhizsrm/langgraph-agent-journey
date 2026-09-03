import os
import re
from typing import List


def extract_local_imports(filepath: str, content: str, base_dir: str) -> List[str]:
    # Match ES6 imports, CSS @imports, and requires
    import_paths = re.findall(r"import\s+(?:.*?\s+from\s+)?['\"](.*?)['\"]", content)
    import_paths += re.findall(r"require\s*\(\s*['\"](.*?)['\"]\s*\)", content)
    import_paths += re.findall(r"@import\s*(?:url\()?['\"]?(.*?)['\"]?\)?", content)

    resolved_files = []
    file_dir = os.path.dirname(filepath)

    for p in import_paths:
        if p.startswith("."):  # local dependency
            # basic clean up in case of query params
            clean_p = p.split("?")[0].split("#")[0]

            # Resolve relative path
            normalized_path = os.path.normpath(os.path.join(file_dir, clean_p))

            # Since imports might omit extensions
            possible_extensions = [
                "",
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".css",
                ".json",
                ".html",
            ]
            for ext in possible_extensions:
                test_path = normalized_path + ext
                if os.path.isfile(test_path):
                    rel_path = os.path.relpath(test_path, base_dir).replace("\\", "/")
                    resolved_files.append(rel_path)
                    break

    return resolved_files


def grep_search(goal: str, base_dir: str) -> List[str]:
    words = [w.lower() for w in re.findall(r"\b\w+\b", goal) if len(w) > 3]
    if not words:
        words = [w.lower() for w in goal.split()]

    ignore_dirs = {
        "node_modules",
        ".git",
        "dist",
        "build",
        "venv",
        "__pycache__",
        "workspace",
    }

    initial_matches = set()
    file_contents = {}

    # File walking
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if not file.endswith(
                (".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".json", ".txt", ".md")
            ):
                continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    file_contents[filepath] = content
                    content_lower = content.lower()

                file_lower = file.lower()

                # Check for heuristic matches
                if any(word in content_lower or word in file_lower for word in words):
                    rel_path = os.path.relpath(filepath, base_dir).replace("\\", "/")
                    initial_matches.add(rel_path)
            except Exception:
                pass

    # AST import expansion (Depth 1)
    expanded_set = set(initial_matches)
    for rel_path in initial_matches:
        full_path = os.path.join(base_dir, rel_path)
        if full_path in file_contents:
            imports = extract_local_imports(
                full_path, file_contents[full_path], base_dir
            )
            expanded_set.update(imports)

    # AST import expansion (Depth 2)
    depth2_set = set(expanded_set)
    for rel_path in expanded_set:
        full_path = os.path.join(base_dir, rel_path)
        if full_path in file_contents:
            imports = extract_local_imports(
                full_path, file_contents[full_path], base_dir
            )
            depth2_set.update(imports)

    return list(depth2_set)
