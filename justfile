# print all commands
default:
  @just --list

# enter virtual environment
shell:
  @echo "run this:\nsource .venv/bin/activate"

# Prepare the target for testing (vorbis)
test-prep:
  # Ensure we're in the root directory
  cd "$(dirname "$(readlink -f "$0")")"
  git submodule update --init --recursive
  chmod +x ./src/tests/prep_target.sh
  ./src/tests/prep_target.sh
  cd ../../..

# Run the tests (vorbis)
test:
  pytest src/tests/tests.py
