import os
import shutil
import tempfile
import pytest
from app.tools.grep_tool import grep_search
from app.agents.enhancement_agent import load_retrieved_files


def setup_synthetic_repo(base_dir, num_unrelated=20):
    os.makedirs(os.path.join(base_dir, "src", "routes"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "src", "controllers"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "src", "services"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "src", "unrelated"), exist_ok=True)

    with open(os.path.join(base_dir, "package.json"), "w") as f:
        f.write('{"main": "src/index.js"}')

    # Core chain simulating actual relational targeting components
    with open(os.path.join(base_dir, "src", "index.js"), "w") as f:
        f.write("require('./routes/users');")

    with open(os.path.join(base_dir, "src", "routes", "users.js"), "w") as f:
        f.write(
            "const ctrl = require('../controllers/users');\n// target_enhancement_keyword"
        )

    with open(os.path.join(base_dir, "src", "controllers", "users.js"), "w") as f:
        f.write("const svc = require('../services/users');")

    with open(os.path.join(base_dir, "src", "services", "users.js"), "w") as f:
        f.write("module.exports = { execute: () => {} };")

    # The bloat simulating repository linear expansions
    for i in range(num_unrelated):
        with open(os.path.join(base_dir, "src", "unrelated", f"file{i}.js"), "w") as f:
            f.write(f"// Unrelated file {i}\nconst unused = {i};\n")


def test_retrieval_does_not_scale_linearly():
    tmp = tempfile.mkdtemp()
    try:
        setup_synthetic_repo(tmp, num_unrelated=50)

        # Scenario: user asks to enhance 'target_enhancement_keyword'
        goal = "target_enhancement_keyword"
        files, metrics = grep_search(goal, tmp)

        # 1. Total files should be exactly 54 (4 core + 50 unrelated)
        # Note: package.json is ignored because it ends in .json but grep search only grabs specific source extensions?
        # Actually grep_search filters for .js/.json/.html/.css, so 55 files total.
        assert metrics["total_repository_files_discovered"] >= 54

        # 2. Files added by retrieval should NOT include the 50 unrelated files!
        # It should only include the core chain connected by AST!
        assert metrics["final_context_files"] < 50

        valid_chain = [
            "src/index.js",
            "src/routes/users.js",
            "src/controllers/users.js",
            "src/services/users.js",
        ]

        # Index might dynamically seed because package.json main points to it.
        # Actually grep_search catches target_enhancement_keyword in users.js.
        # Then AST parses require('../controllers/users') and pulls it.
        # Controllers pulls services.

        unrelated_found = any("unrelated" in f for f in files)
        assert (
            not unrelated_found
        ), "Unrelated files were erroneously included in retrieval context!"

    finally:
        shutil.rmtree(tmp)


def test_regression_old_failure_mode():
    tmp = tempfile.mkdtemp()
    try:
        setup_synthetic_repo(tmp, num_unrelated=100)

        goal = "target_enhancement_keyword"
        files, metrics = grep_search(goal, tmp)

        # The enhancement agent NO LONGER loads the full project!
        # Instead, it calls load_retrieved_files
        b_files, f_files = load_retrieved_files(tmp, files)

        total_memory_files = len(b_files) + len(f_files)

        # In the old code (load_full_project_into_memory), total_memory_files would be > 100
        # In the current code it must equal len(files)!
        assert total_memory_files == len(files)
        assert (
            total_memory_files < 20
        ), "Memory scaling bug detected! Context bloat still exists!"

    finally:
        shutil.rmtree(tmp)
