import os
import json
import pytest
from app.state.schemas import FileContent, GeneratedFiles
from app.agents.repair_agent import project_repair_node


def test_dependency_aware_context(monkeypatch):
    # Mock LLM to avoid real calls
    class MockResult:
        analysis = "mock"
        changes = []

    class MockLLM:
        def invoke(self, prompt):
            self.last_prompt = prompt
            return MockResult()

    mock_llm = MockLLM()
    monkeypatch.setattr("app.agents.repair_agent.repair_llm", mock_llm)

    # Simple explicit dependency graph
    # routes.js -> controller.js -> service.js -> model.js
    file_map = {
        "backend/src/routes.js": "const ctrl = require('./controller');",
        "backend/src/controller.js": "const serv = require('./service');",
        "backend/src/service.js": "const mod = require('./model');",
        "backend/src/model.js": "module.exports = {};",
        "backend/src/unrelated.js": "const nothing = require('nothing');",
    }

    b_files = [FileContent(path=p, content=c) for p, c in file_map.items()]

    mock_state = {
        "mode": "create",
        "repair_attempts": 1,
        "backend_files": GeneratedFiles(files=b_files),
        "frontend_files": GeneratedFiles(files=[]),
        "validation_errors": ["Error inside backend/src/service.js: Missing symbol"],
        "workspace_path": "/mock/workspace",  # Dummy for safe checks
    }

    updated_state = project_repair_node(mock_state)
    prompt = mock_llm.last_prompt

    # Assertions
    # Unrelated files MUST be excluded from the file content blocks
    relevant_context = prompt.split("EXISTING PROJECT FILES:")[0]
    assert "backend/src/unrelated.js" not in relevant_context
    # Core error file MUST be included
    assert "backend/src/service.js" in prompt
    # Forward dependency (model) MUST be included
    assert "backend/src/model.js" in prompt
    # Reverse dependency (controller) MUST be included
    assert "backend/src/controller.js" in prompt

    # Assert Repair Ordering:
    # Model (dependency) should ideally appear BEFORE Service (root error) in the output
    # By counting forward dependencies: Model has 0, Service has 1, Controller has 2, Routes has 3
    # The prioritization sorts specifically putting dependencies BEFORE consumers -> Model first!

    # Extract the actual relevant repair context section securely bypassing validation headers.
    context_split_marker = "RELEVANT REPAIR CONTEXT"
    assert context_split_marker in prompt
    context_section = prompt.split(context_split_marker)[1]

    idx_model = context_section.find("backend/src/model.js")
    idx_service = context_section.find("backend/src/service.js")
    idx_controller = context_section.find("backend/src/controller.js")

    assert idx_model != -1 and idx_service != -1 and idx_controller != -1

    # Validate ordering correctness: Ascending forward dep count!
    # Model (0 forward deps)
    # Service (1 forward dep)
    # Controller (2 forward deps)
    assert idx_model < idx_service
    assert idx_service < idx_controller


def test_package_contradiction(monkeypatch):
    class MockResult:
        analysis = "mock"
        changes = []

    class MockLLM:
        def invoke(self, prompt):
            self.last_prompt = prompt
            return MockResult()

    mock_llm = MockLLM()
    monkeypatch.setattr("app.agents.repair_agent.repair_llm", mock_llm)

    # Fake a missing react dependency error when react is clearly in package.json
    file_map = {
        "frontend/package.json": '{"dependencies": {"react": "^18.2.0"}}',
        "frontend/src/App.jsx": "import React from 'react';",
    }
    f_files = [FileContent(path=p, content=c) for p, c in file_map.items()]

    mock_state = {
        "mode": "create",
        "repair_attempts": 1,
        "backend_files": GeneratedFiles(files=[]),
        "frontend_files": GeneratedFiles(files=f_files),
        "validation_errors": ["Cannot find module 'react'"],
    }

    project_repair_node(mock_state)

    prompt = mock_llm.last_prompt
    assert "PACKAGE DEPENDENCY NOTE" in prompt


def test_relative_import_context_resolution(monkeypatch):
    class MockResult:
        analysis = "mock"
        changes = []

    class MockLLM:
        def invoke(self, prompt):
            self.last_prompt = prompt
            return MockResult()

    mock_llm = MockLLM()
    monkeypatch.setattr("app.agents.repair_agent.repair_llm", mock_llm)

    file_map = {
        "backend/services/noteService.js": "const notes = []; export const createNote = () => {};",
        "backend/controllers/noteController.js": "import noteService from '../services/noteService';",
    }
    b_files = [FileContent(path=p, content=c) for p, c in file_map.items()]

    mock_state = {
        "mode": "create",
        "repair_attempts": 1,
        "backend_files": GeneratedFiles(files=b_files),
        "frontend_files": GeneratedFiles(files=[]),
        # The exact format of the error with relative import
        "validation_errors": [
            "Error: backend/controllers/noteController.js imports the default export from '../services/noteService', but it has no default export."
        ],
    }

    project_repair_node(mock_state)

    prompt = mock_llm.last_prompt
    relevant_context = prompt.split("EXISTING PROJECT FILES:")[0]

    # Verify both the filename and the actual content is parsed firmly in context
    assert "backend/services/noteService.js" in relevant_context
    assert "export const createNote = () => {};" in relevant_context
