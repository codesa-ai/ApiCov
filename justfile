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
  chmod +x ./src/tests/prep_target.sh
  ./src/tests/prep_target.sh
  cd ../../..

# Run the tests (vorbis)
test:
  pytest src/tests/tests.py -v

# Build binary
build:
  . .venv/bin/activate && .venv/bin/python -m PyInstaller --onefile \
  --clean \
  --strip \
  --noconfirm \
  --add-binary "/usr/lib/x86_64-linux-gnu/libm.so.6:." \
  --hidden-import=gcov \
  --hidden-import=modules \
  --hidden-import=requests \
  --hidden-import=bs4 \
  --hidden-import=bs4.builder._lxml \
  --hidden-import=lxml \
  --hidden-import=lxml.etree \
  --hidden-import=lxml._elementpath \
  --python-option="--enable-shared" \
  --add-data "src/modules:modules" \
  src/apicov.py

# reformat the code with Ruff
format:
  uv run ruff format

# check and fix the code with Ruff
lint:
  uv run ruff check --fix

# make sure everything is in a fit state to check in
prepare: lint format test