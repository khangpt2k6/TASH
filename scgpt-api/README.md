# scGPT API

Production-ready FastAPI service that wraps a pretrained
[scGPT](https://github.com/bowang-lab/scGPT) checkpoint and exposes it as a
GPU-backed REST API. Designed to be embedded as a skill / tool inside an
agent platform such as OpenClaw, and to be deployed unchanged on:

* an Azure VM with an NVIDIA GPU,
* Azure Container Apps with a GPU workload profile, or
* Azure Kubernetes Service with the NVIDIA device plugin.

The user-facing contract is:

```text
client → POST /embed { dataset_url }
                ↓
   Download .h5ad from Google Drive
                ↓
       scGPT inference on GPU
                ↓
   Save outputs, return metadata
```

---

## Project layout

```text
scgpt-api/
├── app.py                 # FastAPI app, routes, error handlers, lifespan
├── model_loader.py        # GPU-resident scGPT singleton
├── inference.py           # /embed + /umap pipelines using the singleton
├── gdrive.py              # Google Drive download + cache
├── jobs.py                # In-memory job store (job_id → status/result)
├── schemas.py             # Pydantic request / response models
├── config.py              # Typed YAML loader
├── config.yaml            # All runtime configuration
├── logging_config.py      # JSON / text rotating logger
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── save/
│   └── scGPT_human/       # ← drop args.json, vocab.json, best_model.pt here
├── cache/downloaded_datasets/
├── outputs/
└── logs/
```

---

## Runtime Python version

The container ships **Python 3.11**, not 3.12. The reason is purely a
dependency-resolution one: `scgpt==0.2.4` (the latest published release at
the time of writing) transitively requires `scvi-tools<1.0`, `torchtext`,
`cell-gears<0.0.3` and `orbax<0.1.8`, none of which publish Python-3.12
wheels. Python 3.11 is the highest interpreter the full scGPT graph
resolves cleanly on. All of our own code (FastAPI, Pydantic, scanpy, etc.)
is 3.11/3.12 compatible; flipping back to 3.12 only requires changing two
lines in the `Dockerfile` once scGPT publishes a 3.12-friendly release.

## Quick start (local, with Docker + NVIDIA Container Toolkit)

1. Drop the pretrained checkpoint into `save/scGPT_human/`:

   ```text
   save/scGPT_human/args.json
   save/scGPT_human/vocab.json
   save/scGPT_human/best_model.pt
   ```

2. Build and start the service:

   ```bash
   docker compose up --build
   ```

3. Hit the API:

   ```bash
   curl -s localhost:8000/health
   curl -s -X POST localhost:8000/embed -H 'Content-Type: application/json' -d '{"dataset_url":"https://drive.google.com/file/d/XXXX/view","gene_col":"index","batch_key":"tech","cell_type_key":"celltype"}'
   curl -s -X POST localhost:8000/umap -H 'Content-Type: application/json' -d '{"dataset_url":"https://drive.google.com/file/d/XXXX/view","gene_col":"gene_name","batch_key":"str_batch","cell_type_key":"celltype"}'
   curl -s localhost:8000/job/JOB_ID
   ```

OpenAPI / Swagger docs are auto-generated at `http://localhost:8000/docs`.

---

## API surface

| Method | Path             | Purpose                                                   |
| ------ | ---------------- | --------------------------------------------------------- |
| GET    | `/health`        | Liveness + GPU + model metadata                           |
| POST   | `/embed`         | Download → embed → return `.h5ad` path                    |
| POST   | `/umap`          | Embed → neighbors → UMAP → PNG + CSV                      |
| POST   | `/annotate`      | Placeholder for scGPT reference mapping (returns 501)     |
| GET    | `/job/{job_id}`  | Inspect any past job's status / result / error            |

All error responses share a single typed envelope:

```json
{
  "error": "invalid_drive_url",
  "message": "Could not extract a Drive file id from URL: ...",
  "request_id": "0f2c..."
}
```

The `request_id` is also exposed as the `x-request-id` response header and
threaded into every JSON log line, so a single request can be traced from
the agent platform all the way to the GPU.

---

## Architecture

```text
┌───────────────────────────────────────────────────────────┐
│                       FastAPI app                         │
│                                                           │
│  middleware → request_id, access log                      │
│      │                                                    │
│      ▼                                                    │
│  POST /embed ──▶ GoogleDriveDownloader ──▶ cache/<id>.h5ad│
│      │                                                    │
│      ▼                                                    │
│  inference.run_embed                                      │
│      │ uses                                               │
│      ▼                                                    │
│  ScGPTModel (singleton on app.state.model)                │
│      │   loaded once at startup, lives in GPU memory      │
│      ▼                                                    │
│  TransformerModel(.cuda).eval()                           │
│      │                                                    │
│      ▼                                                    │
│  outputs/<job_id>_embed.h5ad  +  JobStore[job_id]         │
└───────────────────────────────────────────────────────────┘
```

### Model lifecycle

1. `app.py` defines an async `lifespan` context manager.
2. On startup it calls `load_model(settings)` which:
   * verifies `torch.cuda.is_available()` and fails fast if not,
   * loads `args.json`, `vocab.json`, `best_model.pt`,
   * builds the `TransformerModel`, moves it to `cuda:<device_id>`,
   * sets it in eval mode, stores it on `app.state.model`.
3. Every request reuses the same instance — there is no per-request load.
4. On shutdown `reset_model()` deletes the model and calls
   `torch.cuda.empty_cache()` so the next container start is clean.

The singleton is protected by an instance-level `threading.Lock`; concurrent
`/embed` calls are queued rather than racing for VRAM.

### Request lifecycle (`/embed`)

1. **Validation** – Pydantic rejects malformed payloads (HTTP 422).
2. **Job creation** – `JobStore.create()` returns a UUID and marks status
   `pending`.
3. **Status → running**, `started_at` timestamp recorded.
4. **Download** – `GoogleDriveDownloader.download()` extracts the file id
   from the URL, returns the cached file if present, otherwise calls
   `gdown.download(..., fuzzy=True)` and enforces `max_size_gb`.
5. **Load AnnData** – `anndata.read_h5ad()` with friendly error messages.
6. **Column validation** – the requested `batch_key`, `cell_type_key`,
   `gene_col` must exist.
7. **Encode** – `ScGPTModel.encode_anndata()`:
   * intersects the dataset gene list with the scGPT vocabulary,
   * runs scGPT's `Preprocessor` (normalize → log1p → binning),
   * tokenises each cell with a `<cls>` token, pads per batch,
   * runs `model._encode(...)` under `torch.no_grad` + AMP,
   * returns the CLS token embedding, L2-normalised.
8. **Persist** – embeddings stored in `obsm["X_scGPT"]`, written to
   `outputs/<job_id>_embed.h5ad` (gzip).
9. **Status → completed**, response returned to the client.
10. Any exception transitions the job to `failed` with a typed
    `ErrorResponse` and is re-raised so the registered exception handler
    can shape the HTTP error.

### Request lifecycle (`/umap`)

Same as `/embed`, then:

* `scanpy.pp.neighbors(use_rep="X_scGPT", metric=...)`
* `scanpy.tl.umap(min_dist=...)`
* `outputs/<job_id>_umap.h5ad`
* `outputs/<job_id>_umap.png` – a multi-panel figure coloured by each
  available `color_by` column.
* `outputs/<job_id>_umap.csv` – `cell_id, umap_1, umap_2, <color_by>...`.

---

## Configuration

Everything lives in `config.yaml`. The most commonly tuned knobs:

| YAML path                            | Purpose                                       |
| ------------------------------------ | --------------------------------------------- |
| `model.path`                         | Where `args.json/vocab.json/best_model.pt` live |
| `inference.batch_size`               | Per-batch cell count on GPU                    |
| `inference.max_seq_len`              | Truncate long cells to N tokens                |
| `inference.use_fast_transformer`     | Enable flash-attn (needs flash-attn installed) |
| `gpu.device_id`                      | Which CUDA device to bind                      |
| `gpu.memory_fraction`                | Cap VRAM usage when sharing a GPU              |
| `paths.cache_dir/output_dir/log_dir` | Writable directories                           |
| `download.cache_enabled`             | Reuse a previously downloaded file id          |
| `download.max_size_gb`               | Reject pathologically large datasets           |
| `umap.color_by`                      | Default obs columns to plot                    |
| `logging.json`                       | JSON lines vs. human-readable logs             |

Override the file path with `SCGPT_CONFIG=/etc/scgpt/config.yaml` for
environment-specific configs (typically mounted from an Azure Key Vault
or ConfigMap).

---

## Logging

* All logs go to **stdout** (picked up by `docker logs` / `kubectl logs`
  / Azure Log Analytics) **and** to a rotating file under `logs/`.
* When `logging.json: true` each line is a single JSON object including
  `timestamp`, `level`, `logger`, `message`, `request_id`, and any
  structured fields passed via `extra={}`.
* Key events: `app_startup`, `gpu_detected`, `model_loaded`, `request`,
  `drive_download_start/complete`, `encode_start/complete`,
  `embed_persisted`, `umap_persisted`, `request_failed`,
  `unhandled_exception`.

---

## Error handling

| Condition                              | HTTP | `error` code            |
| -------------------------------------- | ---- | ----------------------- |
| Malformed JSON / schema mismatch       | 422  | `invalid_request`       |
| Drive URL not parseable                | 400  | `invalid_drive_url`     |
| Drive download fails / size limit hit  | 502  | `download_failed`       |
| `.h5ad` corrupt / empty                | 400  | `invalid_dataset`       |
| Requested obs/var column missing       | 400  | `missing_columns`       |
| CUDA OOM during inference              | 507  | `cuda_out_of_memory`    |
| Model fails to load or run             | 503  | `model_error`           |
| `/annotate` (not implemented yet)      | 501  | `not_implemented`       |
| Any unhandled exception                | 500  | `internal_error`        |

---

## Deployment

### Local / Azure VM

```bash
git clone <repo> && cd scgpt-api   # NVIDIA driver + Container Toolkit required
docker compose up -d --build
```

### Azure Container Apps (GPU workload profile)

1. Push the image to Azure Container Registry:

   ```bash
   az acr build -r <registry> -t scgpt-api:1.0.0 .
   ```

2. Create a GPU-enabled workload profile (e.g. `NC24-A100`) on your
   Container Apps environment.
3. Create the app referencing that profile:

   ```bash
   az containerapp create --name scgpt-api --environment <env> --image <registry>.azurecr.io/scgpt-api:1.0.0 --workload-profile-name gpu-a100 --cpu 8 --memory 32Gi --target-port 8000 --ingress external --min-replicas 1 --max-replicas 1 --secrets storage-key=<storage-account-key> --env-vars SCGPT_CONFIG=/app/config.yaml --azure-file-volume name=models account-name=<sa> account-key=secretref:storage-key share-name=scgpt-models mount-path=/app/save
   ```

   The model weights live on an Azure Files share mounted read-only at
   `/app/save`. Outputs / cache can live on a second Azure Files share or
   a managed disk – both are exposed via the `paths.*` keys in
   `config.yaml`.

4. Keep `min-replicas=1`: scGPT takes ~30–60 seconds to load and scale-to-
   zero would force every cold start to reload the model.

### Azure Kubernetes Service

A minimal manifest pattern (omitting Service / Ingress for brevity):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: scgpt-api
spec:
  replicas: 1
  selector:
    matchLabels: {app: scgpt-api}
  template:
    metadata:
      labels: {app: scgpt-api}
    spec:
      runtimeClassName: nvidia
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      containers:
        - name: scgpt-api
          image: <registry>.azurecr.io/scgpt-api:1.0.0
          ports: [{containerPort: 8000}]
          resources:
            limits:
              nvidia.com/gpu: 1
              cpu: "8"
              memory: 32Gi
          env:
            - name: SCGPT_CONFIG
              value: /app/config.yaml
          volumeMounts:
            - {name: models, mountPath: /app/save, readOnly: true}
            - {name: cache,  mountPath: /app/cache}
            - {name: outputs, mountPath: /app/outputs}
          readinessProbe:
            httpGet: {path: /health, port: 8000}
            initialDelaySeconds: 90
            periodSeconds: 15
          livenessProbe:
            httpGet: {path: /health, port: 8000}
            initialDelaySeconds: 180
            periodSeconds: 30
      volumes:
        - name: models
          azureFile:
            secretName: storage-secret
            shareName: scgpt-models
            readOnly: true
        - name: cache
          persistentVolumeClaim: {claimName: scgpt-cache}
        - name: outputs
          persistentVolumeClaim: {claimName: scgpt-outputs}
```

### Azure-specific considerations

* **GPU SKUs** – use NCv3 (V100) or NC A100 v4 / ND-series for production;
  scGPT is happy on a single A100 or V100. Confirm CUDA 12.x driver
  support on the chosen image.
* **Cold starts** – model load is ~30–60 s. Pre-warm with a single
  always-on replica, and add a `startupProbe` so Kubernetes does not
  restart the pod during initial loading.
* **Storage** – store the checkpoint on **Azure Files Premium** (NFS or
  SMB). Mount read-only into every replica. Output `.h5ad` and PNG files
  can go on a **second** Azure Files share so they are visible to the
  agent platform without bouncing through the API.
* **Secrets** – `SCGPT_CONFIG` is environment-driven; mount production
  configs from Key Vault using the CSI driver.
* **Observability** – the structured JSON logs flow straight into Azure
  Monitor / Log Analytics. Use `request_id` for correlation with the
  upstream agent platform.
* **Cost** – set `download.cache_enabled: true` so re-running the same
  dataset is a no-op on Drive. Cap `download.max_size_gb` to prevent
  accidental egress.
* **Concurrency** – keep `app.workers: 1` (each worker is a full copy of
  the model in VRAM). For higher throughput, scale **replicas**, not
  workers.

---

## Integration with an agent platform (OpenClaw-style)

The API is designed to be wrapped as a single tool with three actions
(`embed`, `umap`, `annotate`). A minimal tool descriptor:

```json
{
  "name": "scgpt",
  "description": "Run scGPT single-cell analyses on a Google Drive .h5ad",
  "actions": [
    {
      "name": "embed",
      "method": "POST",
      "url": "http://scgpt-api/embed",
      "input_schema": "$ref:/openapi.json#/components/schemas/EmbedRequest",
      "output_schema": "$ref:/openapi.json#/components/schemas/EmbedResponse"
    },
    {
      "name": "umap",
      "method": "POST",
      "url": "http://scgpt-api/umap",
      "input_schema": "$ref:/openapi.json#/components/schemas/UMAPRequest",
      "output_schema": "$ref:/openapi.json#/components/schemas/UMAPResponse"
    },
    {
      "name": "annotate",
      "method": "POST",
      "url": "http://scgpt-api/annotate",
      "input_schema": "$ref:/openapi.json#/components/schemas/AnnotateRequest",
      "output_schema": "$ref:/openapi.json#/components/schemas/AnnotateResponse"
    }
  ]
}
```

Because every response includes the on-disk `embedding_file` / `umap_png`
paths, downstream agent steps (chart rendering, classification, etc.) can
read those artefacts straight from the shared volume.
