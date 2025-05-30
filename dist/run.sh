#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Debug: Script directory: $SCRIPT_DIR"
echo "Debug: Argument 1 (root_path): $1"
echo "Debug: Argument 2 (api_key): $2"
echo "Debug: Argument 3 (install_path): $3"

# Check if the apicov binary exists in the same directory
if [[ -f "$SCRIPT_DIR/apicov" ]]; then
  echo "Debug: Found apicov binary at: $SCRIPT_DIR/apicov"

  # Construct the command based on number of arguments
  if [ -n "$3" ]; then
    echo "Debug: Using install_dir: $3"
    CMD="$SCRIPT_DIR/apicov \"$1\" \"$2\" --install_dir \"$3\""
  else
    echo "Debug: No install_dir provided"
    CMD="$SCRIPT_DIR/apicov \"$1\" \"$2\""
  fi

  echo "Debug: Full command to be executed: $CMD"
  # Run the apicov binary with the provided arguments
  eval "$CMD"
else
  echo "Error: apicov binary not found in $SCRIPT_DIR"
  exit 1
fi
