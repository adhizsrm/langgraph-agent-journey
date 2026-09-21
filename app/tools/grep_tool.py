import os
import re
from typing import List, Set


def extract_local_imports(filepath: str, content: str, base_dir: str) -> List[str]:
    import_paths = re.findall(
        r"import\s+(?:[^'\"]+?\s+from\s+)?['\"](.*?)['\"]", content
    )
    import_paths += re.findall(r"require\s*\(\s*['\"](.*?)['\"]\s*\)", content)
    import_paths += re.findall(r"@import\s*(?:url\()?['\"]?(.*?)['\"]?\)?", content)

    # HTML references expansion
    import_paths += re.findall(
        r"<script[^>]+src=['\"](.*?)['\"]", content, re.IGNORECASE
    )
    import_paths += re.findall(
        r"<link[^>]+href=['\"](.*?)['\"]", content, re.IGNORECASE
    )

    resolved_files = []
    file_dir = os.path.dirname(filepath)

    for p in import_paths:
        if p.startswith(".") or (not p.startswith("/") and not p.startswith("http")):
            clean_p = p.split("?")[0].split("#")[0]
            normalized_path = os.path.normpath(os.path.join(file_dir, clean_p))

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
    stop_words = {
        "that",
        "this",
        "with",
        "from",
        "which",
        "where",
        "when",
        "what",
        "into",
        "then",
        "than",
        "have",
        "will",
        "should",
        "would",
        "could",
        "add",
    }
    words = [
        w.lower()
        for w in re.findall(r"\b\w+\b", goal)
        if len(w) > 3 and w.lower() not in stop_words
    ]
    if not words:
        words = [w.lower() for w in goal.split() if w.lower() not in stop_words]

    ignore_dirs = {
        "node_modules",
        ".git",
        "dist",
        "build",
        "venv",
        "__pycache__",
        "workspace",
    }

    discovered_entry_points = set()
    keyword_matches = set()
    file_contents = {}

    entry_signals = [
        "ReactDOM.createRoot(",
        "ReactDOM.render(",
        "createApp(",
        "bootstrapModule(",
        "app.listen(",
        "server.listen(",
        "http.createServer(",
    ]

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
        for file in files:
            if not file.endswith(
                (".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".json", ".md")
            ):
                continue

            if file in {
                "package-lock.json",
                "yarn.lock",
                "pnpm-lock.yaml",
                "bun.lockb",
            }:
                continue

            filepath = os.path.join(root, file)
            try:
                # Basic size limitation to prevent caching massive files for discovery
                if os.path.getsize(filepath) > 1024 * 500:
                    continue

                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                rel_path = os.path.relpath(filepath, base_dir).replace("\\", "/")
                content_lower = content.lower()
                file_lower = file.lower()

                is_candidate = False

                # 1. Relevance keywords match
                if any(word in content_lower or word in file_lower for word in words):
                    keyword_matches.add(rel_path)
                    is_candidate = True

                # 2. Entry point discovery
                if not file.endswith((".txt", ".md", ".json")):
                    is_entry = False

                    if any(sig in content for sig in entry_signals):
                        is_entry = True

                    # Next.js and typical modern UI root patterns
                    elif (
                        rel_path.endswith("layout.tsx")
                        or rel_path.endswith("layout.jsx")
                        or rel_path.endswith("page.tsx")
                        or rel_path.endswith("page.jsx")
                    ):
                        if (
                            "test/" not in rel_path
                            and "docs/" not in rel_path
                            and "fixture" not in rel_path
                        ):
                            is_entry = True

                    elif file.endswith(".html"):
                        if "<script " in content_lower or "<link " in content_lower:
                            if (
                                "test/" not in rel_path
                                and "docs/" not in rel_path
                                and "fixture" not in rel_path
                            ):
                                is_entry = True

                    if is_entry:
                        discovered_entry_points.add(rel_path)
                        is_candidate = True

                # Lazy cache candidate content
                if is_candidate:
                    file_contents[rel_path] = content

            except Exception:
                pass

    from collections import deque

    import_graph = {}
    queue = deque(discovered_entry_points)
    visited = set(discovered_entry_points)

    # 1. Build downward import graph from all entry points
    while queue:
        node = queue.popleft()
        node_full = os.path.join(base_dir, node)

        if node not in file_contents:
            try:
                with open(node_full, "r", encoding="utf-8") as f:
                    file_contents[node] = f.read()
            except Exception:
                pass

        if node in file_contents:
            imports = extract_local_imports(node_full, file_contents[node], base_dir)
            import_graph[node] = imports
            for imp in imports:
                if imp not in visited:
                    visited.add(imp)
                    queue.append(imp)

    # 2. Find shortest path from any entry point to reachable nodes
    parents = {}
    queue = deque(discovered_entry_points)
    visited_search = set(discovered_entry_points)

    while queue:
        node = queue.popleft()
        for child in import_graph.get(node, []):
            if child not in visited_search:
                visited_search.add(child)
                parents[child] = node
                queue.append(child)

    # 3. Construct shortest paths for keyword matches
    lineage_base = set()
    for match in keyword_matches:
        if match in visited_search:
            curr = match
            while curr is not None:
                lineage_base.add(curr)
                curr = parents.get(curr)
        else:
            # Orphan match.
            # To prevent excessive noise from test, diagnostic, and history scripts containing
            # generic keywords, orphan matches are only appended if their role/filename clearly correlates with intent.
            file_basename = os.path.basename(match).lower()

            if any(w in file_basename for w in words):
                # Strong Intent: Filename actually explicitly maps to a search keyword
                lineage_base.add(match)
            elif (
                file_basename.endswith(".md")
                or "config" in file_basename
                or "setup" in file_basename
                or file_basename == "package.json"
            ):
                # Structural Context: Typical top-level / isolated configuration files and documentation
                lineage_base.add(match)

    # 4. Entry Shell Expansion
    entry_shell_expansions = set()
    for node in lineage_base:
        if node in discovered_entry_points:
            for child in import_graph.get(node, []):
                entry_shell_expansions.add(child)
    lineage_base.update(entry_shell_expansions)

    # Ensure orphans are in import_graph for styling expansion
    for node in lineage_base:
        if node not in import_graph:
            node_full = os.path.join(base_dir, node)
            if node not in file_contents:
                try:
                    with open(node_full, "r", encoding="utf-8") as f:
                        file_contents[node] = f.read()
                except Exception:
                    pass
            if node in file_contents:
                import_graph[node] = extract_local_imports(
                    node_full, file_contents[node], base_dir
                )

    # 5. Styling Expansion
    final_selection = set(lineage_base)
    for node in lineage_base:
        for child in import_graph.get(node, []):
            if child.endswith((".css", ".scss", ".less", ".module.css")):
                final_selection.add(child)

    print("Discovered entry points:")
    for ep in sorted(discovered_entry_points):
        print(f"  - {ep}")

    print("\nRelevant files selected:")
    for km in sorted(keyword_matches):
        print(f"  - {km}")

    print("\nFiles passed to Enhancement Agent:")
    for fs in sorted(final_selection):
        print(f"  - {fs}")

    return list(final_selection)
