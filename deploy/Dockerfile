# The Python environment of the project page server. The image holds no project files: docker-compose.yml mounts the
# repository at /app (read-only), so the container always runs the code, models and recordings that are on disk.
#
#   CPU (default):  docker compose -f deploy/docker-compose.yml build
#   NVIDIA GPU:     docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.gpu.yml build
FROM python:3.11-slim-bookworm

# Where PyTorch comes from: the CPU build (about 200 MB) or, via docker-compose.gpu.yml, the CUDA 13.0 build (several GB)
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib

RUN pip install --index-url "${TORCH_INDEX}" torch==2.14.0
COPY requirements-serve.txt /tmp/requirements-serve.txt
RUN pip install -r /tmp/requirements-serve.txt && rm /tmp/requirements-serve.txt

# The page is on the internet, so the server does not run as root
RUN useradd --create-home --uid 1000 app
USER app
WORKDIR /app

EXPOSE 8000
# 0.0.0.0 inside the container's own network, which only Tailscale and this computer's localhost can reach
CMD ["python", "whistlecode/whistlecode.py", "serve", "--host", "0.0.0.0", "--port", "8000"]
