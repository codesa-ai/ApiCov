#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Debug: Script directory: $SCRIPT_DIR"
echo "Debug: All arguments received: $@"

# Check if the apicov binary exists
if [[ ! -f "$SCRIPT_DIR/apicov" ]]; then
  echo "Error: apicov binary not found in $SCRIPT_DIR"
  exit 1
fi

CMD="$SCRIPT_DIR/apicov" "$@"

echo "Debug: Full command to be executed: $CMD"
# Run the apicov binary with the provided arguments
eval "$CMD"
