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
                (".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".json", ".txt", ".md")
            ):
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

    def expand(seeds: Set[str], depth: int) -> Set[str]:
        current_set = set(seeds)
        expanded = set(seeds)
        for _ in range(depth):
            next_set = set()
            for rp in current_set:
                fp = os.path.join(base_dir, rp)

                # Lazy load missing files discovered during expansion
                if rp not in file_contents:
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            file_contents[rp] = f.read()
                    except Exception:
                        continue

                imports = extract_local_imports(fp, file_contents[rp], base_dir)
                for imp in imports:
                    if imp not in expanded:
                        next_set.add(imp)
            expanded.update(next_set)
            current_set = next_set
        return expanded

    # 1. Expand application footprint context from structural entry points
    entry_tree = expand(discovered_entry_points, depth=2)

    # 2. Final relevant-file selection logic
    final_selection = set()

    for kw_file in keyword_matches:
        if not discovered_entry_points or kw_file in entry_tree:
            final_selection.add(kw_file)

    # If intersection logic pruned everything, fallback to raw relevance hits
    if len(final_selection) == 0:
        final_selection.update(keyword_matches)

    # Always provide entry points to LLM to establish structural architecture
    for ep in discovered_entry_points:
        final_selection.add(ep)

    # Expand to depth 2 to ensure we capture critical architecture layers like App.jsx -> App.css
    final_selection = expand(final_selection, depth=2)

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
