#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Debug: Script directory: $SCRIPT_DIR"
echo "Debug: Argument 1 (root_path): $1"
echo "Debug: Argument 2 (api_key): $2"
echo "Debug: Argument 3 (install_path): $3"
echo "Debug: Argument 4 (doxygen_path): $4"

# Check if the apicov binary exists in the same directory
if [[ -f "$SCRIPT_DIR/apicov" ]]; then
  echo "Debug: Found apicov binary at: $SCRIPT_DIR/apicov"

  # Require install_dir (argument 3)
  if [ -z "$3" ]; then
    echo "Error: install_dir (argument 3) is required."
    echo "Usage: $0 <root_path> <api_key> <install_dir> [doxygen_path]"
    exit 1
  fi

  if [ -n "$4" ]; then
    echo "Debug: Using install_dir: $3 and doxygen_path: $4"
    CMD="$SCRIPT_DIR/apicov \"$1\" \"$2\" --install_dir \"$3\" --doxygen_path \"$4\""
  else
    echo "Debug: Using install_dir: $3"
    CMD="$SCRIPT_DIR/apicov \"$1\" \"$2\" --install_dir \"$3\""
  fi

  echo "Debug: Full command to be executed: $CMD"
  # Run the apicov binary with the provided arguments
  eval "$CMD"
else
  echo "Error: apicov binary not found in $SCRIPT_DIR"
  exit 1
fi
