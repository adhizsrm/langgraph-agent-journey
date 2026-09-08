import os
import re
import json
from typing import List
from app.tools.ast_parser import extract_local_imports


def discover_entry_points(base_dir: str) -> List[str]:
    """Dynamically discover actual application entry points."""
    entry_points = set()
    ignore_dirs = {
        "node_modules",
        ".git",
        "dist",
        "build",
        "venv",
        "__pycache__",
        "workspace",
    }

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, base_dir).replace("\\", "/")

            # 1. Package.json analysis
            if file == "package.json":
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "main" in data and isinstance(data["main"], str):
                            main_path = os.path.normpath(
                                os.path.join(root, data["main"])
                            ).replace("\\", "/")
                            entry_points.add(
                                os.path.relpath(main_path, base_dir).replace("\\", "/")
                            )

                        scripts = data.get("scripts", {})
                        for script_name in ["start", "dev", "build"]:
                            if script_name in scripts:
                                script_cmd = scripts[script_name]
                                tokens = script_cmd.split()
                                for token in tokens:
                                    if token.endswith((".js", ".ts", ".jsx", ".tsx")):
                                        script_path = os.path.normpath(
                                            os.path.join(root, token)
                                        ).replace("\\", "/")
                                        entry_points.add(
                                            os.path.relpath(
                                                script_path, base_dir
                                            ).replace("\\", "/")
                                        )
                except Exception:
                    pass

            # 2. HTML entry parsing
            elif file.endswith(".html"):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        scripts = re.findall(
                            r'<script.*?src=["\'](.*?)["\'].*?>', content
                        )
                        for src in scripts:
                            if src.startswith("/"):
                                src = src[1:]
                            elif src.startswith("./"):
                                src = src[2:]

                            script_path = os.path.normpath(
                                os.path.join(root, src)
                            ).replace("\\", "/")
                            entry_points.add(
                                os.path.relpath(script_path, base_dir).replace(
                                    "\\", "/"
                                )
                            )
                except Exception:
                    pass

            # 3. Bootstrap Code Scanning (Fallback explicitly targeting rendered entry points)
            elif file.endswith((".js", ".jsx", ".ts", ".tsx")):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        if (
                            "createRoot(" in content
                            or "ReactDOM.render(" in content
                            or "app.listen(" in content
                            or "server.listen(" in content
                        ):
                            entry_points.add(rel_path)
                except Exception:
                    pass

    # Clean existing filters
    valid_entry_points = []
    for ep in entry_points:
        full = os.path.join(base_dir, ep)
        if os.path.exists(full):
            valid_entry_points.append(ep)
        else:
            base_full, orig_ext = os.path.splitext(full)
            found = False
            for ext in [".js", ".ts", ".jsx", ".tsx", ".css"]:
                if os.path.exists(base_full + ext):
                    valid_entry_points.append(
                        ep.replace(orig_ext, ext) if orig_ext else ep + ext
                    )
                    found = True
                    break
            if not found:
                for ext in [".js", ".ts", ".jsx", ".tsx", ".css"]:
                    if os.path.exists(full + ext):
                        valid_entry_points.append(ep + ext)
                        break

    return sorted(list(set(valid_entry_points)))


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

    # Dynamically extract roots explicitly tracking actual frameworks
    dynamic_seeds = discover_entry_points(base_dir)

    initial_matches = set()
    file_contents = {}

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if not file.endswith(
                (".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".json", ".txt", ".md")
            ):
                continue
            filepath = os.path.join(root, file)
            try:
                rel_path = os.path.relpath(filepath, base_dir).replace("\\", "/")

                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    file_contents[rel_path] = content
                    content_lower = content.lower()

                file_lower = file.lower()

                if rel_path in dynamic_seeds or any(
                    word in content_lower or word in file_lower for word in words
                ):
                    initial_matches.add(rel_path)
            except Exception:
                pass

    # Depth 1: Expanded set via secure AST imports parsing
    expanded_set = set(initial_matches)
    for rel_path in initial_matches:
        if rel_path in file_contents:
            imports = extract_local_imports(
                os.path.join(base_dir, rel_path), file_contents[rel_path], base_dir
            )
            expanded_set.update(imports)

    # Depth 2: AST import expansion scaling memory context boundly
    depth2_set = set(expanded_set)
    for rel_path in expanded_set:
        if rel_path in file_contents:
            imports = extract_local_imports(
                os.path.join(base_dir, rel_path), file_contents[rel_path], base_dir
            )
            depth2_set.update(imports)

    return list(depth2_set)
