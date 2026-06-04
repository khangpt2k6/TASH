"""High-level inference pipelines: ``embed`` and ``umap``.

These functions are the glue between the FastAPI endpoints and the lower
layers (downloader, model singleton). They:

1. Open the downloaded ``.h5ad`` file.
2. Validate the requested ``obs`` columns exist.
3. Call ``ScGPTModel.encode_anndata`` (using the resident GPU model).
4. Persist the resulting AnnData / figure / CSV under ``outputs/``.
5. Return a typed result that the endpoint serialises straight back.

No HTTP concerns leak into this module – it can be unit-tested by feeding
in a local ``.h5ad`` path and a fake ``ScGPTModel``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import anndata as ad
import matplotlib

# Use a non-interactive backend; servers don't have a display.
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import scanpy as sc  # noqa: E402

from config import Settings  # noqa: E402
from logging_config import get_logger  # noqa: E402
from model_loader import ScGPTModel  # noqa: E402

_LOG = get_logger("scgpt_api.inference")


# Errors


class InvalidDatasetError(ValueError):
    """The .h5ad file could not be opened or is structurally invalid."""


class MissingColumnError(KeyError):
    """A requested obs/var column is not present in the AnnData."""


# Result types


@dataclass(frozen=True)
class EmbedResult:
    n_cells: int
    n_genes_used: int
    embedding_dim: int
    embedding_file: str
    duration_seconds: float


@dataclass(frozen=True)
class UMAPResult:
    n_cells: int
    embedding_dim: int
    embedding_file: str
    umap_png: str
    umap_data: str
    duration_seconds: float


# Public functions


def load_anndata(path: Path) -> ad.AnnData:
    """Open an ``.h5ad`` with friendly error reporting."""
    if not path.exists():
        raise InvalidDatasetError(f"Dataset file not found: {path}")
    try:
        adata = ad.read_h5ad(path)
    except Exception as exc:  # noqa: BLE001
        raise InvalidDatasetError(
            f"Failed to read AnnData from {path.name}: {exc}"
        ) from exc

    if adata.n_obs == 0 or adata.n_vars == 0:
        raise InvalidDatasetError(
            f"AnnData has empty shape {adata.shape}. Nothing to embed."
        )
    return adata


def validate_columns(
    adata: ad.AnnData,
    *,
    obs_cols: Optional[List[str]] = None,
    var_cols: Optional[List[str]] = None,
) -> None:
    """Raise :class:`MissingColumnError` if any requested column is absent."""
    if obs_cols:
        missing = [c for c in obs_cols if c and c not in adata.obs.columns]
        if missing:
            raise MissingColumnError(
                f"adata.obs is missing column(s): {missing}. "
                f"Available: {list(adata.obs.columns)}"
            )
    if var_cols:
        missing = [
            c for c in var_cols
            if c and c != "index" and c not in adata.var.columns
        ]
        if missing:
            raise MissingColumnError(
                f"adata.var is missing column(s): {missing}. "
                f"Available: {list(adata.var.columns)}"
            )


def run_embed(
    *,
    job_id: str,
    dataset_path: Path,
    settings: Settings,
    model: ScGPTModel,
    gene_col: str = "index",
    batch_key: Optional[str] = None,
    cell_type_key: Optional[str] = None,
    batch_size: Optional[int] = None,
) -> EmbedResult:
    """Run scGPT embedding on the given dataset and persist the result."""
    started = time.monotonic()
    adata = load_anndata(dataset_path)
    validate_columns(
        adata,
        obs_cols=[c for c in (batch_key, cell_type_key) if c],
        var_cols=[gene_col],
    )

    embeddings, filtered = model.encode_anndata(
        adata, gene_col=gene_col, batch_size=batch_size
    )

    filtered.obsm["X_scGPT"] = embeddings
    filtered.uns["scGPT_embedding"] = {
        "model_path": settings.model.path,
        "embedding_dim": int(embeddings.shape[1]),
        "gene_col": gene_col,
        "batch_size": batch_size or settings.inference.batch_size,
    }

    out_path = Path(settings.paths.output_dir) / f"{job_id}_embed.h5ad"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.write_h5ad(out_path, compression="gzip")

    duration = time.monotonic() - started
    _LOG.info(
        "embed_persisted",
        extra={
            "job_id": job_id,
            "path": str(out_path),
            "n_cells": filtered.n_obs,
            "n_genes_used": filtered.n_vars,
            "embedding_dim": int(embeddings.shape[1]),
            "duration_seconds": round(duration, 3),
        },
    )
    return EmbedResult(
        n_cells=int(filtered.n_obs),
        n_genes_used=int(filtered.n_vars),
        embedding_dim=int(embeddings.shape[1]),
        embedding_file=str(out_path),
        duration_seconds=duration,
    )


def run_umap(
    *,
    job_id: str,
    dataset_path: Path,
    settings: Settings,
    model: ScGPTModel,
    gene_col: str = "index",
    batch_key: Optional[str] = None,
    cell_type_key: Optional[str] = None,
    batch_size: Optional[int] = None,
    n_neighbors: Optional[int] = None,
    min_dist: Optional[float] = None,
    color_by: Optional[List[str]] = None,
) -> UMAPResult:
    """Embed -> neighbors -> UMAP, persist h5ad + PNG + CSV."""
    started = time.monotonic()
    adata = load_anndata(dataset_path)
    validate_columns(
        adata,
        obs_cols=[c for c in (batch_key, cell_type_key) if c],
        var_cols=[gene_col],
    )

    embeddings, filtered = model.encode_anndata(
        adata, gene_col=gene_col, batch_size=batch_size
    )
    filtered.obsm["X_scGPT"] = embeddings

    n_neighbors = n_neighbors or settings.umap.n_neighbors
    min_dist = min_dist if min_dist is not None else settings.umap.min_dist

    # Cap n_neighbors at n_obs-1 to avoid scanpy errors on tiny datasets.
    n_neighbors = max(2, min(n_neighbors, filtered.n_obs - 1))

    sc.pp.neighbors(
        filtered,
        n_neighbors=n_neighbors,
        use_rep="X_scGPT",
        metric=settings.umap.metric,
    )
    sc.tl.umap(filtered, min_dist=min_dist)

    out_dir = Path(settings.paths.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    h5ad_path = out_dir / f"{job_id}_umap.h5ad"
    png_path = out_dir / f"{job_id}_umap.png"
    csv_path = out_dir / f"{job_id}_umap.csv"

    filtered.write_h5ad(h5ad_path, compression="gzip")

    requested_colors = color_by or settings.umap.color_by
    available_colors = [c for c in requested_colors if c in filtered.obs.columns]

    render_umap(
        filtered,
        png_path,
        color_keys=available_colors,
        figsize=settings.umap.figsize,
        dpi=settings.umap.dpi,
    )

    umap_coords = filtered.obsm["X_umap"]
    coord_df = pd.DataFrame(
        {
            "cell_id": filtered.obs_names.astype(str),
            "umap_1": umap_coords[:, 0],
            "umap_2": umap_coords[:, 1],
        }
    )
    for col in available_colors:
        coord_df[col] = filtered.obs[col].astype(str).to_numpy()
    coord_df.to_csv(csv_path, index=False)

    duration = time.monotonic() - started
    _LOG.info(
        "umap_persisted",
        extra={
            "job_id": job_id,
            "umap_png": str(png_path),
            "umap_csv": str(csv_path),
            "h5ad": str(h5ad_path),
            "n_cells": filtered.n_obs,
            "duration_seconds": round(duration, 3),
        },
    )
    return UMAPResult(
        n_cells=int(filtered.n_obs),
        embedding_dim=int(embeddings.shape[1]),
        embedding_file=str(h5ad_path),
        umap_png=str(png_path),
        umap_data=str(csv_path),
        duration_seconds=duration,
    )


# Plot helper


def render_umap(
    adata: ad.AnnData,
    out_path: Path,
    *,
    color_keys: List[str],
    figsize,
    dpi: int,
) -> None:
    """Render a UMAP scatter, coloured by each available key in one figure."""
    coords = adata.obsm["X_umap"]
    if not color_keys:
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        ax.scatter(coords[:, 0], coords[:, 1], s=4, alpha=0.7, c="steelblue")
        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")
        ax.set_title("scGPT UMAP")
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(out_path, dpi=dpi)
        plt.close(fig)
        return

    n_panels = len(color_keys)
    fig, axes = plt.subplots(
        1, n_panels, figsize=(figsize[0] * n_panels, figsize[1]), dpi=dpi
    )
    if n_panels == 1:
        axes = [axes]

    for ax, key in zip(axes, color_keys):
        values = adata.obs[key].astype(str).to_numpy()
        uniques = np.unique(values)
        cmap = plt.get_cmap("tab20" if len(uniques) <= 20 else "viridis")
        for idx, label in enumerate(uniques):
            mask = values == label
            ax.scatter(
                coords[mask, 0],
                coords[mask, 1],
                s=5,
                alpha=0.75,
                color=cmap(idx % cmap.N),
                label=label,
            )
        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")
        ax.set_title(f"scGPT UMAP – {key}")
        ax.spines[["top", "right"]].set_visible(False)
        # Show a legend only when it stays readable.
        if len(uniques) <= 25:
            ax.legend(
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                fontsize=8,
                frameon=False,
            )

    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
