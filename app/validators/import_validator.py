import re
import posixpath
from typing import List
from app.state.schemas import FileContent

IMPORT_REGEX = re.compile(r'(?:import|from)\s+[\'"](\.[^\'"]+)[\'"]')


def validate_local_imports(files: List[FileContent], agent_name: str) -> List[str]:
    if agent_name == "Backend":
        return []
    local_errors = []
    file_paths = {f.path.replace("\\", "/") for f in files}

    for f in files:
        normalized_path = f.path.replace("\\", "/")
        dir_name = posixpath.dirname(normalized_path)

        for match in IMPORT_REGEX.finditer(f.content):
            import_path = match.group(1)
            resolved = posixpath.normpath(posixpath.join(dir_name, import_path))

            possible_paths = [resolved]
            if not posixpath.splitext(resolved)[1]:
                # No extension specified, try all common ones
                for ext in [".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ".json"]:
                    possible_paths.append(resolved + ext)
                for ext in [".ts", ".tsx", ".js", ".jsx"]:
                    possible_paths.append(resolved + "/index" + ext)

            if not any(p in file_paths for p in possible_paths):
                local_errors.append(
                    f'{agent_name} unresolved local import: {f.path} imports "{import_path}", but the referenced file was not generated.'
                )
    return local_errors
