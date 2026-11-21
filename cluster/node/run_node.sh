#!/usr/bin/env bash
# Start the app (page + API) on this node:
#     bash run_node.sh                               after setup_node.sh (uses .venv)
#     PYTHON=/path/to/anaconda/envs/<env>/bin/python bash run_node.sh
#                                                    with a ready Python, e.g. the mentor's Anaconda (check_node.py says OK)
#     HOST=0.0.0.0 bash run_node.sh                  every machine on the cluster network can open http://<node>:8000
#     PORT=8080 DEVICE=cpu bash run_node.sh          another port / force cpu or cuda
# Keep it running after logout:   nohup bash run_node.sh > server.log 2>&1 &
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-.venv/bin/python}"
if [ ! -x "$PY" ] && ! command -v "$PY" >/dev/null 2>&1; then
  echo "No Python at $PY: run setup_node.sh first, or give a ready one with PYTHON=/path/to/python"; exit 1
fi
exec "$PY" whistle.py serve --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}" ${DEVICE:+--device "$DEVICE"}
