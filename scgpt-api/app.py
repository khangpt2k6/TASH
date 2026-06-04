"""FastAPI application: HTTP surface for the scGPT inference service.

Endpoints
---------

* ``GET  /health``        – liveness + model + GPU report
* ``POST /embed``         – Drive URL -> scGPT cell embeddings (.h5ad)
* ``POST /umap``          – Drive URL -> embeddings -> UMAP figure + CSV
* ``POST /annotate``      – placeholder for future reference mapping
* ``GET  /job/{job_id}``  – inspect the status / result / error of any job
* ``GET  /``              – pointer to /docs and /health

Cross-cutting behaviour:

* The scGPT model is loaded once during the lifespan startup hook and stored
  on ``app.state.model``. Endpoints depend on the singleton via FastAPI's
  dependency-injection helpers below.
* Every request gets a UUID stamped into a ContextVar so the JSON logs can be
  correlated end-to-end.
* All exceptions raised by the inference layer are mapped to typed
  :class:`ErrorResponse` payloads with appropriate HTTP status codes.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import torch
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from config import Settings, get_settings
from gdrive import (
    DownloadError,
    GoogleDriveDownloader,
    InvalidDriveUrlError,
)
from inference import (
    InvalidDatasetError,
    MissingColumnError,
    run_embed,
    run_umap,
)
from jobs import JobStore
from logging_config import configure_logging, get_logger, request_id_var
from model_loader import (
    CudaOutOfMemoryError,
    GPURequiredError,
    ModelLoadError,
    ScGPTModel,
    load_model,
    reset_model,
)
from schemas import (
    AnnotateRequest,
    AnnotateResponse,
    EmbedRequest,
    EmbedResponse,
    ErrorCode,
    ErrorResponse,
    HealthResponse,
    JobInfo,
    JobStatus,
    UMAPRequest,
    UMAPResponse,
)


# Lifespan: load the model, create singletons, free GPU on shutdown.


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = get_settings()
    configure_logging(settings.logging)
    log = get_logger("scgpt_api.app")

    log.info(
        "app_startup",
        extra={
            "config_path": settings.config_path,
            "app_name": settings.app.name,
            "app_version": settings.app.version,
        },
    )

    # Loading the model is what triggers the CUDA check; we want startup to
    # fail loudly if the GPU is not available.
    try:
        model = load_model(settings)
    except (GPURequiredError, ModelLoadError):
        log.exception("model_load_failed")
        raise

    app.state.settings = settings
    app.state.model = model
    app.state.downloader = GoogleDriveDownloader(
        settings.paths.cache_dir, settings.download
    )
    app.state.jobs = JobStore(max_history=settings.jobs.max_history)
    app.state.started_at = time.monotonic()

    log.info("app_ready", extra=model.info())

    try:
        yield
    finally:
        log.info("app_shutdown")
        reset_model()


# Application factory.


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        description=(
            "Production-ready REST service exposing the pretrained scGPT "
            "model for single-cell embedding and UMAP visualisation. "
            "Designed for deployment on Azure VMs, Azure Container Apps "
            "and Azure Kubernetes Service with NVIDIA GPU support."
        ),
        lifespan=lifespan,
    )

    register_middleware(app)
    register_exception_handlers(app)
    register_routes(app)
    return app


# Middleware: request-id injection + access logging.


def register_middleware(app: FastAPI) -> None:
    log = get_logger("scgpt_api.http")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        # Prefer a client-provided X-Request-Id (useful when the agent
        # platform already has its own correlation id).
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.monotonic()

        try:
            response = await call_next(request)
            duration_ms = (time.monotonic() - start) * 1000
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "client": request.client.host if request.client else None,
                },
            )
            response.headers["x-request-id"] = rid
            return response
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            log.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise
        finally:
            request_id_var.reset(token)


# Dependency injection helpers.


def inject_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def inject_model(request: Request) -> ScGPTModel:
    model = request.app.state.model
    if model is None or not model.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded",
        )
    return model


def inject_downloader(request: Request) -> GoogleDriveDownloader:
    return request.app.state.downloader  # type: ignore[no-any-return]


def inject_jobs(request: Request) -> JobStore:
    return request.app.state.jobs  # type: ignore[no-any-return]


# Exception handlers – everything ends up as a typed ErrorResponse.


def build_error(code: ErrorCode, message: str, detail: Optional[str] = None) -> Dict[str, Any]:
    return ErrorResponse(
        error=code,
        message=message,
        detail=detail,
        request_id=request_id_var.get(),
    ).model_dump(mode="json")


def register_exception_handlers(app: FastAPI) -> None:
    log = get_logger("scgpt_api.errors")

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=build_error(
                ErrorCode.invalid_request,
                "Request payload failed validation.",
                str(exc.errors()),
            ),
        )

    @app.exception_handler(InvalidDriveUrlError)
    async def handle_bad_drive_url(_: Request, exc: InvalidDriveUrlError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=build_error(ErrorCode.invalid_drive_url, str(exc)),
        )

    @app.exception_handler(DownloadError)
    async def handle_download_failed(_: Request, exc: DownloadError):
        log.error("download_failed", extra={"error": str(exc)})
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=build_error(ErrorCode.download_failed, str(exc)),
        )

    @app.exception_handler(InvalidDatasetError)
    async def handle_bad_dataset(_: Request, exc: InvalidDatasetError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=build_error(ErrorCode.invalid_dataset, str(exc)),
        )

    @app.exception_handler(MissingColumnError)
    async def handle_missing_columns(_: Request, exc: MissingColumnError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=build_error(ErrorCode.missing_columns, str(exc)),
        )

    @app.exception_handler(CudaOutOfMemoryError)
    async def handle_cuda_oom(_: Request, exc: CudaOutOfMemoryError):
        log.error("cuda_oom", extra={"error": str(exc)})
        return JSONResponse(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            content=build_error(ErrorCode.cuda_oom, str(exc)),
        )

    @app.exception_handler(ModelLoadError)
    async def handle_model_error(_: Request, exc: ModelLoadError):
        log.error("model_error", extra={"error": str(exc)})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=build_error(ErrorCode.model_error, str(exc)),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error(
                ErrorCode.invalid_request
                if exc.status_code < 500
                else ErrorCode.internal_error,
                str(exc.detail),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unhandled(_: Request, exc: Exception):
        log.exception("unhandled_exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=build_error(
                ErrorCode.internal_error,
                "Unexpected internal error.",
                f"{type(exc).__name__}: {exc}",
            ),
        )


# Routes.


def register_routes(app: FastAPI) -> None:

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": app.title,
            "version": app.version,
            "docs": "/docs",
            "health": "/health",
        }

    # Health.

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health(
        request: Request,
        model: ScGPTModel = Depends(inject_model),
        settings: Settings = Depends(inject_settings),
    ) -> HealthResponse:
        uptime = time.monotonic() - getattr(
            request.app.state, "started_at", time.monotonic()
        )
        info = model.info()
        return HealthResponse(
            status="healthy",
            model_loaded=model.is_loaded,
            device=str(model.device),
            model_path=info["model_path"],
            gpu_name=info["gpu_name"],
            cuda_version=info["cuda_version"],
            torch_version=info["torch_version"],
            uptime_seconds=round(uptime, 2),
            version=settings.app.version,
        )

    # /embed.

    @app.post(
        "/embed",
        response_model=EmbedResponse,
        responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
        tags=["inference"],
    )
    async def embed(
        payload: EmbedRequest,
        settings: Settings = Depends(inject_settings),
        model: ScGPTModel = Depends(inject_model),
        downloader: GoogleDriveDownloader = Depends(inject_downloader),
        jobs: JobStore = Depends(inject_jobs),
    ) -> EmbedResponse:
        job = jobs.create(
            endpoint="/embed",
            request=payload.model_dump(mode="json"),
        )

        try:
            jobs.mark_running(job.job_id)
            dl = downloader.download(str(payload.dataset_url))
            result = run_embed(
                job_id=job.job_id,
                dataset_path=dl.path,
                settings=settings,
                model=model,
                gene_col=payload.gene_col,
                batch_key=payload.batch_key,
                cell_type_key=payload.cell_type_key,
                batch_size=payload.batch_size,
            )
        except Exception as exc:  # noqa: BLE001
            jobs.mark_failed(
                job.job_id,
                ErrorResponse(
                    error=classify_exception(exc),
                    message=str(exc),
                    request_id=request_id_var.get(),
                ),
            )
            raise

        response = EmbedResponse(
            job_id=job.job_id,
            status=JobStatus.completed,
            n_cells=result.n_cells,
            n_genes_used=result.n_genes_used,
            embedding_dim=result.embedding_dim,
            embedding_file=result.embedding_file,
            duration_seconds=round(result.duration_seconds, 3),
        )
        jobs.mark_completed(job.job_id, response.model_dump(mode="json"))
        return response

    # /umap.

    @app.post(
        "/umap",
        response_model=UMAPResponse,
        responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
        tags=["inference"],
    )
    async def umap(
        payload: UMAPRequest,
        settings: Settings = Depends(inject_settings),
        model: ScGPTModel = Depends(inject_model),
        downloader: GoogleDriveDownloader = Depends(inject_downloader),
        jobs: JobStore = Depends(inject_jobs),
    ) -> UMAPResponse:
        job = jobs.create(
            endpoint="/umap",
            request=payload.model_dump(mode="json"),
        )

        try:
            jobs.mark_running(job.job_id)
            dl = downloader.download(str(payload.dataset_url))
            result = run_umap(
                job_id=job.job_id,
                dataset_path=dl.path,
                settings=settings,
                model=model,
                gene_col=payload.gene_col,
                batch_key=payload.batch_key,
                cell_type_key=payload.cell_type_key,
                batch_size=payload.batch_size,
                n_neighbors=payload.n_neighbors,
                min_dist=payload.min_dist,
                color_by=payload.color_by,
            )
        except Exception as exc:  # noqa: BLE001
            jobs.mark_failed(
                job.job_id,
                ErrorResponse(
                    error=classify_exception(exc),
                    message=str(exc),
                    request_id=request_id_var.get(),
                ),
            )
            raise

        response = UMAPResponse(
            job_id=job.job_id,
            status=JobStatus.completed,
            n_cells=result.n_cells,
            embedding_dim=result.embedding_dim,
            umap_png=result.umap_png,
            umap_data=result.umap_data,
            embedding_file=result.embedding_file,
            duration_seconds=round(result.duration_seconds, 3),
        )
        jobs.mark_completed(job.job_id, response.model_dump(mode="json"))
        return response

    # /annotate (placeholder).

    @app.post(
        "/annotate",
        response_model=AnnotateResponse,
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        responses={501: {"model": ErrorResponse}},
        tags=["inference"],
    )
    async def annotate(
        payload: AnnotateRequest,  # noqa: ARG001 – validated for the agent
        jobs: JobStore = Depends(inject_jobs),
    ) -> JSONResponse:
        """Placeholder for scGPT reference-mapping cell-type annotation.

        The request/response schemas are finalised so the endpoint can be
        wired into agent tooling today; the implementation will be added in
        a follow-up release.
        """
        job = jobs.create(
            endpoint="/annotate",
            request=payload.model_dump(mode="json"),
        )
        body = AnnotateResponse(
            job_id=job.job_id,
            status=JobStatus.pending,
        )
        jobs.mark_failed(
            job.job_id,
            ErrorResponse(
                error=ErrorCode.not_implemented,
                message=body.message,
                request_id=request_id_var.get(),
            ),
        )
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content=body.model_dump(mode="json"),
        )

    # /job/{job_id}.

    @app.get(
        "/job/{job_id}",
        response_model=JobInfo,
        responses={404: {"model": ErrorResponse}},
        tags=["jobs"],
    )
    async def get_job(
        job_id: str,
        jobs: JobStore = Depends(inject_jobs),
    ) -> JobInfo:
        info = jobs.get(job_id)
        if info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown job_id: {job_id}",
            )
        return info


# Exception -> ErrorCode mapping.


def classify_exception(exc: Exception) -> ErrorCode:
    """Used by /embed and /umap to record a typed error on the failed job."""
    if isinstance(exc, InvalidDriveUrlError):
        return ErrorCode.invalid_drive_url
    if isinstance(exc, DownloadError):
        return ErrorCode.download_failed
    if isinstance(exc, InvalidDatasetError):
        return ErrorCode.invalid_dataset
    if isinstance(exc, MissingColumnError):
        return ErrorCode.missing_columns
    if isinstance(exc, CudaOutOfMemoryError) or isinstance(exc, torch.cuda.OutOfMemoryError):
        return ErrorCode.cuda_oom
    if isinstance(exc, (ModelLoadError, GPURequiredError)):
        return ErrorCode.model_error
    return ErrorCode.internal_error


# ASGI: uvicorn app:app

app = create_app()


if __name__ == "__main__":
    # Dev: python app.py | Prod: uvicorn app:app
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app:app",
        host=settings.app.host,
        port=settings.app.port,
        workers=settings.app.workers,
        timeout_keep_alive=settings.app.request_timeout_seconds,
        log_config=None,
    )
