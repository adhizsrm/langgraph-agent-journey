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
    os.makedirs(os.path.join(base_dir, "src", "models"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "src", "unrelated"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "src", "cycles"), exist_ok=True)

    with open(os.path.join(base_dir, "package.json"), "w") as f:
        f.write('{"main": "src/index.js"}')

    # Forward/Reverse test chain
    with open(os.path.join(base_dir, "src", "index.js"), "w") as f:
        f.write("require('./routes/users');")

    with open(os.path.join(base_dir, "src", "routes", "users.js"), "w") as f:
        f.write(
            "const ctrl = require('../controllers/users');\n// target_route_enhancement"
        )

    with open(os.path.join(base_dir, "src", "controllers", "users.js"), "w") as f:
        f.write(
            "const svc = require('../services/users');\n// target_controller_enhancement"
        )

    with open(os.path.join(base_dir, "src", "services", "users.js"), "w") as f:
        f.write(
            "const mdl = require('../models/users');\n// target_service_enhancement"
        )

    with open(os.path.join(base_dir, "src", "models", "users.js"), "w") as f:
        f.write("module.exports = { data: 'users' };")

    # Products isolated chain
    with open(os.path.join(base_dir, "src", "routes", "products.js"), "w") as f:
        f.write("require('../controllers/products');")
    with open(os.path.join(base_dir, "src", "controllers", "products.js"), "w") as f:
        f.write("require('../services/products');")
    with open(os.path.join(base_dir, "src", "services", "products.js"), "w") as f:
        f.write("require('../models/products');")
    with open(os.path.join(base_dir, "src", "models", "products.js"), "w") as f:
        f.write("module.exports = { data: 'products' };")

    # Cycles test chain
    with open(os.path.join(base_dir, "src", "cycles", "a.js"), "w") as f:
        f.write("require('./b');\n// target_cycle")
    with open(os.path.join(base_dir, "src", "cycles", "b.js"), "w") as f:
        f.write("require('./c');")
    with open(os.path.join(base_dir, "src", "cycles", "c.js"), "w") as f:
        f.write("require('./a');")

    # The bloat simulating repository linear expansions
    for i in range(num_unrelated):
        with open(os.path.join(base_dir, "src", "unrelated", f"file{i}.js"), "w") as f:
            f.write(f"// Unrelated file {i}\nconst unused = {i};\n")


def test_forward_traversal():
    tmp = tempfile.mkdtemp()
    try:
        setup_synthetic_repo(tmp, num_unrelated=5)
        # Goal targets routes/users.js
        files, metrics = grep_search("target_route_enhancement", tmp)

        # Max Depth configured is 2
        # Level 0: routes/users.js
        # Level 1 forward: controllers/users.js
        # Level 2 forward: services/users.js
        # Level 3 forward: models/users.js (Should NOT be traversed directly! Wait, is depth 2 level 2 or 3?)
        # Let's check files actually retrieved

        rel_files = [f.replace("\\", "/") for f in files]
        assert "src/controllers/users.js" in rel_files
        assert "src/services/users.js" in rel_files

    finally:
        shutil.rmtree(tmp)


def test_reverse_impact():
    tmp = tempfile.mkdtemp()
    try:
        setup_synthetic_repo(tmp, num_unrelated=5)
        # Goal targets services/users.js
        files, metrics = grep_search("target_service_enhancement", tmp)

        # Max Reverse Depth is 2
        # Level 0: services/users.js
        # Level 1 backward: controllers/users.js
        # Level 2 backward: routes/users.js
        # Also gets models/users.js because of Level 1 forward!

        rel_files = [f.replace("\\", "/") for f in files]
        assert "src/controllers/users.js" in rel_files
        assert "src/routes/users.js" in rel_files
        assert "src/models/users.js" in rel_files

        # Ensure products are NOT included
        assert not any("products" in f for f in rel_files)

    finally:
        shutil.rmtree(tmp)


def test_cycles():
    tmp = tempfile.mkdtemp()
    try:
        setup_synthetic_repo(tmp, num_unrelated=2)
        # Goal targets a.js
        files, metrics = grep_search("target_cycle", tmp)

        rel_files = [f.replace("\\", "/") for f in files]
        assert "src/cycles/a.js" in rel_files
        assert "src/cycles/b.js" in rel_files
        assert "src/cycles/c.js" in rel_files

        # It must not crash, must return bounded list.
        assert len(files) <= 15

    finally:
        shutil.rmtree(tmp)


def test_repository_scale_boundedness():
    tmp_a = tempfile.mkdtemp()
    tmp_b = tempfile.mkdtemp()
    try:
        setup_synthetic_repo(tmp_a, num_unrelated=20)
        setup_synthetic_repo(tmp_b, num_unrelated=100)

        goal = "target_service_enhancement"
        files_a, metrics_a = grep_search(goal, tmp_a)
        files_b, metrics_b = grep_search(goal, tmp_b)

        # Final context files must be identically bounded despite 80 more files
        assert metrics_a["final_context_files"] == metrics_b["final_context_files"]
        assert metrics_b["final_context_files"] <= 15

    finally:
        shutil.rmtree(tmp_a)
        shutil.rmtree(tmp_b)
