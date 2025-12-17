#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/vorbis"
./autogen.sh
./configure CFLAGS="--coverage -O0"
make
make check