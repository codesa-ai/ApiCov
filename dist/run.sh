#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Debug: Script directory: $SCRIPT_DIR"
echo "Debug: Argument 1 (root_path): $1"
echo "Debug: Argument 2 (install_path): $2"
echo "Debug: Argument 3 (api_key): $3"

# Check if the apicov binary exists in the same directory
if [[ -f "$SCRIPT_DIR/apicov" ]]; then
  echo "Debug: Found apicov binary at: $SCRIPT_DIR/apicov"
  echo "Debug: Full command to be executed: $SCRIPT_DIR/apicov $1 $2 $3"
  # Run the apicov binary with the provided arguments
  "$SCRIPT_DIR/apicov" "$1" "$2" "$3"
else
  echo "Error: apicov binary not found in $SCRIPT_DIR"
  exit 1
fi 