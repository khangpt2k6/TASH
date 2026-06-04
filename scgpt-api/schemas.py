"""Pydantic models for every public request and response payload.

Keeping schemas centralised means the OpenAPI document, the runtime
validation and the agent-tool description always stay in sync. Anything that
crosses the HTTP boundary lives here.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# Shared


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ErrorCode(str, Enum):
    invalid_request = "invalid_request"
    invalid_drive_url = "invalid_drive_url"
    download_failed = "download_failed"
    invalid_dataset = "invalid_dataset"
    missing_columns = "missing_columns"
    cuda_oom = "cuda_out_of_memory"
    model_error = "model_error"
    internal_error = "internal_error"
    not_found = "not_found"
    not_implemented = "not_implemented"


class ErrorResponse(BaseModel):
    error: ErrorCode
    message: str
    detail: Optional[str] = None
    request_id: Optional[str] = None


# /health


class HealthResponse(BaseModel):
    status: str = Field(examples=["healthy"])
    model_loaded: bool
    device: str = Field(examples=["cuda:0"])
    model_path: Optional[str] = None
    gpu_name: Optional[str] = None
    cuda_version: Optional[str] = None
    torch_version: Optional[str] = None
    uptime_seconds: Optional[float] = None
    version: Optional[str] = None

    # FastAPI uses ``model_`` as a reserved prefix on BaseModel; tell it we
    # are not shadowing internals.
    model_config = ConfigDict(protected_namespaces=())


# Common job/embedding request fields


class _BaseDatasetRequest(BaseModel):
    """Shared fields for any endpoint that consumes a Drive-hosted dataset."""

    dataset_url: HttpUrl = Field(
        ...,
        description="Public Google Drive share URL pointing to an .h5ad file.",
        examples=["https://drive.google.com/file/d/1abcDEF/view?usp=sharing"],
    )
    gene_col: str = Field(
        default="index",
        description=(
            "Name of the `adata.var` column that holds gene symbols. Use "
            "'index' to read directly from `adata.var.index`."
        ),
    )
    batch_key: Optional[str] = Field(
        default=None,
        description="Optional `adata.obs` column identifying the batch.",
    )
    cell_type_key: Optional[str] = Field(
        default=None,
        description="Optional `adata.obs` column identifying the cell type.",
    )
    batch_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Override the configured inference batch size.",
    )


# /embed


class EmbedRequest(_BaseDatasetRequest):
    pass


class EmbedResponse(BaseModel):
    job_id: str
    status: JobStatus
    n_cells: int
    n_genes_used: int
    embedding_dim: int
    embedding_file: str
    duration_seconds: float


# /umap


class UMAPRequest(_BaseDatasetRequest):
    n_neighbors: Optional[int] = Field(default=None, ge=2)
    min_dist: Optional[float] = Field(default=None, ge=0.0)
    color_by: Optional[List[str]] = Field(
        default=None,
        description=(
            "Override the configured list of `adata.obs` columns to colour "
            "the UMAP figure by. Missing columns are silently skipped."
        ),
    )


class UMAPResponse(BaseModel):
    job_id: str
    status: JobStatus
    n_cells: int
    embedding_dim: int
    umap_png: str
    umap_data: str
    embedding_file: str
    duration_seconds: float


# /annotate – placeholder


class AnnotateRequest(_BaseDatasetRequest):
    reference_url: Optional[HttpUrl] = Field(
        default=None,
        description=(
            "Google Drive URL of a labelled reference AnnData to map onto. "
            "When omitted the service will use the built-in pan-tissue "
            "reference once available."
        ),
    )
    annotation_key: str = Field(
        default="celltype",
        description="`adata.obs` column on the reference with cell-type labels.",
    )


class AnnotateResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str = Field(
        default=(
            "Cell-type annotation is not yet implemented; this endpoint "
            "currently returns the request schema only."
        )
    )
    # The following fields are populated once the implementation is complete.
    annotated_file: Optional[str] = None
    n_cells: Optional[int] = None
    n_classes: Optional[int] = None


# /job/{job_id}


class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    endpoint: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    request: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[ErrorResponse] = None
