#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if the apicov binary exists in the same directory
if [[ -f "$SCRIPT_DIR/apicov" ]]; then
  echo "Executing: $SCRIPT_DIR/apicov $1 $2"
  # Run the apicov binary with the provided arguments
  "$SCRIPT_DIR/apicov" "$1" "$2"
else
  echo "Error: apicov binary not found in $SCRIPT_DIR"
  exit 1
fi