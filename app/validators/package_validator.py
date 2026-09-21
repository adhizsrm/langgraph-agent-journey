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
            if not start_script:
                errors.append("Backend missing 'start' script")
            else:
                valid_runtimes = ["node", "tsx", "ts-node", "nodemon"]
                if not any(r in start_script for r in valid_runtimes):
                    errors.append(
                        "Backend 'start' script must contain a valid runtime (e.g., 'node', 'tsx', 'ts-node')"
                    )

                valid_entries = [
                    "src/index.js",
                    "src/index.ts",
                    "src/server.js",
                    "src/server.ts",
                    "server.js",
                    "server.ts",
                    "index.js",
                    "index.ts",
                    "dist/index.js",
                    "dist/server.js",
                ]
                if not any(ep in start_script for ep in valid_entries):
                    errors.append(
                        "Backend 'start' script must reference a valid entry point (e.g., src/index.js, server.ts)"
                    )

                # Check dependency if TS runtime is used
                dev_deps = pkg_data.get("devDependencies", {})
                for ts_runtime in ["tsx", "ts-node"]:
                    if (
                        ts_runtime in start_script
                        and ts_runtime not in deps
                        and ts_runtime not in dev_deps
                    ):
                        errors.append(
                            f"Backend 'start' script uses '{ts_runtime}' but it is missing from dependencies"
                        )

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

    # Must have required vite files, allowing TS variants
    frontend_req_groups = [
        ["vite.config.js", "vite.config.ts"],
        ["index.html"],
        ["src/main.jsx", "src/main.tsx"],
        ["src/App.jsx", "src/App.tsx"],
    ]
    for group in frontend_req_groups:
        if not any(find_file(f_files, rf) for rf in group):
            group_str = " or ".join(group)
            errors.append(f"Frontend missing {group_str}")

    return errors
