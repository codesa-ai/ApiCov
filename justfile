# print all commands
default:
  @just --list

# enter virtual environment
shell:
  @echo "run this:\nsource .venv/bin/activate"

# Create virtual environment with Python 3.10
venv:
  python3.10 -m venv .venv
  . .venv/bin/activate && pip install -e .

# Prepare the target for testing (vorbis)
test-prep:
  cd "$(dirname "$(readlink -f "$0")")"
  git submodule update --init --recursive
  chmod +x ./tests/prep_target.sh
  ./src/tests/prep_target.sh
  cd ../../..

# Run the tests (vorbis)
test:
  PYTHONPATH=src pytest tests/tests.py -v

# Build binary locally (may have GLIBC compatibility issues - prefer build-docker for releases)
build:
  . .venv/bin/activate && .venv/bin/python -m PyInstaller --onefile \
  --clean \
  --strip \
  --noconfirm \
  --hidden-import=gcov \
  --hidden-import=modules \
  --hidden-import=requests \
  --hidden-import=bs4 \
  --hidden-import=bs4.builder._lxml \
  --hidden-import=lxml \
  --hidden-import=lxml.etree \
  --hidden-import=lxml._elementpath \
  --hidden-import=xml \
  --hidden-import=xml.etree \
  --hidden-import=xml.etree.ElementTree \
  --hidden-import=xml.parsers \
  --hidden-import=xml.parsers.expat \
  --collect-submodules xml \
  --python-option="--enable-shared" \
  --add-data "src/modules:modules" \
  src/apicov.py

# Build binary using Docker for Ubuntu 22.04 compatibility (recommended for releases)
build-docker:
  #!/usr/bin/env bash
  set -euo pipefail
  echo "Building Docker image for Ubuntu 22.04..."
  docker build -f Dockerfile.build -t apicov-builder .
  echo "Extracting binary from container..."
  mkdir -p dist
  docker create --name apicov-extract apicov-builder
  docker cp apicov-extract:/app/dist/apicov dist/apicov
  docker rm apicov-extract
  chmod +x dist/apicov
  echo "✅ Binary built successfully at dist/apicov"
  echo "   This binary is compatible with Ubuntu 22.04+ (GLIBC 2.35+)"

# reformat the code with Ruff
format:
  uv run ruff format

# check and fix the code with Ruff
lint:
  uv run ruff check --fix

# make sure everything is in a fit state to check in
prepare: lint format test