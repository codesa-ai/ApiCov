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
  pytest src/tests/tests.py

# Build binary
build:
  . .venv/bin/activate && .venv/bin/python -m PyInstaller --onefile --python-option="--enable-shared" src/apicov.py

