# The Python environment of the project page server. The image holds no project files: docker-compose.yml mounts the
# repository at /app (read-only), so the container always runs the code, models and recordings that are on disk.
# The build context is the repository, from which deploy/Dockerfile.dockerignore lets in two files: this image's
# requirements and the lock file, constraints.txt, so that every package is installed at its locked version (BUG-9).
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

# pip itself first: the base image's pip 24.0 has a dozen published advisories. 26.2.2 is the version on the project laptop.
RUN pip install pip==26.2.2
# PyTorch alone from its own index; its dependencies come with everything else, below
RUN pip install --no-deps --index-url "${TORCH_INDEX}" torch==2.14.0
COPY deploy/requirements-serve.txt constraints.txt /tmp/
# Every package at its version in constraints.txt. torch is named again so that its dependencies are installed, and
# setuptools (from the base image) so that it is brought to the locked version. pip check: every requirement is met.
RUN pip install -r /tmp/requirements-serve.txt -c /tmp/constraints.txt torch==2.14.0 setuptools \
 && pip check \
 && rm /tmp/requirements-serve.txt /tmp/constraints.txt

# The page is on the internet, so the server does not run as root
RUN useradd --create-home --uid 1000 app
USER app
WORKDIR /app

EXPOSE 8000
# 0.0.0.0 inside the container's own network, which only Tailscale and this computer's localhost can reach
CMD ["python", "whistlecode/whistlecode.py", "serve", "--host", "0.0.0.0", "--port", "8000"]
