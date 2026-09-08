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


def grep_search(goal: str, base_dir: str) -> tuple[List[str], dict]:
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

    total_files_discovered = 0

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if not file.endswith(
                (".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".json", ".txt", ".md")
            ):
                continue
            total_files_discovered += 1
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

    from app.tools.dependency_graph import build_repository_dependency_graph

    # Configure Explicit Limits (Phase 4 Step 7)
    MAX_FORWARD_DEPTH = 2
    MAX_REVERSE_DEPTH = 2
    MAX_CONTEXT_FILES = 15

    # 1. Build Global Bounded Graph
    all_files = list(file_contents.keys())
    graph = build_repository_dependency_graph(all_files, base_dir, file_contents)

    # 2. Extract Traversal Dependencies
    forward_depth_1 = graph.get_forward_dependencies(initial_matches, max_depth=1)
    reverse_depth_1 = graph.get_reverse_dependencies(initial_matches, max_depth=1)

    forward_deps = graph.get_forward_dependencies(
        initial_matches, max_depth=MAX_FORWARD_DEPTH
    )
    reverse_deps = graph.get_reverse_dependencies(
        initial_matches, max_depth=MAX_REVERSE_DEPTH
    )

    # 3. Bounded Prioritized Context Construction
    final_files = []

    priority_groups = [
        sorted(list(initial_matches)),
        sorted(list((forward_depth_1 | reverse_depth_1) - initial_matches)),
        sorted(
            list(
                (forward_deps | reverse_deps)
                - forward_depth_1
                - reverse_depth_1
                - initial_matches
            )
        ),
    ]

    for group in priority_groups:
        for f in group:
            if len(final_files) < MAX_CONTEXT_FILES and f not in final_files:
                final_files.append(f)

    final_context_chars = sum(len(file_contents.get(f, "")) for f in final_files)

    metrics = {
        "total_repository_files_discovered": total_files_discovered,
        "candidate_files_found_by_retrieval": len(initial_matches),
        "forward_dependency_files": len(forward_deps - initial_matches),
        "reverse_impact_files": len(reverse_deps - initial_matches),
        "final_context_files": len(final_files),
        "final_context_character_count": final_context_chars,
        "graph_nodes": len(graph.nodes),
        "graph_edges": sum(len(neighbors) for neighbors in graph.forward.values()),
        "forward_traversal_depth_configured": MAX_FORWARD_DEPTH,
        "reverse_traversal_depth_configured": MAX_REVERSE_DEPTH,
        "max_context_files_configured": MAX_CONTEXT_FILES,
    }

    return final_files, metrics
