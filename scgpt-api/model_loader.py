from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import scipy.sparse as sp
import torch
from anndata import AnnData

from config import Settings
from logging_config import get_logger

_LOG = get_logger("scgpt_api.model")


# Errors


class GPURequiredError(RuntimeError):
    """Raised when ``gpu.required`` is true and no CUDA device is visible."""


class ModelLoadError(RuntimeError):
    """Raised when the checkpoint cannot be loaded or assembled."""


class CudaOutOfMemoryError(RuntimeError):
    """Raised on a caught ``torch.cuda.OutOfMemoryError``."""


# Singleton


class ScGPTModel:
    """Lifecycle-managed wrapper around a loaded scGPT TransformerModel."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._loaded = False

        # GPU validation – must run first.
        if settings.gpu.required and not torch.cuda.is_available():
            raise GPURequiredError(
                "CUDA GPU is required but torch.cuda.is_available() returned "
                "False. Make sure the container is launched with GPU access "
                "(e.g. `docker run --gpus all` or a Kubernetes resource "
                "request of nvidia.com/gpu)."
            )

        device_id = settings.gpu.device_id
        if torch.cuda.device_count() <= device_id:
            raise GPURequiredError(
                f"Configured gpu.device_id={device_id} but only "
                f"{torch.cuda.device_count()} CUDA device(s) are visible."
            )

        self._device = torch.device(f"cuda:{device_id}")
        torch.cuda.set_device(self._device)

        if settings.gpu.memory_fraction > 0:
            torch.cuda.set_per_process_memory_fraction(
                settings.gpu.memory_fraction, device=device_id
            )

        self._gpu_name = torch.cuda.get_device_name(device_id)
        self._cuda_version = torch.version.cuda or "unknown"
        self._torch_version = torch.__version__

        _LOG.info(
            "gpu_detected",
            extra={
                "device": str(self._device),
                "gpu_name": self._gpu_name,
                "cuda_version": self._cuda_version,
                "torch_version": self._torch_version,
                "total_memory_gb": round(
                    torch.cuda.get_device_properties(device_id).total_memory
                    / (1024 ** 3),
                    2,
                ),
            },
        )

        # scGPT imports – done lazily so this file can be imported on a CPU
        # box for unit testing without scGPT installed.
        try:
            from scgpt.model import TransformerModel  # noqa: WPS433
            from scgpt.tokenizer.gene_tokenizer import GeneVocab  # noqa: WPS433
            from scgpt.preprocess import Preprocessor  # noqa: WPS433
        except Exception as exc:  # noqa: BLE001
            raise ModelLoadError(
                "Failed to import scGPT. Is the `scgpt` package installed "
                "in the runtime environment? "
                f"Original error: {exc}"
            ) from exc

        self._TransformerModel = TransformerModel
        self._GeneVocab = GeneVocab
        self._Preprocessor = Preprocessor

        # Load the model.
        self._model_dir = Path(settings.model.path)
        if not self._model_dir.is_dir():
            raise ModelLoadError(
                f"Model directory does not exist: {self._model_dir.resolve()}"
            )

        self._args_path = self._model_dir / "args.json"
        self._vocab_path = self._model_dir / "vocab.json"
        self._weights_path = self._model_dir / "best_model.pt"
        for p in (self._args_path, self._vocab_path, self._weights_path):
            if not p.exists():
                raise ModelLoadError(f"Missing required model artefact: {p}")

        load_started = time.monotonic()
        self._args: Dict[str, Any] = self.load_args()
        self._vocab = self.load_vocab()
        self._model = self.build_and_load_model()
        self._embsize: int = int(self._args.get("embsize") or self._args.get("d_model"))
        self._load_duration = time.monotonic() - load_started
        self._loaded = True

        _LOG.info(
            "model_loaded",
            extra={
                "model_dir": str(self._model_dir),
                "embedding_dim": self._embsize,
                "vocab_size": len(self._vocab),
                "load_duration_seconds": round(self._load_duration, 2),
                "n_parameters": sum(p.numel() for p in self._model.parameters()),
            },
        )

    # Public properties

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def device(self) -> torch.device:
        return self._device

    @property
    def embedding_dim(self) -> int:
        return self._embsize

    def info(self) -> Dict[str, Any]:
        return {
            "model_path": str(self._model_dir),
            "device": str(self._device),
            "gpu_name": self._gpu_name,
            "cuda_version": self._cuda_version,
            "torch_version": self._torch_version,
            "embedding_dim": self._embsize,
            "vocab_size": len(self._vocab),
            "load_duration_seconds": round(self._load_duration, 2),
        }

    # Loading internals

    def load_args(self) -> Dict[str, Any]:
        with self._args_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def load_vocab(self):
        vocab = self._GeneVocab.from_file(str(self._vocab_path))
        for token in self._settings.model.special_tokens:
            if token not in vocab:
                vocab.append_token(token)
        vocab.set_default_index(vocab[self._settings.model.pad_token])
        return vocab

    def build_and_load_model(self):
        ntokens = len(self._vocab)
        args = self._args

        d_model = int(args.get("embsize") or args.get("d_model"))
        nhead = int(args.get("nheads") or args.get("nhead"))
        d_hid = int(args.get("d_hid") or args.get("dim_feedforward") or 4 * d_model)
        nlayers = int(args.get("nlayers") or args.get("num_layers"))
        nlayers_cls = int(args.get("n_layers_cls") or args.get("nlayers_cls") or 3)
        dropout = float(args.get("dropout", 0.2))
        n_input_bins = int(
            args.get("n_input_bins")
            or self._settings.inference.preprocess.n_bins
        )

        try:
            model = self._TransformerModel(
                ntoken=ntokens,
                d_model=d_model,
                nhead=nhead,
                d_hid=d_hid,
                nlayers=nlayers,
                nlayers_cls=nlayers_cls,
                n_cls=1,
                vocab=self._vocab,
                dropout=dropout,
                pad_token=self._settings.model.pad_token,
                pad_value=self._settings.model.pad_value,
                do_mvc=True,
                do_dab=False,
                use_batch_labels=False,
                domain_spec_batchnorm=False,
                input_emb_style="continuous",
                n_input_bins=n_input_bins,
                cell_emb_style="cls",
                mvc_decoder_style="inner product",
                ecs_threshold=0.0,
                explicit_zero_prob=False,
                use_fast_transformer=self._settings.inference.use_fast_transformer,
                fast_transformer_backend="flash",
                pre_norm=False,
            )
        except TypeError as exc:
            raise ModelLoadError(
                "TransformerModel constructor rejected the supplied arguments. "
                "This usually means args.json is from an incompatible scGPT "
                f"version. Original error: {exc}"
            ) from exc

        checkpoint = torch.load(
            str(self._weights_path), map_location=self._device
        )
        # Some checkpoints are wrapped: {"model_state_dict": ...}.
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            checkpoint = checkpoint["model_state_dict"]

        if self._settings.model.load_partial_state_dict:
            current = model.state_dict()
            usable = {
                k: v for k, v in checkpoint.items()
                if k in current and current[k].shape == v.shape
            }
            skipped = sorted(set(checkpoint.keys()) - set(usable.keys()))
            current.update(usable)
            model.load_state_dict(current)
            if skipped:
                _LOG.warning(
                    "checkpoint_partial_load",
                    extra={
                        "skipped_keys": skipped[:25],
                        "skipped_total": len(skipped),
                        "loaded_total": len(usable),
                    },
                )
        else:
            model.load_state_dict(checkpoint)

        model.to(self._device)
        model.eval()
        return model

    # Inference

    @torch.no_grad()
    def encode_anndata(
        self,
        adata: AnnData,
        *,
        gene_col: str = "index",
        batch_size: Optional[int] = None,
        max_length: Optional[int] = None,
    ) -> Tuple[np.ndarray, AnnData]:
        """Compute one CLS embedding per cell using the resident model.

        Returns a tuple ``(embeddings, filtered_adata)``. ``filtered_adata`` is
        a view restricted to genes that are present in the scGPT vocabulary;
        the embedding rows correspond one-to-one with ``filtered_adata.obs``.
        """
        if not self._loaded:
            raise ModelLoadError("Model is not loaded.")

        batch_size = batch_size or self._settings.inference.batch_size
        max_length = max_length or self._settings.inference.max_seq_len

        # 1. Resolve gene names + intersect with vocab.
        gene_names = self.gene_names(adata, gene_col)
        in_vocab_mask = np.array(
            [gene in self._vocab for gene in gene_names], dtype=bool
        )
        n_kept = int(in_vocab_mask.sum())
        if n_kept == 0:
            raise ValueError(
                "None of the genes in the dataset overlap with the scGPT "
                "vocabulary. Check the `gene_col` parameter."
            )

        adata = adata[:, in_vocab_mask].copy()
        kept_gene_ids = np.array(
            [self._vocab[g] for g in (
                gene_names[i] for i in np.where(in_vocab_mask)[0]
            )],
            dtype=np.int64,
        )

        _LOG.info(
            "encode_start",
            extra={
                "n_cells": adata.n_obs,
                "n_genes_total": len(in_vocab_mask),
                "n_genes_in_vocab": n_kept,
                "batch_size": batch_size,
                "max_length": max_length,
            },
        )

        # 2. Preprocess to the binned representation scGPT expects.
        self.preprocess_anndata(adata)
        counts = adata.layers["X_binned"]
        if sp.issparse(counts):
            counts = counts.toarray()
        counts = np.asarray(counts, dtype=np.float32)

        # 3. Tokenise + forward pass in batches.
        pad_id = self._vocab[self._settings.model.pad_token]
        pad_value = float(self._settings.model.pad_value)
        cls_id = self._vocab["<cls>"]

        n_cells = counts.shape[0]
        embeddings = np.zeros((n_cells, self._embsize), dtype=np.float32)

        start_ts = time.monotonic()
        try:
            with self._lock:
                for start in range(0, n_cells, batch_size):
                    end = min(start + batch_size, n_cells)
                    gene_t, value_t = self.tokenise_batch(
                        counts[start:end],
                        kept_gene_ids,
                        max_length=max_length,
                        pad_id=pad_id,
                        pad_value=pad_value,
                        cls_id=cls_id,
                    )
                    gene_t = gene_t.to(self._device, non_blocking=True)
                    value_t = value_t.to(self._device, non_blocking=True)
                    mask = gene_t.eq(pad_id)

                    with torch.amp.autocast(device_type="cuda", enabled=True):
                        encoded = self._model._encode(
                            gene_t, value_t, src_key_padding_mask=mask
                        )
                    cell_emb = encoded[:, 0, :].float().cpu().numpy()
                    embeddings[start:end] = cell_emb
        except torch.cuda.OutOfMemoryError as exc:
            torch.cuda.empty_cache()
            raise CudaOutOfMemoryError(
                "GPU ran out of memory during inference. Retry with a "
                f"smaller batch_size (current={batch_size})."
            ) from exc

        duration = time.monotonic() - start_ts

        # 4. L2-normalise. scGPT cell embeddings are typically compared by
        #    cosine similarity downstream.
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        embeddings = embeddings / norms

        _LOG.info(
            "encode_complete",
            extra={
                "n_cells": n_cells,
                "embedding_dim": self._embsize,
                "duration_seconds": round(duration, 3),
                "cells_per_second": round(n_cells / max(duration, 1e-6), 2),
            },
        )
        return embeddings, adata

    # Helpers

    @staticmethod
    def gene_names(adata: AnnData, gene_col: str) -> List[str]:
        if gene_col == "index":
            return adata.var.index.astype(str).tolist()
        if gene_col not in adata.var.columns:
            raise KeyError(
                f"gene_col={gene_col!r} is not a column of adata.var. "
                f"Available columns: {list(adata.var.columns)}"
            )
        return adata.var[gene_col].astype(str).tolist()

    def preprocess_anndata(self, adata: AnnData) -> None:
        """Run scGPT's standard normalisation + binning pipeline."""
        cfg = self._settings.inference.preprocess
        preprocessor = self._Preprocessor(
            use_key="X",
            filter_gene_by_counts=False,
            filter_cell_by_counts=False,
            normalize_total=cfg.normalize_total,
            result_normed_key="X_normed",
            log1p=cfg.log1p,
            result_log1p_key="X_log1p",
            subset_hvg=False,
            hvg_flavor="seurat_v3",
            binning=cfg.n_bins,
            result_binned_key="X_binned",
        )
        preprocessor(adata, batch_key=None)

    @staticmethod
    def tokenise_batch(
        batch_counts: np.ndarray,
        gene_ids: np.ndarray,
        *,
        max_length: int,
        pad_id: int,
        pad_value: float,
        cls_id: int,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Build padded (gene_ids, values) tensors with a CLS token prepended."""
        rows_genes: List[np.ndarray] = []
        rows_values: List[np.ndarray] = []
        cls_value = 0.0

        for row in batch_counts:
            nz = np.nonzero(row)[0]
            # Reserve one slot for the CLS token.
            if nz.size > max_length - 1:
                # Keep the top-expressing genes; this is what scGPT's
                # DataCollator does when sequences exceed max_length.
                order = np.argsort(row[nz])[::-1][: max_length - 1]
                nz = nz[order]

            row_gene_ids = np.concatenate(
                ([cls_id], gene_ids[nz].astype(np.int64))
            )
            row_values = np.concatenate(
                ([cls_value], row[nz].astype(np.float32))
            )
            rows_genes.append(row_gene_ids)
            rows_values.append(row_values)

        seq_len = max(len(x) for x in rows_genes)
        padded_genes = np.full((len(rows_genes), seq_len), pad_id, dtype=np.int64)
        padded_values = np.full(
            (len(rows_values), seq_len), pad_value, dtype=np.float32
        )
        for i, (g, v) in enumerate(zip(rows_genes, rows_values)):
            padded_genes[i, : len(g)] = g
            padded_values[i, : len(v)] = v

        return (
            torch.from_numpy(padded_genes),
            torch.from_numpy(padded_values),
        )


# Module-level singleton accessor.

_SINGLETON: Optional[ScGPTModel] = None
_SINGLETON_LOCK = threading.Lock()


def load_model(settings: Settings) -> ScGPTModel:
    """Idempotently construct the global ``ScGPTModel`` instance."""
    global _SINGLETON
    with _SINGLETON_LOCK:
        if _SINGLETON is None:
            _SINGLETON = ScGPTModel(settings)
        return _SINGLETON


def get_model() -> ScGPTModel:
    """Return the global model. Raises if ``load_model`` has not run."""
    if _SINGLETON is None:
        raise ModelLoadError(
            "scGPT model has not been initialised. The lifespan hook in "
            "app.py is responsible for calling load_model() at startup."
        )
    return _SINGLETON


def reset_model() -> None:
    """Drop the singleton (used by shutdown to free GPU memory)."""
    global _SINGLETON
    with _SINGLETON_LOCK:
        if _SINGLETON is not None:
            try:
                del _SINGLETON._model  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
            _SINGLETON = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
