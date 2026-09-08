import json
from app.state.schemas import FileContent
from app.validators.package_validator import validate_frontend_package


def check(name, f_files, expected_errors):
    errs = validate_frontend_package(f_files)
    print(f"[{name}] Errors: {errs}")
    pass_test = len(errs) == expected_errors
    if not pass_test:
        print(f"  -> FAILED: Expected {expected_errors} errors, got {len(errs)}")
    else:
        print(f"  -> PASSED")
    return pass_test


valid_pkg = json.dumps(
    {
        "dependencies": {"react": "1", "react-dom": "1"},
        "devDependencies": {"vite": "1", "@vitejs/plugin-react": "1"},
        "scripts": {"dev": "vite"},
    }
)
bases = [
    FileContent(path="vite.config.js", content=""),
    FileContent(path="index.html", content=""),
    FileContent(path="src/main.jsx", content=""),
    FileContent(path="src/App.jsx", content=""),
]

print("=== STARTING TESTS ===")
check("VALID", bases + [FileContent(path="package.json", content=valid_pkg)], 0)
check(
    "MISSING REACT",
    bases
    + [
        FileContent(
            path="package.json",
            content=json.dumps(
                {
                    "dependencies": {"react-dom": "1"},
                    "devDependencies": {"vite": "1", "@vitejs/plugin-react": "1"},
                    "scripts": {"dev": "vite"},
                }
            ),
        )
    ],
    1,
)
check(
    "MISSING SCRIPT",
    bases
    + [
        FileContent(
            path="package.json",
            content=json.dumps(
                {
                    "dependencies": {"react": "1", "react-dom": "1"},
                    "devDependencies": {"vite": "1", "@vitejs/plugin-react": "1"},
                    "scripts": {},
                }
            ),
        )
    ],
    1,
)
check("INVALID JSON", bases + [FileContent(path="package.json", content="NOT JSON")], 1)
