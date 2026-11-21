#!/usr/bin/env bash
# One-time setup on the node that runs the app (run it inside the unzipped whistle_app/ folder):
#     bash setup_node.sh
#
# Python: the code needs 3.11 or newer. Ubuntu 20.04 nodes ship 3.8, so when no system Python >= 3.11 exists the
# script uses a portable Python 3.11 in .python/ (no sudo): from offline/ when the zip carries it, else downloaded.
# Packages: from offline/wheels/ when the zip carries them (node without internet), else from the internet.
# Options:   PYTHON=/path/to/python3.11      use that Python
#            USE_PORTABLE_PYTHON=1           use the portable Python even if the node has 3.11
set -euo pipefail
cd "$(dirname "$0")"

PY_TAR="cpython-3.11.10+20241016-x86_64-unknown-linux-gnu-install_only.tar.gz"
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20241016/$PY_TAR"
PY_SHA="8b50a442b04724a24c1eebb65a36a0c0e833d35374dbdf9c9470d8a97b164cd9"
TORCH="2.14.0"     # the version the detector and the VAE were trained and tested with (requirements.txt: >=2.11)

echo "== 1/4 checking the unpacked files"
sha256sum -c --quiet MANIFEST.sha256
echo "   all files match MANIFEST.sha256"

echo "== 2/4 finding Python >= 3.11"
PY="${PYTHON:-}"
if [ -z "$PY" ] && [ "${USE_PORTABLE_PYTHON:-0}" != 1 ]; then
  for c in python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
      PY="$(command -v "$c")"; break
    fi
  done
fi
if [ -z "$PY" ]; then
  if [ ! -x .python/bin/python3.11 ]; then
    echo "   no system Python >= 3.11 ($(python3 --version 2>&1 || echo 'none')); setting up a portable Python 3.11"
    tarball="offline/$PY_TAR"
    if [ ! -f "$tarball" ]; then
      mkdir -p offline
      echo "   downloading $PY_TAR (30 MB)"
      if command -v curl >/dev/null 2>&1; then curl -fL --retry 3 -o "$tarball" "$PY_URL" || true
      else wget -q -O "$tarball" "$PY_URL" || true; fi
      if [ ! -s "$tarball" ]; then
        rm -f "$tarball"
        echo "Download failed: this node has no internet access. Build the zip on the laptop with the offline kit"
        echo "(python cluster/make_offline_kit.py, then python cluster/make_cluster_bundle.py) and upload it again."
        exit 1
      fi
    fi
    echo "$PY_SHA  $tarball" | sha256sum -c --quiet
    rm -rf .python python && tar -xzf "$tarball" && mv python .python
  fi
  PY="$PWD/.python/bin/python3.11"
fi
echo "   using $("$PY" --version) at $PY"

echo "== 3/4 installing the packages into .venv"
rm -rf .venv
"$PY" -m venv .venv
PIP=(.venv/bin/python -m pip install --disable-pip-version-check --no-warn-script-location)
if [ -d offline/wheels ]; then
  echo "   from offline/wheels (no internet needed)"
  "${PIP[@]}" --no-index --find-links offline/wheels "torch==$TORCH" -r requirements-node.txt
else
  if ! .venv/bin/python -c "import urllib.request as u; u.urlopen('https://pypi.org/simple/pip/', timeout=15)" 2>/dev/null; then
    echo "pypi.org cannot be reached from this node, and the zip has no offline/wheels folder. Build the zip on the laptop"
    echo "with the offline kit (python cluster/make_offline_kit.py, then python cluster/make_cluster_bundle.py)."
    exit 1
  fi
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    "${PIP[@]}" "torch==$TORCH" -r requirements-node.txt                                                # GPU node: CUDA build
  else
    "${PIP[@]}" "torch==$TORCH" --index-url https://download.pytorch.org/whl/cpu                         # CPU node: small build
    "${PIP[@]}" -r requirements-node.txt
  fi
fi

echo "== 4/4 loading the detector and the trained model"
.venv/bin/python whistle.py model-status | grep -E '"(message|recreate|same_type|generate|conditional)"'
echo "Setup finished. Start the app with:  bash run_node.sh"
