#!/usr/bin/env bash
# Render build script

set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Initializing database..."
python init_db_postgres.py

echo "Build complete!"
