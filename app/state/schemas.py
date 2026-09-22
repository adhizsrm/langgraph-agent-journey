from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field, model_validator, ConfigDict
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


class EnhancementPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_content: str = Field(
        ...,
        description="The exact lines in the file to replace, including leading whitespace.",
    )
    replacement_content: str = Field(
        ..., description="The new code to replace the target content."
    )

    @model_validator(mode="after")
    def validate_patch_changes_content(self) -> "EnhancementPatch":
        if self.target_content == self.replacement_content:
            raise ValueError(
                "EnhancementPatch is a no-op: target_content and "
                "replacement_content must be different."
            )
        return self


class EnhancementAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(..., description="Relative path of file")
    action: Literal["modify", "create", "delete"]
    patches: Optional[List[EnhancementPatch]] = Field(
        None, description="Only for 'modify' actions"
    )
    content: Optional[str] = Field(None, description="Full content for 'create' only")

    @model_validator(mode="after")
    def validate_action_fields(self) -> "EnhancementAction":
        if self.action == "modify":
            if not self.patches:
                raise ValueError(
                    "EnhancementAction with action='modify' MUST contain a non-empty 'patches' list."
                )
        return self


class ImplementationChecklist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requires_ui_changes: bool = Field(
        description="Does this feature require changes to DOM/JSX?"
    )
    requires_stylesheet_changes: bool = Field(
        description="Does this feature require modifying dedicated CSS/SCSS stylesheet files? Set to False when styling can be implemented using Tailwind utility classes, inline styles, CSS-in-JS, or existing styling mechanisms without modifying a stylesheet file."
    )
    requires_logic_state: bool = Field(
        description="Does this change React state or logic?"
    )
    requires_backend_api: bool = Field(
        description="Does this require backend API/route changes?"
    )


class EnhancementAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: str
    checklist: ImplementationChecklist
    target_files: List[str] = Field(
        description="The exact list of files you intend to modify, create, or delete"
    )
    changes: List[EnhancementAction]

    @model_validator(mode="after")
    def validate_semantic_completeness(self) -> "EnhancementAnalysis":
        # 1. Internal Consistency: any file changed must be declared in target_files
        expected_files = set(self.target_files)
        actual_files = set(action.file for action in self.changes)

        extra = actual_files - expected_files
        if extra:
            raise ValueError(
                f"Mismatch: Files modified {extra} but not declared in target_files."
            )

        missing = expected_files - actual_files
        if missing:
            raise ValueError(
                f"Mismatch between target_files and changes: Files declared in target_files {missing} but no corresponding changes were generated."
            )

        # 2. Structural Implementation Intent
        tf_lower = [f.lower() for f in self.target_files]
        if self.checklist.requires_stylesheet_changes:
            if not any(f.endswith(".css") or f.endswith(".scss") for f in tf_lower):
                raise ValueError(
                    "Checklist requires_stylesheet_changes=True but no .css/.scss file is in target_files."
                )
        else:
            actual_changes = [action.file.lower() for action in self.changes]
            css_changes = [
                f for f in actual_changes if f.endswith(".css") or f.endswith(".scss")
            ]
            if css_changes:
                raise ValueError(
                    f"API Contract Violation: requires_stylesheet_changes=False but CSS/SCSS modifications were generated in: {css_changes}. "
                    "If dedicated stylesheet changes are genuinely required, requires_stylesheet_changes must be True."
                )

        if self.checklist.requires_backend_api:
            if not any("backend/" in f for f in tf_lower):
                raise ValueError(
                    "Checklist requires_backend_api=True but no backend/ file is in target_files."
                )
        else:
            actual_changes = [action.file.lower() for action in self.changes]
            backend_changes = [f for f in actual_changes if "backend/" in f]
            if backend_changes:
                raise ValueError(
                    f"API Contract Violation: requires_backend_api=False but backend changes were generated in: {backend_changes}. "
                    "If the existing backend API ALREADY supports the capability, do NOT modify the backend files. "
                    "If backend changes are genuinely required, requires_backend_api must be True."
                )

        if self.checklist.requires_ui_changes:
            if not any(
                f.endswith(".jsx") or f.endswith(".tsx") or f.endswith(".html")
                for f in tf_lower
            ):
                raise ValueError(
                    "Checklist requires_ui_changes=True but no .jsx/.tsx/.html file is in target_files."
                )

        return self


class GraphState(TypedDict):
    # Inputs
    mode: Literal["create", "enhance"]
    raw_goal: str
    target_project_path: str
    directory_listing: str

    # Enhancement Additions
    source_project_path: Optional[str]
    enhancement_files_to_read: Optional[List[str]]
    enhancement_chunks: Optional[List[dict]]

    # Agent Outputs (additive)
    orchestrator_spec: Optional[OrchestratorOutput]
    backend_files: Optional[GeneratedFiles]
    frontend_files: Optional[GeneratedFiles]

    # Final Output / Status
    error: Optional[str]
    conflicts: Optional[List[str]]
    written_files: Optional[List[str]]
    validation_errors: Optional[List[str]]
    safety_errors: Optional[List[str]]

    # Phase 18 Additions
    execution_result: Optional[Dict[str, Any]]
    repair_attempts: int
    repair_history: List[Dict[str, Any]]
    workspace_path: Optional[str]
    workflow_status: Optional[str]
