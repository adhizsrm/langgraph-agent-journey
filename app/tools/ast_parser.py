import os
import tree_sitter
import tree_sitter_javascript
import tree_sitter_typescript
from typing import List

# Cache core language bindings
JS_LANG = tree_sitter.Language(tree_sitter_javascript.language())
TS_LANG = tree_sitter.Language(tree_sitter_typescript.language_typescript())
TSX_LANG = tree_sitter.Language(tree_sitter_typescript.language_tsx())


def get_parser_for_file(filepath: str) -> tree_sitter.Parser:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".ts":
        return tree_sitter.Parser(TS_LANG)
    elif ext == ".tsx":
        return tree_sitter.Parser(TSX_LANG)
    else:  # .js, .jsx and fallback
        return tree_sitter.Parser(JS_LANG)


def extract_local_imports(filepath: str, content: str, base_dir: str) -> List[str]:
    parser = get_parser_for_file(filepath)
    try:
        tree = parser.parse(bytes(content, "utf8"))
    except Exception:
        return []

    raw_imports = []

    def extract_nodes(node):
        # ES Modules
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "string":
                    raw_imports.append(child.text.decode("utf-8").strip("'\""))

        # CommonJS OR Dynamic import() combined into single check
        elif node.type == "call_expression":
            is_require_or_import = False
            for child in node.children:
                if child.type == "import":
                    is_require_or_import = True
                elif (
                    child.type == "identifier"
                    and child.text.decode("utf-8") == "require"
                ):
                    is_require_or_import = True

                if is_require_or_import and child.type == "arguments":
                    for arg in child.children:
                        if arg.type == "string":
                            raw_imports.append(arg.text.decode("utf-8").strip("'\""))

        for child in node.children:
            extract_nodes(child)

    extract_nodes(tree.root_node)

    # Resolving physical local files bridging Node standard mapping
    resolved_files = []
    file_dir = os.path.dirname(filepath)

    for p in raw_imports:
        if p.startswith("."):  # Strict separation isolating external deps
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
            else:
                # Fallback checking directories for index files
                for ext in possible_extensions:
                    if ext == "":
                        continue
                    test_path = os.path.join(normalized_path, "index" + ext)
                    if os.path.isfile(test_path):
                        rel_path = os.path.relpath(test_path, base_dir).replace(
                            "\\", "/"
                        )
                        resolved_files.append(rel_path)
                        break

    return list(set(resolved_files))
