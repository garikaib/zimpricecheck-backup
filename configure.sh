#!/bin/bash
# Configuration Wrapper Script

# Ensure we are in the project root
cd "$(dirname "$0")"

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Install requirements
echo "Checking dependencies..."
./venv/bin/pip install -q -r requirements.txt

# Pass all arguments to the python script
./venv/bin/python3 lib/configure.py "$@"
