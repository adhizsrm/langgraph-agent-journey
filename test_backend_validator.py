import pytest
from app.state.schemas import FileContent

# Our backend contracts support these components. We will mock the validation functions
import app.validators.import_validator as iv
import app.validators.export_validator as ev
from app.validators.topology_validator import validate_topology
import os
import shutil
import tempfile
import json


def test_1_valid_relative_cjs():
    b_files = [
        FileContent(path="backend/src/index.js", content="require('./routes/user');"),
        FileContent(path="backend/src/routes/user.js", content="module.exports = {};"),
    ]
    errs = iv.validate_local_imports(b_files, "Backend")
    assert not errs


def test_2_missing_local_module():
    b_files = [
        FileContent(path="backend/src/index.js", content="require('./routes/missing');")
    ]
    errs = iv.validate_local_imports(b_files, "Backend")
    assert errs


def test_3_valid_nested_relative():
    b_files = [
        FileContent(
            path="backend/src/controllers/user.js",
            content="require('../services/userService');",
        ),
        FileContent(path="backend/src/services/userService.js", content=""),
    ]
    errs = iv.validate_local_imports(b_files, "Backend")
    assert not errs


def test_4_external_dependency():
    b_files = [
        FileContent(
            path="backend/src/index.js", content="require('express');\nrequire('cors');"
        )
    ]
    errs = iv.validate_local_imports(b_files, "Backend")
    assert not errs


def test_5_valid_named_export():
    b_files = [
        FileContent(
            path="backend/src/controllers/user.js",
            content="const { createUser } = require('../services/userService');",
        ),
        FileContent(
            path="backend/src/services/userService.js",
            content="module.exports = {\n createUser \n};",
        ),
    ]
    errs = ev.validate_cross_file_symbols(b_files, "Backend")
    assert not errs


def test_6_missing_named_export():
    b_files = [
        FileContent(
            path="backend/src/controllers/user.js",
            content="const { createUser } = require('../services/userService');",
        ),
        FileContent(
            path="backend/src/services/userService.js",
            content="module.exports = {\n getUser \n};",
        ),
    ]
    errs = ev.validate_cross_file_symbols(b_files, "Backend")
    assert errs


def test_7_exports_foo():
    b_files = [
        FileContent(
            path="backend/src/controllers/user.js",
            content="const { createUser } = require('../services/userService');",
        ),
        FileContent(
            path="backend/src/services/userService.js",
            content="exports.createUser = createUser;",
        ),
    ]
    errs = ev.validate_cross_file_symbols(b_files, "Backend")
    assert not errs


def test_8_module_exports_foo():
    b_files = [
        FileContent(
            path="backend/src/controllers/user.js",
            content="const { createUser } = require('../services/userService');",
        ),
        FileContent(
            path="backend/src/services/userService.js",
            content="module.exports.createUser = createUser;",
        ),
    ]
    errs = ev.validate_cross_file_symbols(b_files, "Backend")
    assert not errs


def test_9_default_module_export():
    b_files = [
        FileContent(
            path="backend/src/controllers/user.js",
            content="const createUser = require('../services/userService');",
        ),
        FileContent(
            path="backend/src/services/userService.js",
            content="module.exports = createUser;",
        ),
    ]
    errs = ev.validate_cross_file_symbols(b_files, "Backend")
    assert not errs


def test_10_existing_topology_still_works():
    # Setup a temp workspace matching topology validator expectation
    tmp = tempfile.mkdtemp()
    try:
        backend_dir = os.path.join(tmp, "backend")
        os.mkdir(backend_dir)
        with open(os.path.join(backend_dir, "package.json"), "w") as f:
            json.dump({"main": "index.js"}, f)

        with open(os.path.join(backend_dir, "index.js"), "w") as f:
            f.write("require('./used.js');")

        with open(os.path.join(backend_dir, "used.js"), "w") as f:
            f.write("console.log('used');")

        with open(os.path.join(backend_dir, "unreachable.js"), "w") as f:
            f.write("console.log('orphaned');")

        errs = validate_topology(tmp)
        assert errs
        assert any("unreachable.js" in str(e) for e in errs)
    finally:
        shutil.rmtree(tmp)
