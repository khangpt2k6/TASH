# scGPT API – CUDA 12.1 / Python 3.11 image
#
# NOTE on Python version: scGPT 0.2.4 (the latest released version) pins
# scvi-tools<1.0, torchtext, cell-gears<0.0.3 and orbax<0.1.8 transitively.
# None of those releases publish Python-3.12 wheels, so the full scGPT
# dependency graph only resolves cleanly on Python 3.11. We deliberately
# target 3.11 here; the rest of the stack (FastAPI, Pydantic, scanpy, etc.)
# is fully 3.11/3.12 compatible.
#
# Build: docker build -t scgpt-api:latest .
# Run:   docker run --rm --gpus all -p 8000:8000 -v $(pwd)/save:/app/save:ro -v $(pwd)/cache:/app/cache -v $(pwd)/outputs:/app/outputs -v $(pwd)/logs:/app/logs scgpt-api:latest

FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04 AS base

# Tell Python and pip to behave well inside a container.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Etc/UTC

# System packages: Python 3.11 via deadsnakes, plus headers for scientific wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common \
        ca-certificates \
        curl \
        git \
        build-essential \
        libhdf5-dev \
        libxml2 \
        libgomp1 \
        tini \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-dev \
        python3.11-venv \
        python3.11-distutils \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python3 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch with CUDA 12.1 wheels first. Doing this as a separate layer
# keeps the (large, slow) PyTorch download cached across rebuilds when only
# requirements.txt changes.
RUN python -m pip install -U pip setuptools wheel && python -m pip install --index-url https://download.pytorch.org/whl/cu121 torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1

# Application Python dependencies.
COPY requirements.txt /app/requirements.txt
RUN python -m pip install -r /app/requirements.txt

# Application source. We copy this last so iterating on Python files is fast.
COPY app.py model_loader.py inference.py schemas.py jobs.py gdrive.py \
     logging_config.py config.py config.yaml /app/

# Create runtime directories (will normally be mounted from the host / a PVC,
# but having them present means the image works standalone too).
RUN mkdir -p /app/save/scGPT_human /app/cache/downloaded_datasets /app/outputs /app/logs

# Runtime configuration.
EXPOSE 8000

# Run as a non-root user. Mounted volumes from the host should be owned by
# (or world-writable for) uid 1000.
RUN useradd --create-home --uid 1000 scgpt \
    && chown -R scgpt:scgpt /app
USER scgpt

# K8s/Container Apps liveness + readiness can hit /health.
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -sf http://127.0.0.1:8000/health || exit 1

# Tini reaps zombie processes if anything (e.g. matplotlib) forks.
ENTRYPOINT ["/usr/bin/tini", "--"]
# uvicorn: --no-access-log; no --log-config (JSON logging in lifespan)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "1800", "--no-access-log"]
