import json
from typing import List
from app.state.schemas import FileContent


def find_file(files: List[FileContent], name: str) -> FileContent:
    for f in files:
        if f.path.endswith(name):
            return f
    return None


def validate_backend_package(b_files: List[FileContent]) -> List[str]:
    errors = []
    if not b_files:
        return errors

    b_pkg = find_file(b_files, "package.json")
    if not b_pkg:
        errors.append("Backend package.json is missing")
    else:
        try:
            pkg_data = json.loads(b_pkg.content)
            deps = pkg_data.get("dependencies", {})
            scripts = pkg_data.get("scripts", {})

            if "express" not in deps:
                errors.append("Backend missing 'express' in dependencies")
            if "cors" not in deps:
                errors.append("Backend missing 'cors' in dependencies")

            start_script = scripts.get("start", "")
            if "node" not in start_script or "src/index.js" not in start_script:
                errors.append(
                    "Backend 'start' script must contain 'node' and 'src/index.js'"
                )

            if pkg_data.get("type") == "module":
                errors.append("Backend package.json must not have 'type': 'module'")
        except json.JSONDecodeError:
            errors.append("Backend package.json is invalid JSON")

    return errors


def validate_frontend_package(f_files: List[FileContent]) -> List[str]:
    errors = []
    if not f_files:
        return errors

    f_pkg = find_file(f_files, "package.json")
    if not f_pkg:
        errors.append("Frontend package.json is missing")
    else:
        try:
            pkg_data = json.loads(f_pkg.content)
            deps = pkg_data.get("dependencies", {})
            dev_deps = pkg_data.get("devDependencies", {})
            scripts = pkg_data.get("scripts", {})

            if "react" not in deps:
                errors.append("Frontend missing 'react' in dependencies")
            if "react-dom" not in deps:
                errors.append("Frontend missing 'react-dom' in dependencies")

            if "vite" not in dev_deps:
                errors.append("Frontend missing 'vite' in devDependencies")
            if "@vitejs/plugin-react" not in dev_deps:
                errors.append(
                    "Frontend missing '@vitejs/plugin-react' in devDependencies"
                )

            if "vite" not in scripts.get("dev", ""):
                errors.append("Frontend 'dev' script must use 'vite'")

            if "react-scripts" in str(pkg_data):
                errors.append("Frontend uses 'react-scripts' but Vite is required")
        except json.JSONDecodeError:
            errors.append("Frontend package.json is invalid JSON")

    # Must have required vite files
    for rf in ["vite.config.js", "index.html", "src/main.jsx", "src/App.jsx"]:
        if not find_file(f_files, rf):
            errors.append(f"Frontend missing {rf}")

    return errors
