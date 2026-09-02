from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ---------------------------------------------------------
# SHARED STATE SCHEMA
# ---------------------------------------------------------
class FileContent(BaseModel):
    path: str = Field(
        ...,
        description="Relative path where the file should be written, e.g., 'backend/src/routes/task.ts'",
    )
    content: str = Field(..., description="The full source code content of the file")


class EntitySpec(BaseModel):
    entity_name: str
    fields: Dict[str, str] = Field(
        ...,
        description="Mapping of field names to their inferred types (e.g. string, number, boolean)",
    )
    validation_rules: List[str] = Field(
        default_factory=list,
        description="Any inferred validation rules (e.g., 'title is required')",
    )


class APIContract(BaseModel):
    base_route: str = Field(..., description="Base route path, e.g., '/api/tasks'")
    operations: List[Dict[str, Any]] = Field(
        ...,
        description="List of operations with method, path, request shape, and response shape",
    )


class OrchestratorOutput(BaseModel):
    entity_spec: EntitySpec
    crud_operations: List[str] = Field(
        ...,
        description="List of operations in scope, e.g., ['Create', 'Read', 'Update', 'Delete']",
    )
    api_contract: APIContract
    execution_order: Literal["backend_first", "frontend_first"] = Field(
        ..., description="Which agent runs first"
    )
    file_locations: Dict[str, str] = Field(
        ...,
        description="Inferred target file locations, e.g. {'backend_routes': 'backend/src/routes/'}",
    )


class GeneratedFiles(BaseModel):
    files: List[FileContent] = Field(
        ..., description="List of all generated files for the agent's domain"
    )


class RepairAction(BaseModel):
    file: str
    action: Literal["modify", "create", "delete"]
    content: str


class RepairAnalysis(BaseModel):
    analysis: str
    changes: List[RepairAction]


class GraphState(TypedDict):
    # Inputs
    raw_goal: str
    target_project_path: str
    directory_listing: str

    # Agent Outputs (additive)
    orchestrator_spec: Optional[OrchestratorOutput]
    backend_files: Optional[GeneratedFiles]
    frontend_files: Optional[GeneratedFiles]

    # Final Output / Status
    error: Optional[str]
    conflicts: Optional[List[str]]
    written_files: Optional[List[str]]
    validation_errors: Optional[List[str]]

    # Phase 18 Additions
    execution_result: Optional[Dict[str, Any]]
    repair_attempts: int
    repair_history: List[Dict[str, Any]]
    workspace_path: Optional[str]
    workflow_status: Optional[str]
