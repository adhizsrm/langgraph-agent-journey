import re
import posixpath
from typing import List
from app.state.schemas import FileContent


def extract_exports(content: str) -> set:
    exports = set()
    matches = re.finditer(
        r"export\s+(?:const|let|var|function|class|interface|type|enum)\s+([a-zA-Z0-9_$]+)",
        content,
    )
    for m in matches:
        exports.add(m.group(1))
    matches = re.finditer(r"export\s*\{([^}]+)\}", content)
    for m in matches:
        for sym in m.group(1).split(","):
            sym = sym.strip()
            if not sym:
                continue
            if " as " in sym:
                exports.add(sym.split(" as ")[1].strip())
            else:
                exports.add(sym)
    if re.search(r"export\s+default", content):
        exports.add("default")
    return exports


def validate_cross_file_symbols(files: List[FileContent], agent_name: str) -> List[str]:
    if agent_name == "Backend":
        return []
    local_errors = []
    file_map = {f.path.replace("\\", "/"): f for f in files}
    exports_map = {
        p: extract_exports(f.content)
        for p, f in file_map.items()
        if p.endswith((".ts", ".tsx"))
    }

    for path, f in file_map.items():
        if not path.endswith((".ts", ".tsx")):
            continue
        dir_name = posixpath.dirname(path)

        import_statements = re.finditer(
            r'import\s+([^"\'\{]*?)(?:\{([^}]+)\})?\s*(?:from\s+)?[\'"](\.[^\'"]+)[\'"]',
            f.content,
        )
        for match in import_statements:
            default_or_ns = match.group(1).strip()
            named_imports = match.group(2)
            import_path = match.group(3)

            resolved = posixpath.normpath(posixpath.join(dir_name, import_path))
            target_path = next(
                (
                    p
                    for p in [
                        resolved,
                        resolved + ".ts",
                        resolved + ".tsx",
                        resolved + ".js",
                        resolved + ".jsx",
                        resolved + "/index.ts",
                        resolved + "/index.tsx",
                        resolved + "/index.js",
                        resolved + "/index.jsx",
                    ]
                    if p in exports_map
                ),
                None,
            )
            if not target_path:
                continue
            target_exports = exports_map[target_path]

            if named_imports:
                for named in named_imports.split(","):
                    named = named.strip()
                    if not named:
                        continue
                    import_name = named.split(" as ")[0].strip()
                    if import_name not in target_exports:
                        local_errors.append(
                            f"{agent_name} unresolved export: {path} imports '{import_name}' from '{import_path}', but the target file does not export '{import_name}'."
                        )

            if default_or_ns:
                default_part = default_or_ns.replace(",", "").strip()
                if default_part:
                    if default_part.startswith("* as "):
                        ns_name = default_part.split("* as ")[1].strip()
                        usages = re.finditer(
                            rf"{re.escape(ns_name)}\.([a-zA-Z0-9_$]+)", f.content
                        )
                        for usage in usages:
                            prop = usage.group(1)
                            if prop not in target_exports:
                                local_errors.append(
                                    f"{agent_name} unresolved exported member: {path} references '{ns_name}.{prop}', but '{import_path}' does not export '{prop}'."
                                )
                    else:
                        if "default" not in target_exports:
                            local_errors.append(
                                f"{agent_name} default import error: {path} imports the default export from '{import_path}', but the target module has no default export."
                            )

    return local_errors
